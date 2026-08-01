"""ComplyCube / CBE-style identity check breakdown (no app-layer imports)."""

from __future__ import annotations

from typing import Any


def _analysis_label(passed: bool | None, outcome: str) -> str:
    if passed is True:
        return "clear"
    if passed is False or outcome == "reject":
        return "attention"
    if outcome == "consider":
        return "attention"
    return "clear" if outcome == "clear" else "attention"


def build_identity_result_breakdown(
    scores: dict[str, Any],
    *,
    outcome: str = "clear",
    face_detected: bool = True,
    previously_enrolled: str = "clear",
    banned_faces: str = "clear",
) -> dict[str, Any]:
    facial = scores.get("facialSimilarityScore")
    if facial is None and scores.get("face_match_score") is not None:
        facial = int(round(float(scores["face_match_score"]) * 100))
    liveness = scores.get("livenessCheckScore")
    if liveness is None and scores.get("liveness_score") is not None:
        liveness = int(round(float(scores["liveness_score"]) * 100))
    fraud = scores.get("fraudRiskScore")

    face_ok = bool(scores.get("face_match_passed"))
    live_ok = bool(scores.get("liveness_passed"))

    return {
        "outcome": outcome,
        "breakdown": {
            "faceAnalysis": {
                "facialSimilarity": _analysis_label(face_ok, outcome),
                "previouslyEnrolledFace": previously_enrolled,
                "bannedFacesAnalysis": banned_faces,
                "breakdown": {
                    "facialSimilarityScore": int(facial) if facial is not None else 0,
                    "fraudRiskScore": int(fraud) if fraud is not None else None,
                },
            },
            "authenticityAnalysis": {
                "spoofedImageAnalysis": _analysis_label(live_ok, outcome),
                "livenessCheck": _analysis_label(live_ok, outcome),
                "breakdown": {
                    "livenessCheckScore": int(liveness) if liveness is not None else 0,
                },
            },
            "integrityAnalysis": {
                "faceDetection": "clear" if face_detected else "attention",
            },
        },
    }
