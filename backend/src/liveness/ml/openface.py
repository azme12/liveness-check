"""OpenFace integration — landmarks, head pose, and AU signals for active liveness.

When LIVENESS_OPENFACE_BIN points to FaceLandmarkImg / FeatureExtraction, we run
the OpenFace CLI and parse CSV output. Otherwise a lightweight OpenCV fallback
estimates pose quality from the face bounding box (works without building OpenFace).
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
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


class OpenFaceAnalyzer:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.openface_enabled
        self.bin = settings.openface_bin
        self.max_yaw = settings.openface_max_yaw
        self.max_pitch = settings.openface_max_pitch
        self.min_certainty = settings.openface_min_certainty

    @property
    def backend(self) -> str:
        if self.enabled and self.bin and Path(self.bin).exists():
            return "openface_cli"
        return "opencv_pose_fallback"

    def analyze(self, image: np.ndarray, face_bbox: tuple[int, int, int, int] | None = None) -> ActiveLivenessReport:
        if self.enabled and self.bin and Path(self.bin).exists():
            try:
                return self._analyze_openface(image)
            except Exception as exc:
                return self._analyze_opencv(image, face_bbox, error=str(exc))
        return self._analyze_opencv(image, face_bbox)

    def _analyze_openface(self, image: np.ndarray) -> ActiveLivenessReport:
        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "frame.jpg"
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            cv2.imwrite(str(img_path), image)

            cmd = [
                str(self.bin),
                "-f",
                str(img_path),
                "-out_dir",
                str(out_dir),
                "-pose",
                "-aus",
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)

            csv_files = list(out_dir.glob("*.csv"))
            if not csv_files:
                raise RuntimeError("OpenFace produced no CSV output")

            row = self._parse_csv_row(csv_files[0])
            yaw = row.get("pose_Ry")
            pitch = row.get("pose_Rx")
            roll = row.get("pose_Rz")
            certainty = row.get("confidence")
            au45 = row.get("AU45_r") or row.get("AU45_c")
            blink = float(au45) > 0.2 if au45 is not None else None

            passed = True
            if yaw is not None and abs(yaw) > self.max_yaw:
                passed = False
            if pitch is not None and abs(pitch) > self.max_pitch:
                passed = False
            if certainty is not None and certainty < self.min_certainty:
                passed = False

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

    def _analyze_opencv(
        self,
        image: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None,
        *,
        error: str | None = None,
    ) -> ActiveLivenessReport:
        """Estimate frontal pose from face centering when OpenFace is unavailable."""
        h, w = image.shape[:2]
        if face_bbox is None:
            side = int(min(h, w) * 0.5)
            x = (w - side) // 2
            y = (h - side) // 2
            face_bbox = (x, y, side, side)

        x, y, bw, bh = face_bbox
        cx = x + bw / 2
        cy = y + bh / 2
        # Normalized offset from image center → rough yaw/pitch proxy
        yaw_proxy = ((cx - w / 2) / max(w / 2, 1)) * 35.0
        pitch_proxy = ((cy - h / 2) / max(h / 2, 1)) * 25.0
        size_ratio = (bw * bh) / max(w * h, 1)
        certainty = float(np.clip(size_ratio * 8.0, 0.2, 0.95))

        passed = (
            abs(yaw_proxy) <= self.max_yaw
            and abs(pitch_proxy) <= self.max_pitch
            and certainty >= self.min_certainty
            and size_ratio >= 0.04
        )

        details = {"size_ratio": size_ratio}
        if error:
            details["openface_error"] = error

        return ActiveLivenessReport(
            passed=passed,
            backend="opencv_pose_fallback",
            head_pose_yaw=yaw_proxy,
            head_pose_pitch=pitch_proxy,
            head_pose_roll=0.0,
            blink_detected=None,
            detection_certainty=certainty,
            details=details,
        )

    @staticmethod
    def detect_openface_install() -> str | None:
        """Try common locations for OpenFace binaries on this machine."""
        settings = get_settings()
        if settings.openface_bin and Path(settings.openface_bin).exists():
            return str(settings.openface_bin)

        candidates = [
            Path("/home/admn/Documents/mine/OpenFace-master (2)/OpenFace-master/build/bin/FaceLandmarkImg"),
            Path("/home/admn/Documents/mine/OpenFace-master (2)/OpenFace-master/build/bin/FeatureExtraction"),
            shutil.which("FaceLandmarkImg") or "",
            shutil.which("FeatureExtraction") or "",
        ]
        for path in candidates:
            if path and Path(path).exists():
                return str(path)
        return None
