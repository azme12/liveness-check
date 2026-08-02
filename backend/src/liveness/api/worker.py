"""Worker that executes pending checks against MongoDB."""

from __future__ import annotations

from time import perf_counter

from liveness.api.deps import get_check_engine
from liveness.checks import CheckContext
from liveness.db import find_one, get_database, update_one
from liveness.ml import FaceGallery, decode_image
from liveness.ml.device_intel import device_velocity
from liveness.storage import BlobStore
from liveness.types import CheckOutcome, CheckResult, CheckStatus, CheckType, utc_now


def _processing_error_result(message: str) -> CheckResult:
    return CheckResult(
        outcome=CheckOutcome.REJECT,
        explainability=["processing_error"],
        signals={
            "reject_reasons": ["processing_error"],
            "processing_error": message,
        },
    )


async def _save_check_result(
    check_id: str,
    result: CheckResult,
    *,
    status: CheckStatus = CheckStatus.COMPLETE,
    error: str | None = None,
) -> None:
    await update_one(
        "checks",
        {"id": check_id},
        {
            "outcome": result.outcome.value,
            "result": result.model_dump(mode="json"),
            "status": status.value,
            "error": error,
            "completed_at": utc_now(),
            "updated_at": utc_now(),
        },
    )


async def _save_processing_failure(check_id: str, exc: Exception) -> None:
    message = str(exc) or exc.__class__.__name__
    result = _processing_error_result(message)
    await _save_check_result(check_id, result, status=CheckStatus.FAILED, error=message)


async def process_check(check_id: str) -> None:
    engine = get_check_engine()
    store = BlobStore()
    check = await find_one("checks", {"id": check_id})
    if check is None:
        return

    try:
        doc_img = None
        live_img = None
        client_name = None
        options = dict(check.get("options") or {})

        if check.get("document_id"):
            doc = await find_one("documents", {"id": check["document_id"]})
            if doc:
                try:
                    doc_img = decode_image(store.get(doc["storage_key"]))
                except FileNotFoundError as exc:
                    result = CheckResult(
                        outcome=CheckOutcome.REJECT,
                        explainability=["document_media_missing"],
                        signals={
                            "reject_reasons": ["document_media_missing"],
                            "processing_error": str(exc),
                        },
                    )
                    await _save_check_result(check_id, result, error=str(exc))
                    return
                if doc.get("document_type"):
                    options["document_type"] = doc["document_type"]
                if doc.get("issuing_country"):
                    options["issuing_country"] = doc["issuing_country"]

        if check.get("live_photo_id"):
            photo = await find_one("live_photos", {"id": check["live_photo_id"]})
            if photo:
                try:
                    live_img = decode_image(store.get(photo["storage_key"]))
                except FileNotFoundError as exc:
                    result = CheckResult(
                        outcome=CheckOutcome.REJECT,
                        explainability=["selfie_media_missing"],
                        signals={
                            "reject_reasons": ["selfie_media_missing"],
                            "processing_error": str(exc),
                        },
                    )
                    await _save_check_result(check_id, result, error=str(exc))
                    return
                if photo.get("device") and "device" not in options:
                    options["device"] = photo["device"]

        client = await find_one("clients", {"id": check["client_id"]})
        if client:
            client_name = client.get("full_name")

        check_type = CheckType(check["type"])
        gallery = FaceGallery(analyzer=engine.faces)

        if check_type == CheckType.FACE_AUTHENTICATION and live_img is not None:
            match = await gallery.search_client(client_id=check["client_id"], image=live_img)
            if match is None:
                enrolled = await gallery.has_enrollment(check["client_id"])
                options["gallery_match"] = None
                if not enrolled:
                    options["gallery_error"] = "no_enrollment"
            else:
                options["gallery_match"] = {
                    "client_id": match.client_id,
                    "label": match.label,
                    "score": match.score,
                    "passed": match.passed,
                    "embedding_id": match.embedding_id,
                    "backend": engine.faces._backend,
                }

        if check_type in {CheckType.IDENTITY, CheckType.ENHANCED_IDENTITY} and live_img is not None:
            org_id = check.get("org_id")
            if org_id:
                dup = await gallery.search_duplicates(
                    org_id=org_id,
                    image=live_img,
                    exclude_client_id=check["client_id"],
                    threshold=0.55,
                )
                if dup is not None and dup.passed:
                    options["duplicate_match"] = {
                        "client_id": dup.client_id,
                        "label": dup.label,
                        "score": dup.score,
                        "passed": True,
                        "embedding_id": dup.embedding_id,
                    }
                fp = (options.get("device") or {}).get("fingerprint_hash")
                if fp:
                    options["device_velocity"] = await device_velocity(
                        org_id=org_id,
                        fingerprint_hash=fp,
                        exclude_client_id=check["client_id"],
                    )
            options.setdefault("session_id", check.get("session_id"))
            options.setdefault("client_id", check.get("client_id"))

        started = perf_counter()
        result = engine.run(
            check_type,
            CheckContext(
                document_image=doc_img,
                live_photo_image=live_img,
                client_name=client_name,
                options=options,
            ),
        )
        processing_ms = round((perf_counter() - started) * 1000.0, 2)
        signals = dict(result.signals or {})
        signals["audit"] = {
            "processing_ms": processing_ms,
            "models": dict(result.model_versions),
            "thresholds": {
                "face_match": engine.settings.face_match_threshold,
                "face_gallery": engine.settings.face_gallery_threshold,
                "duplicate_face": engine.settings.duplicate_face_threshold,
                "liveness": engine.settings.liveness_threshold,
                "quality": engine.settings.quality_threshold,
            },
            "policy_version": "enterprise-risk-v1",
            "evaluated_at": utc_now().isoformat(),
        }
        result.signals = signals

        if (
            check_type in {CheckType.IDENTITY, CheckType.ENHANCED_IDENTITY}
            and live_img is not None
            and result.outcome == CheckOutcome.CLEAR
            and check.get("org_id")
        ):
            await gallery.ensure_enrolled(
                client_id=check["client_id"],
                org_id=check["org_id"],
                image=live_img,
                source_id=check.get("live_photo_id"),
                label=client_name or check["client_id"],
            )

        await _save_check_result(check_id, result)
    except Exception as exc:  # noqa: BLE001
        await _save_processing_failure(check_id, exc)
    try:
        from app.services.webhooks import emit_check_finished_from_id

        await emit_check_finished_from_id(check_id)
    except Exception:  # noqa: BLE001
        pass
    _ = get_database()
