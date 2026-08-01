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
    contrast: float
    glare_ratio: float
    shadow_ratio: float
    rotation_degrees: float
    perspective_score: float
    compression_score: float
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
    """Score capture quality before OCR/authenticity processing."""
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

    contrast = float(np.std(gray)) / 64.0
    contrast_norm = float(np.clip(contrast, 0, 1))
    if contrast_norm < 0.25:
        warnings.append("low_contrast")

    # Strong dark regions often indicate uneven illumination/shadow.
    shadow_ratio = float(np.mean(gray < 35))
    if shadow_ratio > 0.25:
        warnings.append("heavy_shadow")

    # Estimate dominant document rotation from long straight edges.
    edges = cv2.Canny(gray, 60, 180)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(30, min(h, w) // 8),
        minLineLength=max(30, min(h, w) // 3),
        maxLineGap=12,
    )
    angles: list[float] = []
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            normalized = ((angle + 45) % 90) - 45
            angles.append(normalized)
    rotation = float(np.median(angles)) if angles else 0.0
    if abs(rotation) > 8:
        warnings.append("document_rotated")

    # Largest quadrilateral coverage is a lightweight perspective/cropping proxy.
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    perspective = 0.0
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            perspective = max(perspective, float(cv2.contourArea(approx) / max(h * w, 1)))
    if 0 < perspective < 0.35:
        warnings.append("perspective_distortion")

    # Block-boundary discontinuities indicate aggressive JPEG compression.
    vertical = float(np.mean(np.abs(np.diff(gray.astype(np.float32), axis=1))[:, 7::8])) if w > 16 else 0.0
    horizontal = float(np.mean(np.abs(np.diff(gray.astype(np.float32), axis=0))[7::8, :])) if h > 16 else 0.0
    compression = float(np.clip(1.0 - (vertical + horizontal) / 80.0, 0, 1))
    if compression < 0.35:
        warnings.append("compression_artifacts")

    brightness_score = 1.0 - abs(brightness - 0.5) * 2
    score = float(
        np.clip(
            0.38 * blur_norm
            + 0.20 * brightness_score
            + 0.15 * contrast_norm
            + 0.10 * (1.0 - min(glare_ratio / 0.12, 1.0))
            + 0.07 * (1.0 - min(shadow_ratio / 0.25, 1.0))
            + 0.05 * (1.0 - min(abs(rotation) / 15.0, 1.0))
            + 0.05 * compression,
            0,
            1,
        )
    )
    if glare_ratio > 0.12:
        score *= 0.85

    return QualityReport(
        score=score,
        blur_score=blur_norm,
        brightness=brightness,
        contrast=contrast_norm,
        glare_ratio=glare_ratio,
        shadow_ratio=shadow_ratio,
        rotation_degrees=rotation,
        perspective_score=perspective,
        compression_score=compression,
        warnings=warnings,
    )


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
