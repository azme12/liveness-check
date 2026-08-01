"""Explainable document authenticity signals.

These forensic cues identify suspicious captures for review. They are not a
substitute for country-specific security-feature models or certified KYC data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


@dataclass
class DocumentAuthenticityReport:
    score: float
    passed: bool
    ela_score: float
    block_artifact_score: float
    copy_move_score: float
    edge_manipulation_score: float
    qr_data: str | None = None
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "passed": self.passed,
            "ela_score": round(self.ela_score, 4),
            "block_artifact_score": round(self.block_artifact_score, 4),
            "copy_move_score": round(self.copy_move_score, 4),
            "edge_manipulation_score": round(self.edge_manipulation_score, 4),
            "qr_detected": bool(self.qr_data),
            "qr_data": self.qr_data,
            "warnings": self.warnings,
            "details": self.details,
        }


def _error_level_score(image: np.ndarray) -> tuple[float, float]:
    """Return localized ELA anomaly and mean recompression error."""
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        return 0.0, 0.0
    recompressed = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    diff = cv2.absdiff(image, recompressed)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    mean_error = float(np.mean(gray)) / 255.0
    # Localized editing tends to produce a small region far above global error.
    p99 = float(np.percentile(gray, 99)) / 255.0
    anomaly = float(np.clip((p99 - mean_error * 2.5) / 0.30, 0, 1))
    return anomaly, mean_error


def _block_artifact_score(gray: np.ndarray) -> float:
    """Estimate abnormal 8x8 JPEG boundary discontinuity."""
    h, w = gray.shape
    g = gray.astype(np.float32)
    if h < 24 or w < 24:
        return 0.0
    v_all = np.abs(np.diff(g, axis=1))
    h_all = np.abs(np.diff(g, axis=0))
    v_boundary = float(np.mean(v_all[:, 7::8]))
    h_boundary = float(np.mean(h_all[7::8, :]))
    v_normal = float(np.mean(v_all)) + 1e-6
    h_normal = float(np.mean(h_all)) + 1e-6
    ratio = ((v_boundary / v_normal) + (h_boundary / h_normal)) / 2.0
    return float(np.clip((ratio - 1.15) / 1.2, 0, 1))


def _copy_move_score(gray: np.ndarray) -> tuple[float, int]:
    """Detect repeated local features separated in the image."""
    orb = cv2.ORB_create(nfeatures=700)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    if descriptors is None or len(keypoints) < 20:
        return 0.0, 0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    pairs = matcher.knnMatch(descriptors, descriptors, k=3)
    suspicious = 0
    for candidates in pairs:
        source = candidates[0].queryIdx if candidates else -1
        for match in candidates:
            if match.trainIdx == source:
                continue
            p1 = np.asarray(keypoints[match.queryIdx].pt)
            p2 = np.asarray(keypoints[match.trainIdx].pt)
            if match.distance < 28 and np.linalg.norm(p1 - p2) > 45:
                suspicious += 1
                break
    ratio = suspicious / max(len(keypoints), 1)
    return float(np.clip((ratio - 0.02) / 0.12, 0, 1)), suspicious


def _edge_manipulation_score(gray: np.ndarray) -> float:
    """Look for small, unusually edge-dense edited regions."""
    edges = cv2.Canny(gray, 80, 180)
    h, w = gray.shape
    grid_scores: list[float] = []
    for y in range(0, h, max(32, h // 8)):
        for x in range(0, w, max(32, w // 8)):
            tile = edges[y : y + max(32, h // 8), x : x + max(32, w // 8)]
            if tile.size:
                grid_scores.append(float(np.mean(tile > 0)))
    if len(grid_scores) < 4:
        return 0.0
    median = float(np.median(grid_scores)) + 1e-6
    peak = float(np.percentile(grid_scores, 95))
    return float(np.clip((peak / median - 3.0) / 6.0, 0, 1))


def _decode_qr(image: np.ndarray) -> str | None:
    try:
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        return data.strip()[:2000] if data else None
    except cv2.error:
        return None


def assess_document_authenticity(image: np.ndarray) -> DocumentAuthenticityReport:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    ela, mean_error = _error_level_score(image)
    block = _block_artifact_score(gray)
    copy_move, duplicate_features = _copy_move_score(gray)
    edge = _edge_manipulation_score(gray)
    qr_data = _decode_qr(image)

    warnings: list[str] = []
    if ela > 0.70:
        warnings.append("possible_local_editing")
    if block > 0.70:
        warnings.append("possible_double_compression")
    if copy_move > 0.65:
        warnings.append("possible_copy_move_forgery")
    if edge > 0.75:
        warnings.append("possible_edge_manipulation")

    tamper_risk = 0.35 * ela + 0.25 * block + 0.25 * copy_move + 0.15 * edge
    score = float(np.clip(1.0 - tamper_risk, 0, 1))
    # Forensic heuristics produce review signals, not automatic hard rejection.
    passed = score >= 0.55 and len(warnings) < 2
    return DocumentAuthenticityReport(
        score=score,
        passed=passed,
        ela_score=ela,
        block_artifact_score=block,
        copy_move_score=copy_move,
        edge_manipulation_score=edge,
        qr_data=qr_data,
        warnings=warnings,
        details={
            "mean_recompression_error": mean_error,
            "duplicate_features": duplicate_features,
            "policy": "review_signal_only",
        },
    )
