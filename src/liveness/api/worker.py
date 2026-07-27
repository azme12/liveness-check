"""Worker that executes pending checks."""

from __future__ import annotations

from liveness.checks import CheckContext, CheckEngine
from liveness.db import Check, get_session_factory
from liveness.ml import decode_image
from liveness.storage import BlobStore
from liveness.types import CheckStatus, CheckType, utc_now


async def process_check(check_id: str) -> None:
    factory = get_session_factory()
    engine = CheckEngine()
    store = BlobStore()

    async with factory() as session:
        check = await session.get(Check, check_id)
        if check is None:
            return

        try:
            doc_img = None
            live_img = None
            client_name = None

            if check.document_id:
                from liveness.db import Document

                doc = await session.get(Document, check.document_id)
                if doc:
                    doc_img = decode_image(store.get(doc.storage_key))

            if check.live_photo_id:
                from liveness.db import LivePhoto

                photo = await session.get(LivePhoto, check.live_photo_id)
                if photo:
                    live_img = decode_image(store.get(photo.storage_key))

            from liveness.db import Client

            client = await session.get(Client, check.client_id)
            if client:
                client_name = client.full_name

            result = engine.run(
                CheckType(check.type),
                CheckContext(
                    document_image=doc_img,
                    live_photo_image=live_img,
                    client_name=client_name,
                    options=check.options,
                ),
            )
            check.result = result.model_dump(mode="json")
            check.status = CheckStatus.COMPLETE.value
            check.error = None
        except Exception as exc:  # noqa: BLE001 — surface to API status
            check.status = CheckStatus.FAILED.value
            check.error = str(exc)
        check.updated_at = utc_now()
        await session.commit()
