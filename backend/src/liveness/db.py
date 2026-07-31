"""MongoDB (Motor) persistence for clients, media, checks, and sessions."""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from liveness.config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_url)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        settings = get_settings()
        _db = get_client()[settings.mongodb_db]
    return _db


async def init_db() -> None:
    """Create indexes. Safe to call on every startup."""
    db = get_database()
    await db.clients.create_index("id", unique=True)
    await db.documents.create_index("id", unique=True)
    await db.documents.create_index("client_id")
    await db.live_photos.create_index("id", unique=True)
    await db.live_photos.create_index("client_id")
    await db.checks.create_index("id", unique=True)
    await db.checks.create_index([("client_id", 1), ("created_at", -1)])
    await db.sessions.create_index("id", unique=True)
    await db.sessions.create_index("token", unique=True)
    await db.face_embeddings.create_index("id", unique=True)
    await db.face_embeddings.create_index("client_id")


async def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


async def get_db():
    """FastAPI dependency — yields the database handle."""
    yield get_database()


async def find_one(collection: str, query: dict[str, Any]) -> dict[str, Any] | None:
    return await get_database()[collection].find_one(query, {"_id": 0})


async def insert_one(collection: str, doc: dict[str, Any]) -> dict[str, Any]:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    await get_database()[collection].insert_one(payload)
    return payload


async def update_one(collection: str, query: dict[str, Any], patch: dict[str, Any]) -> None:
    await get_database()[collection].update_one(query, {"$set": patch})


__all__ = [
    "init_db",
    "close_db",
    "get_db",
    "get_database",
    "get_client",
    "find_one",
    "insert_one",
    "update_one",
]
