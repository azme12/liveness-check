"""Passive face liveness — MiniFAS ONNX when available, heuristic fallback otherwise."""

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
    """Detect print / screen presentation attacks."""

    def __init__(self, model_path: Path | None = None) -> None:
        settings = get_settings()
        self.threshold = settings.liveness_threshold
        self.model_path = model_path or settings.models_dir / "liveness" / "minifas_v2.onnx"
        self._session = None
        self._backend = "heuristic"

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
                self._backend = "heuristic"

    def predict(self, image: np.ndarray, face_bbox: tuple[int, int, int, int] | None = None) -> LivenessReport:
        if self._session is not None:
            return self._predict_onnx(image, face_bbox)
        return self._predict_heuristic(image, face_bbox)

    def _crop_face(self, image: np.ndarray, bbox: tuple[int, int, int, int] | None, scale: float = 2.7) -> np.ndarray:
        h, w = image.shape[:2]
        if bbox is None:
            # Center crop as fallback
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
        blob = np.transpose(blob, (2, 0, 1))[None, ...]  # NCHW
        input_name = self._session.get_inputs()[0].name
        logits = self._session.run(None, {input_name: blob})[0][0]
        # Softmax over [live, print, replay] or [spoof, live]
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()
        if len(probs) == 3:
            live_score = float(probs[0])
        else:
            live_score = float(probs[-1])
        label = "live" if live_score >= self.threshold else "spoof"
        return LivenessReport(
            label=label,
            score=live_score,
            backend=self._backend,
            details={"probs": probs.tolist()},
        )

    def _predict_heuristic(self, image: np.ndarray, face_bbox: tuple[int, int, int, int] | None) -> LivenessReport:
        """Lightweight screen/print cues — not production-grade anti-spoofing."""
        crop = self._crop_face(image, face_bbox, scale=1.8)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop

        # Frequency energy — screens often show moiré / periodic patterns
        f = np.fft.fft2(gray.astype(np.float32))
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)
        h, w = magnitude.shape
        cy, cx = h // 2, w // 2
        # High-frequency ring energy
        y, x = np.ogrid[:h, :w]
        mask = ((y - cy) ** 2 + (x - cx) ** 2) > (min(h, w) * 0.15) ** 2
        hf_ratio = float(magnitude[mask].mean() / (magnitude.mean() + 1e-6))

        # Color variance — prints can look flatter
        if crop.ndim == 3:
            color_std = float(np.std(crop.astype(np.float32)))
        else:
            color_std = float(np.std(gray.astype(np.float32)))

        # Heuristic score in [0, 1]
        score = float(np.clip(0.35 + 0.25 * min(hf_ratio / 3.0, 1.0) + 0.25 * min(color_std / 60.0, 1.0), 0, 1))
        label = "live" if score >= self.threshold else "spoof"
        return LivenessReport(
            label=label,
            score=score,
            backend="heuristic",
            details={"hf_ratio": hf_ratio, "color_std": color_std},
        )
