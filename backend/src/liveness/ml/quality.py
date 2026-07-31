"""Image quality gates (OpenCV heuristics — no heavy ML required)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class QualityReport:
    score: float
    blur_score: float
    brightness: float
    warnings: list[str]

    @property
    def passed(self) -> bool:
        return self.score >= 0.35 and not any(
            w.startswith("reject:") for w in self.warnings
        )


def _to_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    return image


def assess_quality(image: np.ndarray) -> QualityReport:
    """Score blur, brightness, and size for capture rejection."""
    bgr = _to_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    warnings: list[str] = []

    h, w = gray.shape[:2]
    if min(h, w) < 200:
        warnings.append("reject:image_too_small")

    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    # Typical sharp photos > 100; soft phone shots ~30–80
    blur_norm = min(1.0, blur / 150.0)
    if blur_norm < 0.25:
        warnings.append("blurry")

    brightness = float(np.mean(gray)) / 255.0
    if brightness < 0.15:
        warnings.append("too_dark")
    elif brightness > 0.92:
        warnings.append("too_bright")

    # Glare: high saturation of near-white pixels
    glare_ratio = float(np.mean(gray > 245))
    if glare_ratio > 0.12:
        warnings.append("glare")

    score = float(np.clip(0.55 * blur_norm + 0.35 * (1.0 - abs(brightness - 0.5) * 2) + 0.1, 0, 1))
    if glare_ratio > 0.12:
        score *= 0.85

    return QualityReport(score=score, blur_score=blur_norm, brightness=brightness, warnings=warnings)


def decode_image(data: bytes, *, max_side: int | None = None) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")
    if max_side and max(img.shape[:2]) > max_side:
        h, w = img.shape[:2]
        scale = max_side / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img
