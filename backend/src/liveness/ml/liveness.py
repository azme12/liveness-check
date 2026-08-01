"""Passive face liveness — MiniFAS ONNX only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from liveness.config import get_settings


@dataclass
class LivenessReport:
    label: str  # live | spoof | unknown
    score: float
    backend: str
    details: dict


class LivenessDetector:
    """Detect print / screen presentation attacks (MiniFASNet V2)."""

    def __init__(self, model_path: Path | None = None) -> None:
        settings = get_settings()
        self.threshold = settings.liveness_threshold
        self.model_path = model_path or settings.models_dir / "liveness" / "minifas_v2.onnx"
        self._session = None
        self._backend = "unavailable"

        if self.model_path.exists():
            try:
                import onnxruntime as ort

                self._session = ort.InferenceSession(
                    str(self.model_path),
                    providers=["CPUExecutionProvider"],
                )
                self._backend = "minifas_onnx"
            except Exception:
                self._session = None
                self._backend = "unavailable"

    def predict(self, image: np.ndarray, face_bbox: tuple[int, int, int, int] | None = None) -> LivenessReport:
        if self._session is None:
            return LivenessReport(
                label="unknown",
                score=0.0,
                backend="unavailable",
                details={"error": "minifas_model_missing"},
            )
        return self._predict_onnx(image, face_bbox)

    def _crop_face(self, image: np.ndarray, bbox: tuple[int, int, int, int] | None, scale: float = 2.7) -> np.ndarray:
        h, w = image.shape[:2]
        if bbox is None:
            side = min(h, w)
            x1 = (w - side) // 2
            y1 = (h - side) // 2
            crop = image[y1 : y1 + side, x1 : x1 + side]
        else:
            x, y, bw, bh = bbox
            cx, cy = x + bw / 2, y + bh / 2
            side = max(bw, bh) * scale
            x1 = int(max(0, cx - side / 2))
            y1 = int(max(0, cy - side / 2))
            x2 = int(min(w, cx + side / 2))
            y2 = int(min(h, cy + side / 2))
            crop = image[y1:y2, x1:x2]
        return crop

    def _predict_onnx(self, image: np.ndarray, face_bbox: tuple[int, int, int, int] | None) -> LivenessReport:
        assert self._session is not None
        crop = self._crop_face(image, face_bbox)
        resized = cv2.resize(crop, (80, 80))
        blob = resized.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[None, ...]
        input_name = self._session.get_inputs()[0].name
        logits = self._session.run(None, {input_name: blob})[0][0]
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()
        if len(probs) == 3:
            live_score = float(probs[1])
            spoof_score = float(probs[0] + probs[2])
            details = {
                "probs": probs.tolist(),
                "print_score": float(probs[0]),
                "live_score": live_score,
                "replay_score": float(probs[2]),
                "spoof_score": spoof_score,
            }
        else:
            live_score = float(probs[-1])
            details = {"probs": probs.tolist()}
        label = "live" if live_score >= self.threshold else "spoof"
        return LivenessReport(
            label=label,
            score=live_score,
            backend=self._backend,
            details=details,
        )
