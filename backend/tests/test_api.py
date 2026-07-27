"""API integration tests with httpx + ASGI + mongomock."""

from __future__ import annotations

import io

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient
from PIL import Image

from liveness.api import create_app
from liveness.config import get_settings
import liveness.db as db_mod


@pytest.fixture(autouse=True)
def _tmp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVENESS_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("LIVENESS_API_KEY", "sk_test_liveness_dev")
    monkeypatch.setenv("LIVENESS_MONGODB_DB", "liveness_test")
    get_settings.cache_clear()
    db_mod._client = None
    db_mod._db = None
    yield
    get_settings.cache_clear()
    db_mod._client = None
    db_mod._db = None


def _jpeg_bytes(color=(100, 120, 140), size=(400, 300)) -> bytes:
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    arr[:] = color
    arr[::4, ::4] = 200
    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
async def client(monkeypatch):
    mock = AsyncMongoMockClient()

    def _get_client():
        return mock

    monkeypatch.setattr(db_mod, "get_client", _get_client)
    db_mod._client = mock
    db_mod._db = mock["liveness_test"]

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            yield ac


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["backends"]["db"] == "mongodb"


@pytest.mark.asyncio
async def test_identity_check_flow(client: AsyncClient):
    headers = {"X-Api-Key": "sk_test_liveness_dev"}

    cr = await client.post(
        "/v1/clients",
        json={"email": "a@b.com", "full_name": "Ada Lovelace"},
        headers=headers,
    )
    assert cr.status_code == 200
    client_id = cr.json()["id"]

    doc = await client.post(
        "/v1/documents",
        params={"client_id": client_id},
        files={"file": ("doc.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )
    assert doc.status_code == 200
    document_id = doc.json()["id"]

    photo = await client.post(
        "/v1/livePhotos",
        params={"client_id": client_id},
        files={"file": ("selfie.jpg", _jpeg_bytes((90, 110, 130)), "image/jpeg")},
        headers=headers,
    )
    assert photo.status_code == 200
    live_photo_id = photo.json()["id"]

    chk = await client.post(
        "/v1/checks",
        json={
            "client_id": client_id,
            "type": "identity_check",
            "document_id": document_id,
            "live_photo_id": live_photo_id,
            "client_consent": True,
        },
        headers=headers,
    )
    assert chk.status_code == 200
    check_id = chk.json()["id"]
    assert chk.json()["status"] == "pending"

    import asyncio

    for _ in range(30):
        got = await client.get(f"/v1/checks/{check_id}", headers=headers)
        assert got.status_code == 200
        if got.json()["status"] in {"complete", "failed"}:
            break
        await asyncio.sleep(0.05)

    final = (await client.get(f"/v1/checks/{check_id}", headers=headers)).json()
    assert final["status"] in {"complete", "failed"}
    if final["status"] == "complete":
        assert final["result"]["outcome"] in {"clear", "consider", "reject"}
