"""Worker that executes pending checks against MongoDB."""

from __future__ import annotations

from liveness.checks import CheckContext, CheckEngine
from liveness.db import find_one, get_database, update_one
from liveness.ml import decode_image
from liveness.storage import BlobStore
from liveness.types import CheckStatus, CheckType, utc_now


async def process_check(check_id: str) -> None:
    engine = CheckEngine()
    store = BlobStore()
    check = await find_one("checks", {"id": check_id})
    if check is None:
        return

    try:
        doc_img = None
        live_img = None
        client_name = None

        if check.get("document_id"):
            doc = await find_one("documents", {"id": check["document_id"]})
            if doc:
                doc_img = decode_image(store.get(doc["storage_key"]))

        if check.get("live_photo_id"):
            photo = await find_one("live_photos", {"id": check["live_photo_id"]})
            if photo:
                live_img = decode_image(store.get(photo["storage_key"]))

        client = await find_one("clients", {"id": check["client_id"]})
        if client:
            client_name = client.get("full_name")

        result = engine.run(
            CheckType(check["type"]),
            CheckContext(
                document_image=doc_img,
                live_photo_image=live_img,
                client_name=client_name,
                options=check.get("options"),
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
