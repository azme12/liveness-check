"""Face detection + 1:1 matching (InsightFace when available, OpenCV fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np

from liveness.config import get_settings


@dataclass
class FaceDetection:
    bbox: tuple[int, int, int, int]  # x, y, w, h
    embedding: np.ndarray | None = None
    confidence: float = 1.0


@dataclass
class FaceMatchReport:
    score: float
    passed: bool
    backend: str
    face_detected_a: bool
    face_detected_b: bool


class FaceAnalyzer:
    def __init__(self) -> None:
        self.threshold = get_settings().face_match_threshold
        self._app = None
        self._cascade = None
        self._backend = "histogram"

        try:
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=-1, det_size=(640, 640))
            self._app = app
            self._backend = "insightface"
            return
        except Exception:
            self._app = None

        # OpenCV 4.x Haar cascades
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
            try:
                cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                )
                if not cascade.empty():
                    self._cascade = cascade
                    self._backend = "opencv_haar"
            except Exception:
                self._cascade = None

    def _largest_face(self, faces: list[FaceDetection]) -> FaceDetection | None:
        if not faces:
            return None
        return max(faces, key=lambda f: f.bbox[2] * f.bbox[3])

    def _detect_insightface(self, image: np.ndarray) -> list[FaceDetection]:
        assert self._app is not None
        faces = self._app.get(image)
        out: list[FaceDetection] = []
        for f in faces:
            x1, y1, x2, y2 = f.bbox.astype(int)
            out.append(
                FaceDetection(
                    bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                    embedding=np.asarray(f.normed_embedding, dtype=np.float32),
                    confidence=float(getattr(f, "det_score", 1.0)),
                )
            )
        return out

    def _detect_haar(self, image: np.ndarray, *, min_size: tuple[int, int]) -> list[FaceDetection]:
        if self._cascade is None:
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        rects = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=4,
            minSize=min_size,
        )
        return [FaceDetection(bbox=(int(x), int(y), int(w), int(h))) for (x, y, w, h) in rects]

    def _document_face_regions(self, image: np.ndarray) -> list[tuple[np.ndarray, int, int]]:
        """Crop regions where ID/passport portrait photos usually appear."""
        h, w = image.shape[:2]
        regions: list[tuple[np.ndarray, int, int]] = [(image, 0, 0)]
        # Portrait on left or right third (Fayda, passports, many national IDs)
        third = max(w // 3, 1)
        regions.append((image[:, :third], 0, 0))
        regions.append((image[:, third : 2 * third], third, 0))
        regions.append((image[:, 2 * third :], 2 * third, 0))
        # Top half often contains the photo on vertical IDs
        half_h = max(h // 2, 1)
        regions.append((image[:half_h, :], 0, 0))
        regions.append((image[:half_h, :third], 0, 0))
        regions.append((image[:half_h, 2 * third :], 2 * third, 0))
        return regions

    def detect(self, image: np.ndarray, *, document_mode: bool = False) -> list[FaceDetection]:
        if self._app is not None:
            faces = self._detect_insightface(image)
            if faces:
                return faces
            if not document_mode:
                return faces
            # Retry portrait crops on ID scans
            collected: list[FaceDetection] = []
            for crop, ox, oy in self._document_face_regions(image):
                if crop.size == 0 or min(crop.shape[:2]) < 40:
                    continue
                for f in self._detect_insightface(crop):
                    x, y, bw, bh = f.bbox
                    collected.append(
                        FaceDetection(
                            bbox=(x + ox, y + oy, bw, bh),
                            embedding=f.embedding,
                            confidence=f.confidence,
                        )
                    )
            return collected

        min_size = (28, 28) if document_mode else (60, 60)
        faces = self._detect_haar(image, min_size=min_size)
        if faces or not document_mode:
            return faces

        collected: list[FaceDetection] = []
        for crop, ox, oy in self._document_face_regions(image):
            if crop.size == 0:
                continue
            for f in self._detect_haar(crop, min_size=(24, 24)):
                x, y, bw, bh = f.bbox
                collected.append(FaceDetection(bbox=(x + ox, y + oy, bw, bh), confidence=f.confidence))
        return collected

    def _embedding_fallback(self, image: np.ndarray, face: FaceDetection) -> np.ndarray:
        x, y, w, h = face.bbox
        crop = image[max(0, y) : y + h, max(0, x) : x + w]
        if crop.size == 0:
            crop = image
        crop = cv2.resize(crop, (128, 128))
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
        vec = lab.astype(np.float32).reshape(-1)
        vec = vec - vec.mean()
        norm = np.linalg.norm(vec) + 1e-8
        return (vec / norm).astype(np.float32)

    def match(self, image_a: np.ndarray, image_b: np.ndarray) -> FaceMatchReport:
        """1:1 compare — image_a is the document portrait, image_b the live selfie."""
        faces_a = self.detect(image_a, document_mode=True)
        faces_b = self.detect(image_b, document_mode=False)
        fa = self._largest_face(faces_a)
        fb = self._largest_face(faces_b)

        if fa is None or fb is None:
            return FaceMatchReport(
                score=0.0,
                passed=False,
                backend=self._backend,
                face_detected_a=fa is not None,
                face_detected_b=fb is not None,
            )

        emb_a = fa.embedding if fa.embedding is not None else self._embedding_fallback(image_a, fa)
        emb_b = fb.embedding if fb.embedding is not None else self._embedding_fallback(image_b, fb)

        score = float(np.dot(emb_a, emb_b) / ((np.linalg.norm(emb_a) * np.linalg.norm(emb_b)) + 1e-8))
        # InsightFace cosine on normed embeddings is typically 0..1
        score = max(0.0, min(1.0, score))

        if self._backend == "insightface":
            thr = self.threshold
        elif self._backend == "opencv_haar":
            thr = max(0.35, self.threshold - 0.05)
        else:
            thr = 0.55

        return FaceMatchReport(
            score=score,
            passed=score >= thr,
            backend=self._backend,
            face_detected_a=True,
            face_detected_b=True,
        )


@lru_cache(maxsize=1)
def get_face_analyzer() -> FaceAnalyzer:
    """Process-wide singleton — InsightFace model load is expensive (~100MB+ RAM)."""
    return FaceAnalyzer()
