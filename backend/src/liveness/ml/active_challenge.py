"""Active liveness challenge validation (blink / smile / head turn).

Used when passive MiniFAS confidence is weak — frontend can prompt the user
and send challenge evidence in check options.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from liveness.ml.face_mesh import FaceMeshReport

CHALLENGE_TYPES = ("blink", "smile", "turn_left", "turn_right", "look_up")


@dataclass
class ChallengeResult:
    required: bool
    challenge: str | None
    passed: bool | None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "challenge": self.challenge,
            "passed": self.passed,
            "reason": self.reason,
            "details": self.details,
        }


def needs_active_challenge(*, liveness_score: float, liveness_threshold: float, liveness_backend: str) -> bool:
    """Recommend active challenge when passive score is borderline-live or model missing."""
    if liveness_backend == "unavailable":
        return True
    score = float(liveness_score)
    thr = float(liveness_threshold)
    # Live but weak confidence band just above threshold
    return thr <= score < thr + 0.12


def pick_challenge(seed: str | None = None) -> str:
    if not seed:
        return "blink"
    idx = sum(ord(c) for c in seed) % len(CHALLENGE_TYPES)
    return CHALLENGE_TYPES[idx]


def evaluate_challenge(
    *,
    challenge: str | None,
    mesh: FaceMeshReport | None,
    pose_yaw: float | None = None,
    pose_pitch: float | None = None,
    frames: list[dict[str, Any]] | None = None,
) -> ChallengeResult:
    """Validate challenge using mesh/pose or multi-frame EAR sequence."""
    if not challenge:
        return ChallengeResult(required=False, challenge=None, passed=None)

    # Multi-frame blink: EAR dips then recovers
    if challenge == "blink" and frames:
        ears = [f.get("ear") for f in frames if f.get("ear") is not None]
        if len(ears) >= 3:
            mn, mx = min(ears), max(ears)
            passed = mn < 0.16 and mx > 0.22 and (mx - mn) > 0.06
            return ChallengeResult(
                required=True,
                challenge=challenge,
                passed=passed,
                reason=None if passed else "blink_not_detected",
                details={"ear_min": mn, "ear_max": mx},
            )

    if mesh is None:
        return ChallengeResult(
            required=True,
            challenge=challenge,
            passed=False,
            reason="missing_mesh",
        )

    if challenge == "blink":
        passed = bool(mesh.blink_likely) or (mesh.ear is not None and mesh.ear < 0.16)
        return ChallengeResult(
            required=True,
            challenge=challenge,
            passed=passed,
            reason=None if passed else "blink_not_detected",
            details={"ear": mesh.ear},
        )

    if challenge == "smile":
        passed = bool(mesh.smiling) or (mesh.mar is not None and mesh.mar >= 0.45)
        return ChallengeResult(
            required=True,
            challenge=challenge,
            passed=passed,
            reason=None if passed else "smile_not_detected",
            details={"mar": mesh.mar},
        )

    yaw = pose_yaw if pose_yaw is not None else mesh.yaw
    pitch = pose_pitch if pose_pitch is not None else mesh.pitch

    if challenge == "turn_left":
        passed = yaw is not None and yaw <= -12
        return ChallengeResult(required=True, challenge=challenge, passed=passed, reason=None if passed else "yaw_left_missing", details={"yaw": yaw})
    if challenge == "turn_right":
        passed = yaw is not None and yaw >= 12
        return ChallengeResult(required=True, challenge=challenge, passed=passed, reason=None if passed else "yaw_right_missing", details={"yaw": yaw})
    if challenge == "look_up":
        passed = pitch is not None and pitch >= 10
        return ChallengeResult(required=True, challenge=challenge, passed=passed, reason=None if passed else "pitch_up_missing", details={"pitch": pitch})

    return ChallengeResult(required=True, challenge=challenge, passed=False, reason="unknown_challenge")
