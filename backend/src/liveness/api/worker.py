"""Worker that executes pending checks against MongoDB."""

from __future__ import annotations

from liveness.api.deps import get_check_engine
from liveness.checks import CheckContext
from liveness.db import find_one, get_database, update_one
from liveness.ml import FaceGallery, decode_image
from liveness.storage import BlobStore
from liveness.types import CheckStatus, CheckType, utc_now


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
                doc_img = decode_image(store.get(doc["storage_key"]))
                if doc.get("document_type"):
                    options["document_type"] = doc["document_type"]
                if doc.get("issuing_country"):
                    options["issuing_country"] = doc["issuing_country"]

        if check.get("live_photo_id"):
            photo = await find_one("live_photos", {"id": check["live_photo_id"]})
            if photo:
                live_img = decode_image(store.get(photo["storage_key"]))

        client = await find_one("clients", {"id": check["client_id"]})
        if client:
            client_name = client.get("full_name")

        check_type = CheckType(check["type"])
        if check_type == CheckType.FACE_AUTHENTICATION and live_img is not None:
            gallery = FaceGallery(analyzer=engine.faces)
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

        result = engine.run(
            check_type,
            CheckContext(
                document_image=doc_img,
                live_photo_image=live_img,
                client_name=client_name,
                options=options,
            ),
        )
        await update_one(
            "checks",
            {"id": check_id},
            {
                "outcome": result.outcome.value,
                "result": result.model_dump(mode="json"),
                "status": CheckStatus.COMPLETE.value,
                "error": None,
                "completed_at": utc_now(),
                "updated_at": utc_now(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        await update_one(
            "checks",
            {"id": check_id},
            {
                "status": CheckStatus.FAILED.value,
                "error": str(exc),
                "updated_at": utc_now(),
            },
        )
    # Notify Trustanova webhooks when running inside the unified backend
    try:
        from app.services.webhooks import emit_check_finished_from_id

        await emit_check_finished_from_id(check_id)
    except Exception:  # noqa: BLE001
        pass
    # touch DB to keep connection warm / ensure writes flushed
    _ = get_database()
