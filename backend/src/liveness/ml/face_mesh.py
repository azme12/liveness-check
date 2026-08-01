"""Face mesh landmarks — MediaPipe Face Landmarker only."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from liveness.config import get_settings

_LEFT_EYE = [33, 160, 158, 133, 153, 144]
_RIGHT_EYE = [362, 385, 387, 263, 373, 380]


@dataclass
class FaceMeshReport:
    backend: str
    ear: float | None = None
    mar: float | None = None
    eyes_open: bool | None = None
    smiling: bool | None = None
    blink_likely: bool | None = None
    yaw: float | None = None
    pitch: float | None = None
    roll: float | None = None
    landmark_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "ear": self.ear,
            "mar": self.mar,
            "eyes_open": self.eyes_open,
            "smiling": self.smiling,
            "blink_likely": self.blink_likely,
            "yaw": self.yaw,
            "pitch": self.pitch,
            "roll": self.roll,
            "landmark_count": self.landmark_count,
            "details": self.details,
        }


def _ear_from_points(pts: np.ndarray) -> float:
    a = np.linalg.norm(pts[1] - pts[5])
    b = np.linalg.norm(pts[2] - pts[4])
    c = np.linalg.norm(pts[0] - pts[3]) + 1e-6
    return float((a + b) / (2.0 * c))


def _mar_from_points(upper: np.ndarray, lower: np.ndarray, left: np.ndarray, right: np.ndarray) -> float:
    vert = np.linalg.norm(upper - lower)
    horiz = np.linalg.norm(left - right) + 1e-6
    return float(vert / horiz)


def _pose_from_landmarks(landmarks: np.ndarray, image_size: tuple[int, int]) -> tuple[float, float, float]:
    h, w = image_size
    idx = [1, 152, 33, 263, 61, 291]
    if landmarks.shape[0] < max(idx) + 1:
        return 0.0, 0.0, 0.0
    image_points = landmarks[idx].astype(np.float64)
    model_points = np.array(
        [
            (0.0, 0.0, 0.0),
            (0.0, -63.6, -12.5),
            (-43.3, 32.7, -26.0),
            (43.3, 32.7, -26.0),
            (-28.9, -28.9, -24.1),
            (28.9, -28.9, -24.1),
        ],
        dtype=np.float64,
    )
    focal = w
    center = (w / 2.0, h / 2.0)
    camera = np.array([[focal, 0, center[0]], [0, focal, center[1]], [0, 0, 1]], dtype=np.float64)
    dist = np.zeros((4, 1))
    ok, rvec, _ = cv2.solvePnP(model_points, image_points, camera, dist, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return 0.0, 0.0, 0.0
    rmat, _ = cv2.Rodrigues(rvec)
    sy = float(np.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2))
    pitch = float(np.degrees(np.arctan2(-rmat[2, 0], sy)))
    yaw = float(np.degrees(np.arctan2(rmat[1, 0], rmat[0, 0])))
    roll = float(np.degrees(np.arctan2(rmat[2, 1], rmat[2, 2])))
    return yaw, pitch, roll


_PRODUCTION_MESH_BACKENDS = frozenset({"mediapipe_solutions", "mediapipe_tasks"})


class FaceMeshAnalyzer:
    def __init__(self) -> None:
        self._mp_mesh = None
        self._mp_mode: str | None = None
        self._backend = "unavailable"
        settings = get_settings()
        if not settings.mediapipe_enabled:
            return
        try:
            import mediapipe as mp

            if hasattr(mp, "solutions"):
                self._mp_mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                )
                self._mp_mode = "solutions"
                self._backend = "mediapipe_solutions"
            else:
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision

                candidates = (
                    settings.models_dir / "face_landmarker.task",
                    Path(__file__).resolve().parents[3] / "models" / "face_landmarker.task",
                    Path("/app/models/face_landmarker.task"),
                )
                model_path = next((path for path in candidates if path.exists()), None)
                if model_path is None:
                    return
                options = vision.FaceLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_path=str(model_path)),
                    running_mode=vision.RunningMode.IMAGE,
                    num_faces=1,
                    output_face_blendshapes=True,
                )
                self._mp_mesh = vision.FaceLandmarker.create_from_options(options)
                self._mp_mode = "tasks"
                self._backend = "mediapipe_tasks"
        except Exception:
            self._mp_mesh = None
            self._mp_mode = None
            self._backend = "unavailable"

    @property
    def production_ready(self) -> bool:
        return self._backend in _PRODUCTION_MESH_BACKENDS

    def analyze(
        self,
        image: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None = None,
        yunet_row: np.ndarray | None = None,
        *,
        ear_open_threshold: float = 0.20,
        ear_blink_threshold: float = 0.16,
        mar_smile_threshold: float = 0.45,
    ) -> FaceMeshReport:
        del face_bbox, yunet_row
        if self._mp_mesh is None:
            return FaceMeshReport(
                backend="unavailable",
                landmark_count=0,
                details={"error": "mediapipe_required"},
            )
        report = self._analyze_mediapipe(
            image,
            ear_open_threshold=ear_open_threshold,
            ear_blink_threshold=ear_blink_threshold,
            mar_smile_threshold=mar_smile_threshold,
        )
        if report.landmark_count > 0:
            return report
        return FaceMeshReport(backend=self._backend, landmark_count=0)

    def _analyze_mediapipe(
        self,
        image: np.ndarray,
        *,
        ear_open_threshold: float,
        ear_blink_threshold: float,
        mar_smile_threshold: float,
    ) -> FaceMeshReport:
        assert self._mp_mesh is not None
        h, w = image.shape[:2]
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if self._mp_mode == "tasks":
            import mediapipe as mp

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._mp_mesh.detect(mp_image)
            if not result.face_landmarks:
                return FaceMeshReport(backend=self._backend, landmark_count=0)
            lm = result.face_landmarks[0]
        else:
            result = self._mp_mesh.process(rgb)
            if not result.multi_face_landmarks:
                return FaceMeshReport(backend=self._backend, landmark_count=0)
            lm = result.multi_face_landmarks[0].landmark
        pts = np.array([(p.x * w, p.y * h) for p in lm], dtype=np.float64)

        left = pts[_LEFT_EYE]
        right = pts[_RIGHT_EYE]
        ear = (_ear_from_points(left) + _ear_from_points(right)) / 2.0
        mar = _mar_from_points(pts[13], pts[14], pts[78], pts[308])
        yaw, pitch, roll = _pose_from_landmarks(pts, (h, w))

        return FaceMeshReport(
            backend=self._backend,
            ear=ear,
            mar=mar,
            eyes_open=ear >= ear_open_threshold,
            smiling=mar >= mar_smile_threshold,
            blink_likely=ear < ear_blink_threshold,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            landmark_count=len(pts),
            details={"ear_left": _ear_from_points(left), "ear_right": _ear_from_points(right)},
        )


@lru_cache
def get_face_mesh_analyzer() -> FaceMeshAnalyzer:
    return FaceMeshAnalyzer()
