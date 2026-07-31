"""Check runners — document + identity pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from liveness.config import Settings, get_settings
from liveness.ml import DocumentOcr, FaceAnalyzer, LivenessDetector, OpenFaceAnalyzer, assess_quality
from liveness.ml.document_types import resolve_document_type
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
        self.faces = FaceAnalyzer()
        self.openface = OpenFaceAnalyzer()

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
        ocr = self.ocr.extract(ctx.document_image)
        warnings = list(quality.warnings) + list(ocr.warnings)

        hard_fail = any(w.startswith("reject:") for w in warnings)
        mrz_ok = ocr.mrz_valid is not False
        valid = quality.passed and not hard_fail and mrz_ok

        if hard_fail or not quality.passed:
            outcome = CheckOutcome.REJECT
        elif ocr.mrz_valid is False:
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
                document_type=doc_type,
                fields=ocr.fields,
                warnings=warnings,
            ),
            signals={
                "scores": enrich_verification_scores(
                    {
                        "document_type": doc_type,
                        "document_quality": quality.score,
                        "document_valid": valid,
                        "liveness_score": None,
                        "face_match_score": None,
                    }
                ),
            },
            explainability=warnings,
            model_versions={"ocr": ocr.backend, "quality": "opencv_heuristic"},
        )

    def run_identity(self, ctx: CheckContext) -> CheckResult:
        doc_result = self.run_document(ctx)
        doc_result.document = _apply_document_type(doc_result.document, ctx, doc_result.document.document_type if doc_result.document else None)
        if ctx.live_photo_image is None:
            return CheckResult(
                outcome=CheckOutcome.REJECT,
                document=doc_result.document,
                explainability=["missing_live_photo"],
            )

        faces = self.faces.detect(ctx.live_photo_image)
        bbox = faces[0].bbox if faces else None
        live = self.liveness.predict(ctx.live_photo_image, bbox)
        active = self.openface.analyze(ctx.live_photo_image, bbox)

        match = None
        if ctx.document_image is not None:
            match = self.faces.match(ctx.document_image, ctx.live_photo_image)

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
        if match and not match.passed:
            explain.append(f"face_match_below_threshold:{match.score:.3f}")
        if match and match.passed:
            explain.append(f"face_match_passed:{match.score:.3f}")
        if match and not match.face_detected_a:
            explain.append("no_face_on_document")
        if match and not match.face_detected_b:
            explain.append("no_face_on_selfie")

        scores = _identity_scores(document=doc_result.document, biometric=biometric)
        signals = {
            "scores": scores,
            "active_liveness": {
                "passed": active.passed,
                "backend": active.backend,
                "head_pose_yaw": active.head_pose_yaw,
                "head_pose_pitch": active.head_pose_pitch,
                "detection_certainty": active.detection_certainty,
            },
        }

        if (
            doc_result.outcome == CheckOutcome.REJECT
            or live.label != "live"
            or (match is not None and not match.passed)
            or not faces
        ):
            outcome = CheckOutcome.REJECT
        elif doc_result.outcome == CheckOutcome.CONSIDER:
            outcome = CheckOutcome.CONSIDER
        else:
            outcome = CheckOutcome.CLEAR

        versions = dict(doc_result.model_versions)
        versions["liveness"] = live.backend
        versions["active_liveness"] = active.backend
        if match:
            versions["face"] = match.backend

        return CheckResult(
            outcome=outcome,
            document=doc_result.document,
            biometric=biometric,
            signals=signals,
            explainability=explain,
            model_versions=versions,
        )

    def run_enhanced_identity(self, ctx: CheckContext) -> CheckResult:
        """Identity check plus OpenFace-style active liveness (pose / AU signals)."""
        base = self.run_identity(ctx)
        active = (base.signals or {}).get("active_liveness") or {}
        if not active.get("passed", True):
            explain = list(base.explainability)
            explain.append("active_liveness_failed")
            return CheckResult(
                outcome=CheckOutcome.REJECT,
                document=base.document,
                biometric=base.biometric,
                signals=base.signals,
                explainability=explain,
                model_versions=base.model_versions,
            )
        return base

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
