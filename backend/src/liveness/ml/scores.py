"""Normalize verification scores for partner APIs (0–100 scale)."""

from __future__ import annotations

from typing import Any


def score_to_percent(value: float | None) -> int | None:
    """Map a 0..1 similarity/confidence to an integer 0..100."""
    if value is None:
        return None
    clamped = max(0.0, min(1.0, float(value)))
    return int(round(clamped * 100))


def enrich_verification_scores(scores: dict[str, Any]) -> dict[str, Any]:
    """Add CBE-style fields alongside legacy 0..1 scores."""
    face = scores.get("face_match_score")
    live = scores.get("liveness_score")
    facial = score_to_percent(face if isinstance(face, (int, float)) else None)
    liveness = score_to_percent(live if isinstance(live, (int, float)) else None)
    out = dict(scores)
    out["facialSimilarityScore"] = facial
    out["livenessCheckScore"] = liveness
    # Aliases partners often expect
    if facial is not None:
        out["face_match_percent"] = facial
    if liveness is not None:
        out["liveness_percent"] = liveness
    return out
