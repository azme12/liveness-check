"""Aggregate fraud / risk score from biometric + device + duplicate signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from liveness.types import CheckOutcome


@dataclass
class FraudAssessment:
    risk_score: float  # 0 = safest, 100 = highest risk
    outcome: CheckOutcome
    factors: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 1),
            "outcome": self.outcome.value,
            "factors": self.factors,
            "flags": self.flags,
        }


def compute_fraud_score(
    *,
    face_match_score: float | None = None,
    face_match_passed: bool | None = None,
    liveness_score: float | None = None,
    liveness_passed: bool | None = None,
    document_quality: float | None = None,
    document_valid: bool | None = None,
    document_authenticity: float | None = None,
    document_authenticity_passed: bool | None = None,
    duplicate_score: float | None = None,
    duplicate_hit: bool = False,
    device_risk: float | None = None,
    velocity_count: int = 0,
    multi_face: bool = False,
    heuristic_liveness: bool = False,
    active_challenge_needed: bool = False,
    active_challenge_passed: bool | None = None,
) -> FraudAssessment:
    """Weighted risk: higher = worse. Maps to CLEAR / CONSIDER / REJECT."""
    flags: list[str] = []
    factors: dict[str, Any] = {}

    if face_match_score is not None:
        face_risk = max(0.0, (1.0 - float(face_match_score)) * 100.0)
        factors["face_match"] = round(100.0 - face_risk, 1)
        if face_match_passed is False:
            flags.append("face_match_failed")
            face_risk = max(face_risk, 70.0)
    else:
        face_risk = 40.0
        factors["face_match"] = None

    if liveness_score is not None:
        live_risk = max(0.0, (1.0 - float(liveness_score)) * 100.0)
        factors["liveness"] = round(100.0 - live_risk, 1)
        if liveness_passed is False:
            flags.append("liveness_failed")
            live_risk = max(live_risk, 75.0)
        if heuristic_liveness:
            flags.append("heuristic_liveness")
            live_risk = min(100.0, live_risk + 15.0)
    else:
        live_risk = 50.0
        factors["liveness"] = None

    if document_quality is not None:
        doc_risk = max(0.0, (1.0 - float(document_quality)) * 100.0)
        factors["document"] = round(100.0 - doc_risk, 1)
        if document_valid is False:
            flags.append("document_invalid")
            doc_risk = max(doc_risk, 60.0)
    else:
        doc_risk = 25.0
        factors["document"] = None
    if document_authenticity is not None:
        authenticity_risk = max(0.0, (1.0 - float(document_authenticity)) * 100.0)
        factors["document_authenticity"] = round(float(document_authenticity) * 100.0, 1)
        # Forensic heuristics are review signals: cap their contribution.
        doc_risk = max(doc_risk, min(authenticity_risk, 65.0))
        if document_authenticity_passed is False:
            flags.append("document_authenticity_review")
    else:
        factors["document_authenticity"] = None

    dup_risk = 0.0
    if duplicate_hit:
        flags.append("duplicate_identity")
        dup_risk = 85.0 if (duplicate_score or 0) >= 0.55 else 55.0
        factors["duplicate"] = round(float(duplicate_score or 0) * 100, 1)
    else:
        factors["duplicate"] = 0

    device = float(device_risk or 0.0)
    factors["device"] = round(max(0.0, 100.0 - device), 1) if device_risk is not None else None
    if device >= 50:
        flags.append("device_risk")
    if velocity_count >= 3:
        flags.append("velocity_abuse")
        device = max(device, 40.0 + min(velocity_count, 10) * 5.0)
    factors["velocity"] = velocity_count

    if multi_face:
        flags.append("multi_face")
        face_risk = max(face_risk, 90.0)

    if active_challenge_needed and active_challenge_passed is not True:
        flags.append("active_challenge_pending")
    if active_challenge_passed is False:
        flags.append("active_challenge_failed")

    risk = (
        0.30 * face_risk
        + 0.30 * live_risk
        + 0.15 * doc_risk
        + 0.15 * dup_risk
        + 0.10 * min(device, 100.0)
    )
    if active_challenge_passed is False:
        risk = max(risk, 70.0)
    if multi_face:
        risk = max(risk, 80.0)
    if duplicate_hit and (duplicate_score or 0) >= 0.70:
        risk = max(risk, 75.0)

    risk = max(0.0, min(100.0, float(risk)))

    hard_reject = (
        multi_face
        or face_match_passed is False
        or (liveness_passed is False and not heuristic_liveness)
        or (duplicate_hit and (duplicate_score or 0) >= 0.75)
        or active_challenge_passed is False
        or document_valid is False
    )

    if hard_reject or risk >= 70:
        outcome = CheckOutcome.REJECT
    elif (
        risk >= 35
        or active_challenge_needed
        or "duplicate_identity" in flags
        or "velocity_abuse" in flags
        or heuristic_liveness
    ):
        outcome = CheckOutcome.CONSIDER
    else:
        outcome = CheckOutcome.CLEAR

    return FraudAssessment(risk_score=risk, outcome=outcome, factors=factors, flags=flags)
