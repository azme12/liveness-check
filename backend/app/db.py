from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(get_settings().mongodb_url)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[get_settings().mongodb_db]


async def init_db() -> None:
    db = get_database()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.notifications.create_index("id", unique=True)
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.organizations.create_index("id", unique=True)
    await db.clients.create_index("id", unique=True)
    await db.clients.create_index([("org_id", 1), ("created_at", -1)])
    await db.checks.create_index("id", unique=True)
    await db.sessions.create_index("id", unique=True)
    await db.workflows.create_index("id", unique=True)
    await db.api_keys.create_index("id", unique=True)
    await db.allowed_ips.create_index("id", unique=True)
    await db.webhooks.create_index("id", unique=True)
    await db.webhooks.create_index([("org_id", 1), ("enabled", 1)])
    await db.events.create_index([("created_at", -1)])
    await db.events.create_index([("org_id", 1), ("created_at", -1)])
    await db.events.create_index("id", unique=True)
    await db.webhook_deliveries.create_index("id", unique=True)
    await db.webhook_deliveries.create_index([("status", 1), ("next_attempt_at", 1)])
    await db.webhook_deliveries.create_index([("org_id", 1), ("created_at", -1)])
    await db.api_logs.create_index([("created_at", -1)])


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
