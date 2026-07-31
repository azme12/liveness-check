"""OpenFace integration — landmarks, head pose, and AU signals for active liveness.

When FaceLandmarkImg is available we parse CSV pose columns (radians → degrees).
Otherwise InsightFace pose or a lightweight bbox proxy is used for frontal gating.
"""

from __future__ import annotations

import csv
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from liveness.config import get_settings


@dataclass
class ActiveLivenessReport:
    passed: bool
    backend: str
    head_pose_yaw: float | None = None
    head_pose_pitch: float | None = None
    head_pose_roll: float | None = None
    blink_detected: bool | None = None
    detection_certainty: float | None = None
    details: dict | None = None


@dataclass
class HeadPoseLimits:
    max_yaw: float
    max_pitch: float
    max_roll: float
    min_certainty: float


def evaluate_head_pose(
    *,
    yaw: float | None,
    pitch: float | None,
    roll: float | None,
    certainty: float | None,
    limits: HeadPoseLimits,
) -> bool:
    """Return True when head is frontal enough for KYC selfie capture."""
    if certainty is not None and certainty < limits.min_certainty:
        return False
    if yaw is not None and abs(yaw) > limits.max_yaw:
        return False
    if pitch is not None and abs(pitch) > limits.max_pitch:
        return False
    if roll is not None and abs(roll) > limits.max_roll:
        return False
    return True


