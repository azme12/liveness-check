"""Check runners — document + identity pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from liveness.config import Settings, get_settings
from liveness.ml import DocumentOcr, LivenessDetector, assess_quality
from liveness.ml.active_challenge import (
    ChallengeResult,
    evaluate_challenge,
    needs_active_challenge,
    pick_challenge,
)
from liveness.ml.document_authenticity import assess_document_authenticity
from liveness.ml.document_types import resolve_document_type
from liveness.ml.face import get_face_analyzer
from liveness.ml.face_mesh import get_face_mesh_analyzer
from liveness.ml.fraud import compute_fraud_score
from liveness.ml.openface import get_openface_analyzer
from liveness.ml.partner_format import build_identity_result_breakdown
from liveness.ml.replay import analyze_replay_cues
from liveness.ml.scores import enrich_verification_scores
from liveness.types import (
    BiometricResult,
    CheckOutcome,
    CheckResult,
    CheckType,
    DocumentResult,
)


@dataclass
class CheckContext:
    document_image: np.ndarray | None = None
    live_photo_image: np.ndarray | None = None
    client_name: str | None = None
    options: dict[str, Any] | None = None


def _document_type_hint(ctx: CheckContext) -> str | None:
    opts = ctx.options or {}
    return opts.get("document_type") or opts.get("doc_type")


def _apply_document_type(doc: DocumentResult | None, ctx: CheckContext, ocr_type: str | None) -> DocumentResult | None:
    if doc is None:
        return None
    resolved = resolve_document_type(hint=_document_type_hint(ctx), ocr_detected=ocr_type or doc.document_type)
    if resolved:
        doc.document_type = resolved
    return doc


def _identity_scores(
    *,
    document: DocumentResult | None,
    biometric: BiometricResult | None,
    match_passed: bool | None = None,
) -> dict[str, Any]:
    doc = document
    bio = biometric
    raw = {
        "document_type": doc.document_type if doc else None,
        "document_quality": doc.quality_score if doc else None,
        "document_valid": doc.valid if doc else None,
        "liveness_score": bio.liveness_score if bio else None,
        "liveness_passed": bio.liveness == "live" if bio else None,
        "liveness_label": bio.liveness if bio else None,
        "face_match_score": bio.face_match_score if bio else None,
        "face_match_passed": bio.face_match_passed if bio else match_passed,
        "face_detected": bio.face_detected if bio else None,
    }
    return enrich_verification_scores(raw)


class CheckEngine:
    """Orchestrates async check types (run synchronously in worker for MVP)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.ocr = DocumentOcr()
        self.liveness = LivenessDetector()
        self.faces = get_face_analyzer()
        self.openface = get_openface_analyzer()
        self.mesh = get_face_mesh_analyzer()

    def run(self, check_type: CheckType, ctx: CheckContext) -> CheckResult:
        if check_type == CheckType.DOCUMENT:
            return self.run_document(ctx)
        if check_type == CheckType.IDENTITY:
            return self.run_identity(ctx)
        if check_type == CheckType.ENHANCED_IDENTITY:
            return self.run_enhanced_identity(ctx)
        if check_type == CheckType.FACE_AUTHENTICATION:
            return self.run_face_authentication(ctx)
        if check_type == CheckType.STANDARD_SCREENING:
            return self.run_screening(ctx)
        return CheckResult(
            outcome=CheckOutcome.CONSIDER,
            explainability=[f"check_type_not_implemented:{check_type}"],
        )

    def run_document(self, ctx: CheckContext) -> CheckResult:
        if ctx.document_image is None:
            return CheckResult(
                outcome=CheckOutcome.REJECT,
                explainability=["missing_document_image"],
            )

        quality = assess_quality(ctx.document_image)
        authenticity = assess_document_authenticity(ctx.document_image)
        ocr = self.ocr.extract(ctx.document_image)
        warnings = list(quality.warnings) + list(ocr.warnings) + list(authenticity.warnings)

        hard_fail = any(w.startswith("reject:") for w in warnings)
        mrz_ok = ocr.mrz_valid is not False
        valid = quality.passed and not hard_fail and mrz_ok

        if hard_fail or not quality.passed:
            outcome = CheckOutcome.REJECT
        elif ocr.mrz_valid is False or not authenticity.passed:
            outcome = CheckOutcome.CONSIDER
        elif ocr.fields.full_name or ocr.mrz_valid:
            outcome = CheckOutcome.CLEAR
        else:
            outcome = CheckOutcome.CONSIDER
            warnings.append("limited_field_extraction")

        doc_type = resolve_document_type(hint=_document_type_hint(ctx), ocr_detected=ocr.document_type)

        return CheckResult(
            outcome=outcome,
            document=DocumentResult(
                valid=valid,
                mrz_valid=ocr.mrz_valid,
                quality_score=quality.score,
                authenticity_score=authenticity.score,
                authenticity_passed=authenticity.passed,
                document_type=doc_type,
                fields=ocr.fields,
                warnings=warnings,
            ),
            signals={
                "scores": enrich_verification_scores(
                    {
                        "document_type": doc_type,
                        "document_quality": quality.score,
                        "document_authenticity": authenticity.score,
                        "document_valid": valid,
                        "liveness_score": None,
                        "face_match_score": None,
                    }
                ),
                "document_quality": {
                    "blur": quality.blur_score,
                    "brightness": quality.brightness,
                    "contrast": quality.contrast,
                    "glare_ratio": quality.glare_ratio,
                    "shadow_ratio": quality.shadow_ratio,
                    "rotation_degrees": quality.rotation_degrees,
                    "perspective_score": quality.perspective_score,
                    "compression_score": quality.compression_score,
                },
                "document_authenticity": authenticity.to_dict(),
            },
            explainability=warnings,
            model_versions={
                "ocr": ocr.backend,
                "quality": "opencv_quality_v2",
                "document_authenticity": "opencv_forensics_v1",
            },
        )

    def run_identity(self, ctx: CheckContext) -> CheckResult:
        opts = ctx.options or {}
        doc_result = self.run_document(ctx)
        doc_result.document = _apply_document_type(
            doc_result.document, ctx, doc_result.document.document_type if doc_result.document else None
        )
        if ctx.live_photo_image is None:
            return CheckResult(
                outcome=CheckOutcome.REJECT,
                document=doc_result.document,
                explainability=["missing_live_photo"],
            )

        faces = self.faces.detect(ctx.live_photo_image)
        multi_face = len(faces) > 1
        bbox = faces[0].bbox if faces else None
        yunet_row = faces[0].raw_row if faces else None

        live = self.liveness.predict(ctx.live_photo_image, bbox)
        active = self.openface.analyze(ctx.live_photo_image, bbox)
        mesh = self.mesh.analyze(ctx.live_photo_image, bbox, yunet_row)
        replay = analyze_replay_cues(ctx.live_photo_image, bbox)

        match = None
        if ctx.document_image is not None:
            match = self.faces.match(ctx.document_image, ctx.live_photo_image)

        # Prefer mesh pose when OpenFace/InsightFace weak
        if mesh.yaw is not None and active.head_pose_yaw is None:
            active.head_pose_yaw = mesh.yaw
            active.head_pose_pitch = mesh.pitch
            active.head_pose_roll = mesh.roll

        duplicate = opts.get("duplicate_match") or {}
        duplicate_hit = bool(duplicate.get("passed"))
        duplicate_score = float(duplicate["score"]) if duplicate.get("score") is not None else None

        device = opts.get("device") or {}
        velocity = opts.get("device_velocity") or {}
        device_risk = float(device.get("risk") or velocity.get("risk") or 0.0)
        velocity_count = int(velocity.get("distinct_clients") or 0)

        challenge_name = opts.get("active_challenge") or (
            pick_challenge(opts.get("session_id") or opts.get("client_id"))
            if needs_active_challenge(
                liveness_score=live.score,
                liveness_threshold=self.settings.liveness_threshold,
                liveness_backend=live.backend,
            )
            else None
        )
        challenge_required = bool(challenge_name) and needs_active_challenge(
            liveness_score=live.score,
            liveness_threshold=self.settings.liveness_threshold,
            liveness_backend=live.backend,
        )
        challenge = evaluate_challenge(
            challenge=challenge_name if challenge_required or opts.get("active_challenge") else None,
            mesh=mesh,
            pose_yaw=active.head_pose_yaw,
            pose_pitch=active.head_pose_pitch,
            frames=opts.get("challenge_frames"),
        )
        # Only require challenge when passive is weak; single still photo cannot prove blink
        if challenge_required and opts.get("active_challenge") is None and opts.get("challenge_frames") is None:
            challenge = ChallengeResult(
                required=True,
                challenge=challenge_name,
                passed=None,
                reason="challenge_recommended",
                details={"hint": "Prompt user to blink/smile and re-submit with challenge evidence"},
            )

        biometric = BiometricResult(
            liveness=live.label,
            liveness_score=live.score,
            face_match_score=match.score if match else None,
            face_match_passed=match.passed if match else None,
            face_detected=bool(faces),
        )

        explain: list[str] = list(doc_result.explainability)
        doc_label = (doc_result.document.document_type if doc_result.document else None) or "document"
        explain.insert(0, f"document_type:{doc_label}")
        if live.label != "live":
            explain.append("liveness_failed")
        if live.backend == "unavailable":
            explain.append("liveness_model_unavailable")
        if mesh.backend == "unavailable":
            explain.append("face_mesh_unavailable")
        if match and match.backend in {"unavailable", "sface_required"}:
            explain.append(f"face_match_backend:{match.backend}")
        if match and not match.passed:
            explain.append(f"face_match_below_threshold:{match.score:.3f}")
        if match and match.passed:
            explain.append(f"face_match_passed:{match.score:.3f}")
        if match and not match.face_detected_a:
            explain.append("no_face_on_document")
        if match and not match.face_detected_b:
            explain.append("no_face_on_selfie")
        if match:
            explain.append(f"face_backend:{match.backend}")
        if multi_face:
            explain.append("multiple_faces")
        if duplicate_hit:
            explain.append(f"duplicate_identity:{duplicate.get('client_id')}:{duplicate_score:.3f}")
        if active.head_pose_yaw is not None:
            explain.append(f"head_yaw:{active.head_pose_yaw:.1f}")
        if active.head_pose_pitch is not None:
            explain.append(f"head_pitch:{active.head_pose_pitch:.1f}")
        if active.head_pose_roll is not None:
            explain.append(f"head_roll:{active.head_pose_roll:.1f}")
        if mesh.ear is not None:
            explain.append(f"ear:{mesh.ear:.3f}")
        if mesh.mar is not None:
            explain.append(f"mar:{mesh.mar:.3f}")
        for flag in replay.flags:
            explain.append(f"replay:{flag}")

        fraud = compute_fraud_score(
            face_match_score=match.score if match else None,
            face_match_passed=match.passed if match else None,
            liveness_score=live.score if live.label != "unknown" else None,
            liveness_passed=(live.label == "live") if live.label != "unknown" else False,
            document_quality=doc_result.document.quality_score if doc_result.document else None,
            document_valid=doc_result.document.valid if doc_result.document else None,
            document_authenticity=doc_result.document.authenticity_score if doc_result.document else None,
            document_authenticity_passed=(
                doc_result.document.authenticity_passed if doc_result.document else None
            ),
            duplicate_score=duplicate_score,
            duplicate_hit=duplicate_hit,
            device_risk=max(device_risk, replay.risk * 0.5),
            velocity_count=velocity_count,
            multi_face=multi_face,
            heuristic_liveness=False,
            active_challenge_needed=challenge.required and challenge.passed is None,
            active_challenge_passed=challenge.passed,
        )

        # Hard biometric fails still reject even if fraud softens
        weak_production_stack = (
            live.backend != "minifas_onnx"
            or not self.faces.production_ready
            or mesh.backend == "unavailable"
            or (match is not None and match.backend in {"unavailable", "sface_required"})
        )
        if (
            weak_production_stack
            or live.label not in {"live", "unknown"}
            or (match is not None and not match.passed)
            or not faces
            or multi_face
            or live.label == "unknown"
        ):
            outcome = CheckOutcome.REJECT
        elif doc_result.outcome == CheckOutcome.REJECT:
            outcome = CheckOutcome.REJECT
        else:
            outcome = fraud.outcome
            if doc_result.outcome == CheckOutcome.CONSIDER and outcome == CheckOutcome.CLEAR:
                outcome = CheckOutcome.CONSIDER

        scores = _identity_scores(document=doc_result.document, biometric=biometric)
        scores["fraudRiskScore"] = int(round(fraud.risk_score))
        breakdown = build_identity_result_breakdown(
            scores,
            outcome=outcome.value,
            face_detected=bool(faces),
            previously_enrolled="attention" if duplicate_hit else "clear",
            banned_faces="attention" if duplicate_hit and (duplicate_score or 0) >= 0.75 else "clear",
        )
        selfie_face = faces[0] if faces else None
        signals = {
            "scores": scores,
            "complycube": breakdown,
            "fraud": fraud.to_dict(),
            "active_liveness": {
                "passed": active.passed,
                "backend": active.backend,
                "head_pose_yaw": active.head_pose_yaw,
                "head_pose_pitch": active.head_pose_pitch,
                "head_pose_roll": active.head_pose_roll,
                "detection_certainty": active.detection_certainty,
            },
            "face_mesh": mesh.to_dict(),
            "replay": replay.to_dict(),
            "active_challenge": challenge.to_dict(),
            "duplicate": duplicate or None,
            "device": device or None,
            "device_velocity": velocity or None,
            "face_analysis": {
                "backend": match.backend if match else self.faces._backend,
                "face_detected_document": match.face_detected_a if match else None,
                "face_detected_selfie": match.face_detected_b if match else bool(faces),
                "selfie_yaw": selfie_face.pose_yaw if selfie_face else mesh.yaw,
                "selfie_pitch": selfie_face.pose_pitch if selfie_face else mesh.pitch,
                "selfie_roll": selfie_face.pose_roll if selfie_face else mesh.roll,
                "liveness_backend": live.backend,
                "mesh_backend": mesh.backend,
                "ear": mesh.ear,
                "mar": mesh.mar,
                "eyes_open": mesh.eyes_open,
                "smiling": mesh.smiling,
            },
            "reject_reasons": [
                e
                for e in explain
                if e.startswith(("liveness_", "face_match_", "no_face_", "reject:", "multiple_", "duplicate_", "replay:"))
            ],
        }

        versions = dict(doc_result.model_versions)
        versions["liveness"] = live.backend
        versions["active_liveness"] = active.backend
        versions["face_mesh"] = mesh.backend
        if match:
            versions["face"] = match.backend

        return CheckResult(
            outcome=outcome,
            document=doc_result.document,
            biometric=biometric,
            risk_score=fraud.risk_score,
            signals=signals,
            explainability=explain,
            model_versions=versions,
        )

    def run_enhanced_identity(self, ctx: CheckContext) -> CheckResult:
        """Identity check plus OpenFace-style active liveness (pose / AU signals)."""
        base = self.run_identity(ctx)
        active = (base.signals or {}).get("active_liveness") or {}
        challenge = (base.signals or {}).get("active_challenge") or {}
        explain = list(base.explainability)
        outcome = base.outcome
        if not active.get("passed", True):
            explain.append("active_liveness_failed")
            outcome = CheckOutcome.REJECT
        if challenge.get("required") and challenge.get("passed") is False:
            explain.append("active_challenge_failed")
            outcome = CheckOutcome.REJECT
        if challenge.get("required") and challenge.get("passed") is None and outcome == CheckOutcome.CLEAR:
            explain.append("active_challenge_pending")
            outcome = CheckOutcome.CONSIDER
        return CheckResult(
            outcome=outcome,
            document=base.document,
            biometric=base.biometric,
            risk_score=base.risk_score,
            signals=base.signals,
            explainability=explain,
            model_versions=base.model_versions,
        )

    def run_face_authentication(self, ctx: CheckContext) -> CheckResult:
        """1:N match against enrolled gallery (Face Recognition System pattern)."""
        if ctx.live_photo_image is None:
            return CheckResult(
                outcome=CheckOutcome.REJECT,
                explainability=["missing_live_photo"],
            )

        gallery_data = (ctx.options or {}).get("gallery_match")
        gallery_error = (ctx.options or {}).get("gallery_error")
        faces = self.faces.detect(ctx.live_photo_image)
        bbox = faces[0].bbox if faces else None
        live = self.liveness.predict(ctx.live_photo_image, bbox)

        if gallery_data is None and gallery_error == "no_enrollment":
            return CheckResult(
                outcome=CheckOutcome.REJECT,
                biometric=BiometricResult(
                    liveness=live.label,
                    liveness_score=live.score,
                    face_detected=bool(faces),
                ),
                explainability=["no_face_enrollment"],
                model_versions={"face_gallery": self.faces._backend, "liveness": live.backend},
            )

        if not faces:
            return CheckResult(
                outcome=CheckOutcome.REJECT,
                biometric=BiometricResult(
                    liveness=live.label,
                    liveness_score=live.score,
                    face_detected=False,
                ),
                explainability=["no_face_on_selfie", "liveness_failed" if live.label != "live" else "no_face"],
            )

        if gallery_data is None:
            err = (ctx.options or {}).get("gallery_error")
            explain = ["gallery_match_not_run"]
            if err == "no_enrollment":
                explain.append("no_face_enrollment")
            return CheckResult(
                outcome=CheckOutcome.REJECT if err else CheckOutcome.CONSIDER,
                biometric=BiometricResult(
                    liveness=live.label,
                    liveness_score=live.score,
                    face_detected=True,
                ),
                explainability=explain,
                model_versions={"face_gallery": self.faces._backend, "liveness": live.backend},
            )

        score = float(gallery_data.get("score", 0.0))
        passed = bool(gallery_data.get("passed"))
        label = gallery_data.get("label", "")

        biometric = BiometricResult(
            liveness=live.label,
            liveness_score=live.score,
            face_match_score=score,
            face_match_passed=passed,
            face_detected=True,
        )

        explain: list[str] = []
        if live.label != "live":
            explain.append("liveness_failed")
        if not passed:
            explain.append(f"gallery_match_below_threshold:{score:.3f}")
        else:
            explain.append(f"gallery_match:{label}")

        if live.label != "live" or not passed:
            outcome = CheckOutcome.REJECT
        else:
            outcome = CheckOutcome.CLEAR

        return CheckResult(
            outcome=outcome,
            biometric=biometric,
            matches=[{"label": label, "score": score, "embedding_id": gallery_data.get("embedding_id")}],
            signals={"gallery": gallery_data},
            explainability=explain,
            model_versions={
                "face_gallery": gallery_data.get("backend", "insightface"),
                "liveness": live.backend,
            },
        )

    def run_screening(self, ctx: CheckContext) -> CheckResult:
        """Placeholder AML — hook yente later. Always clear unless name looks blocked."""
        name = (ctx.client_name or "").strip().lower()
        blocked = {"osama bin laden", "test sanctioned person"}
        if name and name in blocked:
            return CheckResult(
                outcome=CheckOutcome.CONSIDER,
                matches=[{"name": name, "list": "demo_blocklist", "score": 0.99}],
                explainability=["demo_sanctions_hit"],
                model_versions={"aml": "demo_blocklist"},
            )
        return CheckResult(
            outcome=CheckOutcome.CLEAR,
            matches=[],
            explainability=["no_matches"],
            model_versions={"aml": "demo_blocklist"},
        )
