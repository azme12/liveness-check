from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_database
from app.security import hash_password


def new_id(prefix: str = "") -> str:
    raw = uuid.uuid4().hex
    return f"{prefix}{raw}" if prefix else raw


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_user_account_defaults(user: dict[str, Any]) -> dict[str, Any]:
    """Backfill profile fields lightly. Avoids extra DB work on every /me."""
    db = get_database()
    patch: dict[str, Any] = {}
    if not user.get("first_name") and user.get("full_name"):
        parts = str(user["full_name"]).strip().split(None, 1)
        patch["first_name"] = parts[0] if parts else "User"
        patch["last_name"] = parts[1] if len(parts) > 1 else ""
    if "theme" not in user:
        patch["theme"] = "system"
    if "notification_prefs" not in user:
        patch["notification_prefs"] = {"email_checks": True, "email_webhooks": True, "in_app": True}
    if patch:
        await db.users.update_one({"id": user["id"]}, {"$set": patch})
        user = {**user, **patch}

    # Only check notifications once — after welcome is written, set a flag on the user.
    if not user.get("welcome_notification_sent"):
        existing = await db.notifications.find_one({"user_id": user["id"]}, {"_id": 1})
        if not existing:
            now = utcnow()
            await db.notifications.insert_one(
                {
                    "id": new_id("ntf_"),
                    "user_id": user["id"],
                    "type": "system",
                    "title": "Welcome to Trustanova",
                    "body": "Your workspace is ready. Add a client or create a workflow to get started.",
                    "read": False,
                    "created_at": now,
                }
            )
        await db.users.update_one({"id": user["id"]}, {"$set": {"welcome_notification_sent": True}})
        user = {**user, "welcome_notification_sent": True}
    return user


async def ensure_org_defaults(org_id: str) -> None:
    """Backfill org flags only. Skips after first successful backfill."""
    db = get_database()
    org = await db.organizations.find_one({"id": org_id})
    if not org:
        return
    patch: dict = {}
    if "live_enabled" not in org:
        patch["live_enabled"] = False
    if "activation" not in org:
        patch["activation"] = {"step": 1, "completed": False}
    # One-time env tag backfill for legacy docs (avoid 8x update_many on every /me).
    if not org.get("env_backfilled"):
        for coll in ("clients", "sessions", "checks", "workflows", "webhooks", "events", "api_logs", "allowed_ips"):
            await db[coll].update_many(
                {"org_id": org_id, "environment": {"$exists": False}},
                {"$set": {"environment": "live"}},
            )
        patch["env_backfilled"] = True
    if patch:
        await db.organizations.update_one({"id": org_id}, {"$set": patch})


# Backwards-compatible alias (old imports)
async def ensure_workspace_demo(org_id: str) -> None:
    await ensure_org_defaults(org_id)