class OpenFaceAnalyzer:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.openface_enabled
        self.auto_detect = settings.openface_auto_detect
        self.bin = self._resolve_bin(settings.openface_bin)
        self.limits = HeadPoseLimits(
            max_yaw=settings.openface_max_yaw,
            max_pitch=settings.openface_max_pitch,
            max_roll=settings.openface_max_roll,
            min_certainty=settings.openface_min_certainty,
        )
        self.selfie_limits = HeadPoseLimits(
            max_yaw=settings.selfie_max_yaw,
            max_pitch=settings.selfie_max_pitch,
            max_roll=settings.selfie_max_roll,
            min_certainty=settings.selfie_min_pose_certainty,
        )

    @staticmethod
    def _resolve_bin(configured: Path | None) -> Path | None:
        if configured and Path(configured).exists():
            return Path(configured)
        detected = OpenFaceAnalyzer.detect_openface_install()
        return Path(detected) if detected else None

    @property
    def backend(self) -> str:
        if self._use_cli():
            return "openface_cli"
        return "opencv_pose_fallback"

    def _use_cli(self) -> bool:
        return self.bin is not None and (self.enabled or self.auto_detect)

    def analyze(
        self,
        image: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None = None,
        *,
        insightface_pose: tuple[float, float, float] | None = None,
        limits: HeadPoseLimits | None = None,
    ) -> ActiveLivenessReport:
        pose_limits = limits or self.limits
        if self._use_cli():
            try:
                return self._analyze_openface(image, pose_limits)
            except Exception as exc:
                return self._analyze_fallback(
                    image,
                    face_bbox,
                    pose_limits,
                    insightface_pose=insightface_pose,
                    error=str(exc),
                )
        return self._analyze_fallback(
            image,
            face_bbox,
            pose_limits,
            insightface_pose=insightface_pose,
        )

    def _analyze_openface(self, image: np.ndarray, limits: HeadPoseLimits) -> ActiveLivenessReport:
        assert self.bin is not None
        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "frame.jpg"
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            cv2.imwrite(str(img_path), image)

            cmd = [
                str(self.bin),
                "-wild",
                "-f",
                str(img_path),
                "-out_dir",
                str(out_dir),
                "-pose",
                "-aus",
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=90)

            csv_files = list(out_dir.glob("*.csv"))
            if not csv_files:
                raise RuntimeError("OpenFace produced no CSV output")

            row = self._parse_csv_row(csv_files[0])
            # OpenFace CSV pose_Rx/Ry/Rz are radians (pitch/yaw/roll).
            yaw = self._pose_degrees(row.get("pose_Ry"))
            pitch = self._pose_degrees(row.get("pose_Rx"))
            roll = self._pose_degrees(row.get("pose_Rz"))
            certainty = row.get("confidence")
            au45 = row.get("AU45_r") or row.get("AU45_c")
            blink = float(au45) > 0.2 if au45 is not None else None

            passed = evaluate_head_pose(
                yaw=yaw,
                pitch=pitch,
                roll=roll,
                certainty=certainty,
                limits=limits,
            )

            return ActiveLivenessReport(
                passed=passed,
                backend="openface_cli",
                head_pose_yaw=yaw,
                head_pose_pitch=pitch,
                head_pose_roll=roll,
                blink_detected=blink,
                detection_certainty=certainty,
                details=row,
            )

    @staticmethod
    def _pose_degrees(value: float | None) -> float | None:
        if value is None:
            return None
        # Values > 2π are already degrees (fallback proxies); OpenFace uses radians.
        if abs(value) <= math.pi + 0.01:
            return math.degrees(value)
        return value

    def _parse_csv_row(self, csv_path: Path) -> dict[str, float | None]:
        with csv_path.open(newline="") as f:
            reader = csv.DictReader(f)
            row = next(reader, None)
        if not row:
            return {}
        out: dict[str, float | None] = {}
        for key, val in row.items():
            if val is None or val == "":
                out[key] = None
                continue
            try:
                out[key] = float(val)
            except ValueError:
                out[key] = None
        return out

    def _analyze_fallback(
        self,
        image: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None,
        limits: HeadPoseLimits,
        *,
        insightface_pose: tuple[float, float, float] | None = None,
        error: str | None = None,
    ) -> ActiveLivenessReport:
        """Estimate frontal pose from InsightFace or face centering."""
        if insightface_pose is not None:
            yaw, pitch, roll = insightface_pose
            certainty = 0.85
            passed = evaluate_head_pose(
                yaw=yaw,
                pitch=pitch,
                roll=roll,
                certainty=certainty,
                limits=limits,
            )
            details: dict = {"source": "insightface_pose"}
            if error:
                details["openface_error"] = error
            return ActiveLivenessReport(
                passed=passed,
                backend="insightface_pose",
                head_pose_yaw=yaw,
                head_pose_pitch=pitch,
                head_pose_roll=roll,
                blink_detected=None,
                detection_certainty=certainty,
                details=details,
            )

        h, w = image.shape[:2]
        if face_bbox is None:
            side = int(min(h, w) * 0.5)
            x = (w - side) // 2
            y = (h - side) // 2
            face_bbox = (x, y, side, side)

        x, y, bw, bh = face_bbox
        cx = x + bw / 2
        cy = y + bh / 2
        yaw_proxy = ((cx - w / 2) / max(w / 2, 1)) * 35.0
        pitch_proxy = ((cy - h / 2) / max(h / 2, 1)) * 25.0
        roll_proxy = self._estimate_roll_proxy(image, face_bbox)
        size_ratio = (bw * bh) / max(w * h, 1)
        certainty = float(np.clip(size_ratio * 8.0, 0.2, 0.95))

        passed = evaluate_head_pose(
            yaw=yaw_proxy,
            pitch=pitch_proxy,
            roll=roll_proxy,
            certainty=certainty,
            limits=limits,
        ) and size_ratio >= 0.04

        details = {"size_ratio": size_ratio, "source": "bbox_proxy"}
        if error:
            details["openface_error"] = error

        return ActiveLivenessReport(
            passed=passed,
            backend="opencv_pose_fallback",
            head_pose_yaw=yaw_proxy,
            head_pose_pitch=pitch_proxy,
            head_pose_roll=roll_proxy,
            blink_detected=None,
            detection_certainty=certainty,
            details=details,
        )

    @staticmethod
    def _estimate_roll_proxy(image: np.ndarray, face_bbox: tuple[int, int, int, int]) -> float:
        """Rough roll from eye-line tilt using upper-face edges."""
        x, y, w, h = face_bbox
        H, W = image.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(W, x + w), min(H, y + int(h * 0.55))
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        ys, xs = np.where(edges > 0)
        if len(xs) < 40:
            return 0.0
        coeffs = np.polyfit(xs.astype(np.float64), ys.astype(np.float64), 1)
        angle_rad = math.atan(coeffs[0])
        return math.degrees(angle_rad)

    @staticmethod
    def detect_openface_install() -> str | None:
        """Try common locations for OpenFace binaries on this machine."""
        settings = get_settings()
        if settings.openface_bin and Path(settings.openface_bin).exists():
            return str(settings.openface_bin)

        candidates = [
            Path("/home/admn/Documents/mine/OpenFace-master (2)/OpenFace-master/build/bin/FaceLandmarkImg"),
            Path("/home/admn/Documents/mine/OpenFace-master (2)/OpenFace-master/build/bin/FeatureExtraction"),
            Path.home() / "OpenFace/build/bin/FaceLandmarkImg",
            shutil.which("FaceLandmarkImg") or "",
            shutil.which("FeatureExtraction") or "",
        ]
        for path in candidates:
            if path and Path(path).exists():
                return str(path)
        return None


@lru_cache(maxsize=1)
def get_openface_analyzer() -> OpenFaceAnalyzer:
    return OpenFaceAnalyzer()
