"""Face detection + 1:1 matching (InsightFace / YuNet / OpenCV Haar)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path

import cv2
import numpy as np

from liveness.config import get_settings


@dataclass
class FaceDetection:
    bbox: tuple[int, int, int, int]  # x, y, w, h
    embedding: np.ndarray | None = None
    confidence: float = 1.0
    pose_yaw: float | None = None
    pose_pitch: float | None = None
    pose_roll: float | None = None


@dataclass
class FaceMatchReport:
    score: float
    passed: bool
    backend: str
    face_detected_a: bool
    face_detected_b: bool


def _yunet_model_path() -> Path | None:
    settings = get_settings()
    candidates = [
        settings.models_dir / "face_detection_yunet_2023mar.onnx",
        Path(__file__).resolve().parents[3] / "models" / "face_detection_yunet_2023mar.onnx",
        Path("/app/models/face_detection_yunet_2023mar.onnx"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


class FaceAnalyzer:
    def __init__(self) -> None:
        self.threshold = get_settings().face_match_threshold
        self._app = None
        self._yunet = None
        self._cascade = None
        self._backend = "histogram"

        settings = get_settings()
        if settings.insightface_enabled:
            try:
                from insightface.app import FaceAnalysis

                app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                app.prepare(ctx_id=-1, det_size=(640, 640))
                self._app = app
                self._backend = "insightface"
                return
            except Exception:
                self._app = None

        # Lightweight YuNet (~230KB) — good for Render free tier
        yunet_path = _yunet_model_path()
        if yunet_path is not None and hasattr(cv2, "FaceDetectorYN"):
            try:
                detector = cv2.FaceDetectorYN.create(
                    str(yunet_path),
                    "",
                    (320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000,
                )
                self._yunet = detector
                self._backend = "opencv_yunet"
            except Exception:
                self._yunet = None

        # Haar cascade fallback
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
            for name in (
                "haarcascade_frontalface_default.xml",
                "haarcascade_frontalface_alt2.xml",
            ):
                try:
                    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + name)
                    if not cascade.empty():
                        self._cascade = cascade
                        if self._backend == "histogram":
                            self._backend = "opencv_haar"
                        break
                except Exception:
                    continue

    def _largest_face(self, faces: list[FaceDetection]) -> FaceDetection | None:
        if not faces:
            return None
        return max(faces, key=lambda f: f.bbox[2] * f.bbox[3])

    def _pose_from_insightface(self, face) -> tuple[float | None, float | None, float | None]:
        raw = getattr(face, "pose", None)
        if raw is None:
            return None, None, None
        arr = np.asarray(raw, dtype=np.float32).reshape(-1)
        if arr.size < 3:
            return None, None, None
        yaw, pitch, roll = float(arr[0]), float(arr[1]), float(arr[2])
        # InsightFace reports degrees for most buffalo models.
        if max(abs(yaw), abs(pitch), abs(roll)) <= math.pi + 0.01:
            yaw, pitch, roll = math.degrees(yaw), math.degrees(pitch), math.degrees(roll)
        return yaw, pitch, roll

    def _detect_insightface(self, image: np.ndarray) -> list[FaceDetection]:
        assert self._app is not None
        faces = self._app.get(image)
        out: list[FaceDetection] = []
        for f in faces:
            x1, y1, x2, y2 = f.bbox.astype(int)
            yaw, pitch, roll = self._pose_from_insightface(f)
            out.append(
                FaceDetection(
                    bbox=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                    embedding=np.asarray(f.normed_embedding, dtype=np.float32),
                    confidence=float(getattr(f, "det_score", 1.0)),
                    pose_yaw=yaw,
                    pose_pitch=pitch,
                    pose_roll=roll,
                )
            )
        return out

    def _detect_yunet(self, image: np.ndarray) -> list[FaceDetection]:
        if self._yunet is None:
            return []
        h, w = image.shape[:2]
        self._yunet.setInputSize((w, h))
        _, faces = self._yunet.detect(image)
        if faces is None or len(faces) == 0:
            return []
        out: list[FaceDetection] = []
        for row in faces:
            x, y, bw, bh = [int(v) for v in row[:4]]
            score = float(row[-1]) if len(row) > 4 else 1.0
            if bw < 20 or bh < 20:
                continue
            # YuNet landmarks: right_eye, left_eye, nose, right_mouth, left_mouth
            pose_yaw = pose_pitch = pose_roll = None
            if len(row) >= 14:
                re_x, re_y = float(row[4]), float(row[5])
                le_x, le_y = float(row[6]), float(row[7])
                nose_x, nose_y = float(row[8]), float(row[9])
                eye_mid_x = (re_x + le_x) / 2.0
                eye_mid_y = (re_y + le_y) / 2.0
                eye_dist = max(abs(le_x - re_x), 1.0)
                # Rough frontal proxies from landmark geometry
                pose_yaw = float(np.clip(((nose_x - eye_mid_x) / eye_dist) * 35.0, -45, 45))
                pose_pitch = float(np.clip(((nose_y - eye_mid_y) / max(bh, 1) * 2 - 0.55) * 40.0, -40, 40))
                pose_roll = float(np.clip(math.degrees(math.atan2(le_y - re_y, max(le_x - re_x, 1e-3))), -30, 30))
            out.append(
                FaceDetection(
                    bbox=(max(0, x), max(0, y), bw, bh),
                    confidence=score,
                    pose_yaw=pose_yaw,
                    pose_pitch=pose_pitch,
                    pose_roll=pose_roll,
                )
            )
        return out

    def _detect_haar(self, image: np.ndarray, *, min_size: tuple[int, int]) -> list[FaceDetection]:
        if self._cascade is None:
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        rects = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=3,
            minSize=min_size,
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        return [FaceDetection(bbox=(int(x), int(y), int(w), int(h))) for (x, y, w, h) in rects]

    def _document_face_regions(self, image: np.ndarray) -> list[tuple[np.ndarray, int, int]]:
        """Crop regions where ID/passport portrait photos usually appear."""
        h, w = image.shape[:2]
        regions: list[tuple[np.ndarray, int, int]] = [(image, 0, 0)]
        third = max(w // 3, 1)
        regions.append((image[:, :third], 0, 0))
        regions.append((image[:, third : 2 * third], third, 0))
        regions.append((image[:, 2 * third :], 2 * third, 0))
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
                            pose_yaw=f.pose_yaw,
                            pose_pitch=f.pose_pitch,
                            pose_roll=f.pose_roll,
                        )
                    )
            return collected

        faces = self._detect_yunet(image)
        if faces:
            return faces

        min_size = (24, 24) if document_mode else (40, 40)
        faces = self._detect_haar(image, min_size=min_size)
        if faces or not document_mode:
            # For selfies, also try a scaled-down pass if full-res missed
            if not faces and not document_mode:
                h, w = image.shape[:2]
                if max(h, w) > 640:
                    scale = 640 / max(h, w)
                    small = cv2.resize(image, (int(w * scale), int(h * scale)))
                    for f in self._detect_yunet(small) or self._detect_haar(small, min_size=(30, 30)):
                        x, y, bw, bh = f.bbox
                        faces.append(
                            FaceDetection(
                                bbox=(int(x / scale), int(y / scale), int(bw / scale), int(bh / scale)),
                                confidence=f.confidence,
                                pose_yaw=f.pose_yaw,
                                pose_pitch=f.pose_pitch,
                                pose_roll=f.pose_roll,
                            )
                        )
            return faces

        collected: list[FaceDetection] = []
        for crop, ox, oy in self._document_face_regions(image):
            if crop.size == 0:
                continue
            for f in self._detect_yunet(crop) or self._detect_haar(crop, min_size=(20, 20)):
                x, y, bw, bh = f.bbox
                collected.append(
                    FaceDetection(
                        bbox=(x + ox, y + oy, bw, bh),
                        confidence=f.confidence,
                        pose_yaw=f.pose_yaw,
                        pose_pitch=f.pose_pitch,
                        pose_roll=f.pose_roll,
                    )
                )
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
        score = max(0.0, min(1.0, score))

        if self._backend == "insightface":
            thr = self.threshold
        elif self._backend in {"opencv_yunet", "opencv_haar"}:
            thr = max(0.32, self.threshold - 0.08)
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