async def seed_if_empty() -> None:
    db = get_database()
    if await db.users.count_documents({}) > 0:
        return

    org_id = new_id("org_")
    user_id = new_id("usr_")
    now = utcnow()

    await db.organizations.insert_one(
        {
            "id": org_id,
            "name": "NileVerify Technologies",
            "live_enabled": False,
            "activation": {"step": 1, "completed": False},
            "created_at": now,
        }
    )
    await db.users.insert_one(
        {
            "id": user_id,
            "email": "admin@trustanova.dev",
            "full_name": "Admin User",
            "first_name": "Admin",
            "last_name": "User",
            "password_hash": hash_password("admin123"),
            "org_id": org_id,
            "role": "owner",
            "theme": "system",
            "notification_prefs": {"email_checks": True, "email_webhooks": True, "in_app": True},
            "created_at": now,
        }
    )
    await db.notifications.insert_many(
        [
            {
                "id": new_id("ntf_"),
                "user_id": user_id,
                "type": "system",
                "title": "Welcome to Trustanova",
                "body": "Your workspace is ready. Start by adding a client or creating a workflow.",
                "read": False,
                "created_at": now,
            },
            {
                "id": new_id("ntf_"),
                "user_id": user_id,
                "type": "check",
                "title": "Identity check completed",
                "body": "A sample identity check finished with Clear outcome.",
                "read": False,
                "created_at": now - timedelta(hours=2),
            },
        ]
    )

    clients = []
    live_names = [
        ("Marta", "Gebre", "marta.gebre@example.com"),
        ("Kidus", "Alemu", "kidus.alemu@example.com"),
        ("Selam", "Bekele", "selam.bekele@example.com"),
        ("Nahom", "Tadesse", "nahom.tadesse@example.com"),
        ("Hiwot", "Assefa", "hiwot.assefa@example.com"),
    ]
    for first, last, email in live_names:
        cid = new_id("cli_")
        clients.append(
            {
                "id": cid,
                "org_id": org_id,
                "environment": "live",
                "first_name": first,
                "last_name": last,
                "name": f"{first} {last}",
                "email": email,
                "type": "person",
                "risk": "low",
                "created_at": now - timedelta(hours=len(clients)),
            }
        )
    test_names = [
        ("Demo", "Client One", "demo1@test.nileverify.dev"),
        ("Demo", "Client Two", "demo2@test.nileverify.dev"),
        ("Sandbox", "Company", "sandbox@test.nileverify.dev"),
    ]
    for i, (first, last, email) in enumerate(test_names):
        clients.append(
            {
                "id": new_id("cli_"),
                "org_id": org_id,
                "environment": "test",
                "first_name": first,
                "last_name": last,
                "name": f"{first} {last}",
                "email": email,
                "type": "company" if "Company" in last else "person",
                "risk": "low",
                "created_at": now - timedelta(hours=i + 10),
            }
        )
    if clients:
        await db.clients.insert_many(clients)

    workflows = [
        {
            "id": new_id("wf_"),
            "org_id": org_id,
            "environment": "live",
            "name": "Liveness",
            "description": "liveness check for national ID",
            "status": "active",
            "version": 1,
            "steps": [{"type": "identity_check", "label": "Identity Check"}],
            "created_at": now - timedelta(days=4),
            "updated_at": now - timedelta(days=4),
        },
        {
            "id": new_id("wf_"),
            "org_id": org_id,
            "environment": "live",
            "name": "Full KYC",
            "description": "document check, enhanced id check",
            "status": "active",
            "version": 1,
            "steps": [
                {"type": "document_check", "label": "Document Check"},
                {"type": "identity_check", "label": "Identity Check"},
            ],
            "created_at": now - timedelta(days=4),
            "updated_at": now - timedelta(days=4),
        },
        {
            "id": new_id("wf_"),
            "org_id": org_id,
            "environment": "test",
            "name": "Sandbox KYC",
            "description": "test-only verification workflow",
            "status": "active",
            "version": 1,
            "steps": [{"type": "identity_check", "label": "Identity Check"}],
            "created_at": now - timedelta(days=2),
            "updated_at": now - timedelta(days=2),
        },
    ]
    await db.workflows.insert_many(workflows)

    checks = []
    live_clients = [c for c in clients if c["environment"] == "live"]
    for i, c in enumerate(live_clients[:4]):
        outcome = "clear" if i % 2 == 0 else "attention"
        checks.append(
            {
                "id": new_id("chk_"),
                "org_id": org_id,
                "environment": "live",
                "client_id": c["id"],
                "client_name": c["name"],
                "type": "identity_check",
                "status": "complete",
                "outcome": outcome,
                "created_at": now - timedelta(hours=i + 1),
                "updated_at": now - timedelta(hours=i),
                "completed_at": now - timedelta(hours=i),
            }
        )
    test_clients = [c for c in clients if c["environment"] == "test"]
    for i, c in enumerate(test_clients[:2]):
        checks.append(
            {
                "id": new_id("chk_"),
                "org_id": org_id,
                "environment": "test",
                "client_id": c["id"],
                "client_name": c["name"],
                "type": "identity_check",
                "status": "complete",
                "outcome": "clear",
                "created_at": now - timedelta(hours=i + 1),
                "updated_at": now - timedelta(hours=i),
                "completed_at": now - timedelta(hours=i),
            }
        )
    await db.checks.insert_many(checks)

    await db.api_keys.insert_many(
        [
            {
                "id": new_id("key_"),
                "org_id": org_id,
                "access": "live",
                "kind": "api",
                "key": f"sk_live_{secrets.token_hex(16)}",
                "rate_limit": "10 requests per second",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": new_id("key_"),
                "org_id": org_id,
                "access": "sandbox",
                "kind": "api",
                "key": f"sk_test_{secrets.token_hex(16)}",
                "rate_limit": "5 requests per second",
                "created_at": now - timedelta(days=100),
            },
        ]
    )

    await db.webhooks.insert_many(
        [
            {
                "id": new_id("wh_"),
                "org_id": org_id,
                "url": "https://uat.example.com/api/v1/kyc/webhooks",
                "secret": f"whsec_{secrets.token_hex(12)}",
                "enabled": True,
                "events": ["check.completed", "check.failed", "check.updated", "check.monitoring.attention"],
                "updated_at": now - timedelta(days=3),
            },
            {
                "id": new_id("wh_"),
                "org_id": org_id,
                "url": "https://prod.example.com/api/v1/kyc/webhooks",
                "secret": f"whsec_{secrets.token_hex(12)}",
                "enabled": True,
                "events": ["check.completed", "check.failed", "check.updated"],
                "updated_at": now - timedelta(days=10),
            },
            {
                "id": new_id("wh_"),
                "org_id": org_id,
                "url": "https://dev.example.com/api/v1/kyc/webhooks",
                "secret": f"whsec_{secrets.token_hex(12)}",
                "enabled": False,
                "events": ["check.completed", "check.failed"],
                "updated_at": now - timedelta(days=12),
            },
        ]
    )

    events = []
    sample_types = [
        "check.completed",
        "check.completed.clear",
        "check.failed",
        "client.created",
        "workflow.session.completed",
    ]
    for i in range(25):
        et = sample_types[i % len(sample_types)]
        events.append(
            {
                "id": new_id("evt_"),
                "org_id": org_id,
                "type": et,
                "event_type": et,
                "resourceType": "checks" if et.startswith("check") else ("clients" if et.startswith("client") else "sessions"),
                "resource_type": "checks" if et.startswith("check") else ("clients" if et.startswith("client") else "sessions"),
                "payload": {"demo": True, "index": i},
                "status": "succeeded",
                "attempt": 1,
                "created_at": now - timedelta(hours=i),
                "createdAt": (now - timedelta(hours=i)).isoformat(),
            }
        )
    await db.events.insert_many(events)

    logs = []
    for i in range(30):
        logs.append(
            {
                "id": new_id("log_"),
                "org_id": org_id,
                "method": "POST" if i % 3 else "GET",
                "path": "/v1/checks" if i % 2 else "/v1/clients",
                "status_code": 200 if i % 5 else 400,
                "created_at": now - timedelta(hours=i * 2),
            }
        )
    await db.api_logs.insert_many(logs)


def serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None

    def convert(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [convert(v) for v in value]
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items() if k != "_id"}
        return value

    return convert({k: v for k, v in doc.items() if k != "_id"})
