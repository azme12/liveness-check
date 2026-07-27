"""Check runners — document + identity pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from liveness.config import Settings, get_settings
from liveness.ml import DocumentOcr, FaceAnalyzer, LivenessDetector, assess_quality
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


class CheckEngine:
    """Orchestrates async check types (run synchronously in worker for MVP)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.ocr = DocumentOcr()
        self.liveness = LivenessDetector()
        self.faces = FaceAnalyzer()

    def run(self, check_type: CheckType, ctx: CheckContext) -> CheckResult:
        if check_type == CheckType.DOCUMENT:
            return self.run_document(ctx)
        if check_type == CheckType.IDENTITY:
            return self.run_identity(ctx)
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

        return CheckResult(
            outcome=outcome,
            document=DocumentResult(
                valid=valid,
                mrz_valid=ocr.mrz_valid,
                quality_score=quality.score,
                document_type=ocr.document_type,
                fields=ocr.fields,
                warnings=warnings,
            ),
            explainability=warnings,
            model_versions={"ocr": ocr.backend, "quality": "opencv_heuristic"},
        )

    def run_identity(self, ctx: CheckContext) -> CheckResult:
        doc_result = self.run_document(ctx)
        if ctx.live_photo_image is None:
            return CheckResult(
                outcome=CheckOutcome.REJECT,
                document=doc_result.document,
                explainability=["missing_live_photo"],
            )

        faces = self.faces.detect(ctx.live_photo_image)
        bbox = faces[0].bbox if faces else None
        live = self.liveness.predict(ctx.live_photo_image, bbox)

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
        if live.label != "live":
            explain.append("liveness_failed")
        if match and not match.passed:
            explain.append(f"face_match_below_threshold:{match.score:.3f}")
        if match and not match.face_detected_a:
            explain.append("no_face_on_document")
        if match and not match.face_detected_b:
            explain.append("no_face_on_selfie")

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
        if match:
            versions["face"] = match.backend

        return CheckResult(
            outcome=outcome,
            document=doc_result.document,
            biometric=biometric,
            explainability=explain,
            model_versions=versions,
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
