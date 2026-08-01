"""Extra replay / presentation-attack cues (moire, bezel, paper edges).

These are soft signals that boost fraud risk — MiniFAS remains the primary PAD.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


@dataclass
class ReplaySignals:
    moire_score: float = 0.0
    bezel_score: float = 0.0
    paper_edge_score: float = 0.0
    reflection_score: float = 0.0
    risk: float = 0.0  # 0..100
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "moire_score": round(self.moire_score, 3),
            "bezel_score": round(self.bezel_score, 3),
            "paper_edge_score": round(self.paper_edge_score, 3),
            "reflection_score": round(self.reflection_score, 3),
            "risk": round(self.risk, 1),
            "flags": self.flags,
        }


def analyze_replay_cues(
    image: np.ndarray,
    face_bbox: tuple[int, int, int, int] | None = None,
) -> ReplaySignals:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    flags: list[str] = []

    # --- Moire / screen refresh: high-frequency periodic energy ---
    f = np.fft.fft2(gray.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    ring = ((yy - cy) ** 2 + (xx - cx) ** 2 > (min(h, w) * 0.12) ** 2) & (
        (yy - cy) ** 2 + (xx - cx) ** 2 < (min(h, w) * 0.45) ** 2
    )
    moire = float(mag[ring].mean() / (mag.mean() + 1e-6))
    moire_score = float(np.clip((moire - 1.2) / 2.5, 0, 1))
    if moire_score > 0.55:
        flags.append("moire_pattern")

    # --- Phone bezel: dark rectangular border around frame ---
    border = 8
    edges = [
        gray[:border, :],
        gray[-border:, :],
        gray[:, :border],
        gray[:, -border:],
    ]
    border_mean = float(np.mean([np.mean(e) for e in edges]))
    center_mean = float(np.mean(gray[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]))
    bezel_score = 0.0
    if center_mean > 40:
        bezel_score = float(np.clip((center_mean - border_mean) / 80.0, 0, 1))
    if bezel_score > 0.55 and border_mean < 45:
        flags.append("device_bezel")

    # --- Printed paper edges: strong straight contours near face ---
    paper_edge_score = 0.0
    if face_bbox is not None:
        x, y, bw, bh = face_bbox
        pad = int(max(bw, bh) * 0.35)
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
        region = gray[y1:y2, x1:x2]
        if region.size:
            edges_c = cv2.Canny(region, 80, 180)
            lines = cv2.HoughLinesP(edges_c, 1, np.pi / 180, threshold=40, minLineLength=int(min(bw, bh) * 0.4), maxLineGap=8)
            if lines is not None and len(lines) >= 4:
                paper_edge_score = float(np.clip(len(lines) / 12.0, 0, 1))
                if paper_edge_score > 0.5:
                    flags.append("paper_edges")

    # --- Specular reflection blobs (screen glare) ---
    bright = float(np.mean(gray > 245))
    reflection_score = float(np.clip(bright / 0.12, 0, 1))
    if reflection_score > 0.6:
        flags.append("screen_reflection")

    risk = float(
        np.clip(
            100.0
            * (0.35 * moire_score + 0.25 * bezel_score + 0.25 * paper_edge_score + 0.15 * reflection_score),
            0,
            100,
        )
    )

    return ReplaySignals(
        moire_score=moire_score,
        bezel_score=bezel_score,
        paper_edge_score=paper_edge_score,
        reflection_score=reflection_score,
        risk=risk,
        flags=flags,
    )
