"""Face detection + 1:1 matching — InsightFace or YuNet + SFace only."""

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
    raw_row: np.ndarray | None = None


@dataclass
class FaceMatchReport:
    score: float
    passed: bool
    backend: str
    face_detected_a: bool
    face_detected_b: bool


_PRODUCTION_FACE_BACKENDS = frozenset({"insightface", "opencv_yunet_sface"})
_SFACE_MATCH_THRESHOLD = 0.363


def _model_path(filename: str) -> Path | None:
    settings = get_settings()
    candidates = [
        settings.models_dir / filename,
        Path(__file__).resolve().parents[3] / "models" / filename,
        Path("/app/models") / filename,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _offset_yunet_row(row: np.ndarray | None, ox: int, oy: int) -> np.ndarray | None:
    if row is None:
        return None
    out = np.asarray(row, dtype=np.float32).copy()
    out[0] += ox
    out[1] += oy
    for i in range(4, min(len(out), 14), 2):
        out[i] += ox
        out[i + 1] += oy
    return out


class FaceAnalyzer:
    def __init__(self) -> None:
        settings = get_settings()
        self.threshold = settings.face_match_threshold
        self._app = None
        self._yunet = None
        self._sface = None
        self._backend = "unavailable"

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

        yunet_path = _model_path("face_detection_yunet_2023mar.onnx")
        if yunet_path is not None and hasattr(cv2, "FaceDetectorYN"):
            try:
                self._yunet = cv2.FaceDetectorYN.create(
                    str(yunet_path),
                    "",
                    (320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000,
                )
                self._backend = "opencv_yunet"
            except Exception:
                self._yunet = None

        sface_path = _model_path("face_recognition_sface_2021dec.onnx")
        if self._yunet is not None and sface_path is not None and hasattr(cv2, "FaceRecognizerSF"):
            try:
                self._sface = cv2.FaceRecognizerSF.create(str(sface_path), "")
                self._backend = "opencv_yunet_sface"
            except Exception:
                self._sface = None

        if self._backend not in _PRODUCTION_FACE_BACKENDS:
            self._backend = "unavailable"

    @property
    def production_ready(self) -> bool:
        return self._backend in _PRODUCTION_FACE_BACKENDS

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
        if max(abs(yaw), abs(pitch), abs(roll)) <= math.pi + 0.01:
            yaw, pitch, roll = math.degrees(yaw), math.degrees(pitch), math.degrees(roll)
        return yaw, pitch, roll

    def _detect_insightface(self, image: np.ndarray) -> list[FaceDetection]:
        assert self._app is not None
        out: list[FaceDetection] = []
        for f in self._app.get(image):
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
            pose_yaw = pose_pitch = pose_roll = None
            if len(row) >= 14:
                re_x, re_y = float(row[4]), float(row[5])
                le_x, le_y = float(row[6]), float(row[7])
                nose_x, nose_y = float(row[8]), float(row[9])
                eye_mid_x = (re_x + le_x) / 2.0
                eye_mid_y = (re_y + le_y) / 2.0
                eye_dist = max(abs(le_x - re_x), 1.0)
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
                    raw_row=np.asarray(row, dtype=np.float32),
                )
            )
        return out

    def _sface_embedding(self, image: np.ndarray, face: FaceDetection) -> np.ndarray | None:
        if self._sface is None or face.raw_row is None:
            return None
        try:
            aligned = self._sface.alignCrop(image, face.raw_row.reshape(1, -1))
            feature = self._sface.feature(aligned)
            return np.asarray(feature, dtype=np.float32).reshape(-1)
        except Exception:
            return None

    def _document_face_regions(self, image: np.ndarray) -> list[tuple[np.ndarray, int, int]]:
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

    def _detect_yunet_scaled(self, image: np.ndarray) -> list[FaceDetection]:
        h, w = image.shape[:2]
        if max(h, w) <= 640:
            return []
        scale = 640 / max(h, w)
        small = cv2.resize(image, (int(w * scale), int(h * scale)))
        faces: list[FaceDetection] = []
        for f in self._detect_yunet(small):
            x, y, bw, bh = f.bbox
            row = f.raw_row.copy() if f.raw_row is not None else None
            if row is not None:
                row[0] /= scale
                row[1] /= scale
                row[2] /= scale
                row[3] /= scale
                for i in range(4, min(len(row), 14), 2):
                    row[i] /= scale
                    row[i + 1] /= scale
            faces.append(
                FaceDetection(
                    bbox=(int(x / scale), int(y / scale), int(bw / scale), int(bh / scale)),
                    confidence=f.confidence,
                    pose_yaw=f.pose_yaw,
                    pose_pitch=f.pose_pitch,
                    pose_roll=f.pose_roll,
                    raw_row=row,
                )
            )
        return faces

    def detect(self, image: np.ndarray, *, document_mode: bool = False) -> list[FaceDetection]:
        if not self.production_ready:
            return []

        if self._app is not None:
            faces = self._detect_insightface(image)
            if faces or not document_mode:
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
        if not faces and not document_mode:
            faces = self._detect_yunet_scaled(image)
        if faces:
            return faces
        if not document_mode:
            return []

        collected: list[FaceDetection] = []
        for crop, ox, oy in self._document_face_regions(image):
            if crop.size == 0:
                continue
            for f in self._detect_yunet(crop):
                x, y, bw, bh = f.bbox
                collected.append(
                    FaceDetection(
                        bbox=(x + ox, y + oy, bw, bh),
                        confidence=f.confidence,
                        pose_yaw=f.pose_yaw,
                        pose_pitch=f.pose_pitch,
                        pose_roll=f.pose_roll,
                        raw_row=_offset_yunet_row(f.raw_row, ox, oy),
                    )
                )
        return collected

    def match(self, image_a: np.ndarray, image_b: np.ndarray) -> FaceMatchReport:
        if not self.production_ready:
            return FaceMatchReport(
                score=0.0,
                passed=False,
                backend="unavailable",
                face_detected_a=False,
                face_detected_b=False,
            )

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

        emb_a = fa.embedding
        emb_b = fb.embedding
        backend = "insightface"
        threshold = self.threshold

        if emb_a is None or emb_b is None:
            sface_a = self._sface_embedding(image_a, fa)
            sface_b = self._sface_embedding(image_b, fb)
            if sface_a is None or sface_b is None:
                return FaceMatchReport(
                    score=0.0,
                    passed=False,
                    backend="sface_required",
                    face_detected_a=True,
                    face_detected_b=True,
                )
            emb_a, emb_b = sface_a, sface_b
            backend = "opencv_sface"
            threshold = _SFACE_MATCH_THRESHOLD

        score = float(np.dot(emb_a, emb_b) / ((np.linalg.norm(emb_a) * np.linalg.norm(emb_b)) + 1e-8))
        score = max(0.0, min(1.0, score))
        return FaceMatchReport(
            score=score,
            passed=score >= threshold,
            backend=backend,
            face_detected_a=True,
            face_detected_b=True,
        )


@lru_cache(maxsize=1)
def get_face_analyzer() -> FaceAnalyzer:
    return FaceAnalyzer()
