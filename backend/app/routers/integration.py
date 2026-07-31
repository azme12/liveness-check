from __future__ import annotations

import math
import secrets
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.db import get_database
from app.deps import get_current_user
from app.schemas import AllowedIpCreate, WebhookCreate, WebhookUpdate
from app.services.seed import new_id, serialize, utcnow
from app.services.webhook_events import WEBHOOK_EVENT_TYPES, validate_events
from app.services.webhooks import emit_event

router = APIRouter(prefix="/integration", tags=["integration"])

Access = Literal["live", "sandbox"]
Kind = Literal["api"]


def _pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size)) if total else 1


def _access_from_env(environment: str) -> Access:
    if environment in {"test", "sandbox"}:
        return "sandbox"
    if environment == "live":
        return "live"
    raise HTTPException(status_code=400, detail="environment must be test or live")


def _key_prefix(access: Access, kind: Kind) -> str:
    return "sk_live_" if access == "live" else "sk_test_"


async def ensure_org_keys(org_id: str) -> None:
    """Make sure each org has secret API keys for sandbox and live."""
    db = get_database()
    now = utcnow()
    needed = [
        ("live", "api", "10 requests per second"),
        ("sandbox", "api", "5 requests per second"),
    ]
    for access, kind, rate in needed:
        filt: dict[str, Any] = {"org_id": org_id, "access": access}
        existing = await db.api_keys.find_one(
            {**filt, "$or": [{"kind": "api"}, {"kind": {"$exists": False}}]}
        )
        if existing:
            if "kind" not in existing:
                await db.api_keys.update_one({"id": existing["id"]}, {"$set": {"kind": "api"}})
            continue
        await db.api_keys.insert_one(
            {
                "id": new_id("key_"),
                "org_id": org_id,
                "access": access,
                "kind": kind,
                "key": f"{_key_prefix(access, kind)}{secrets.token_hex(16)}",
                "rate_limit": rate,
                "created_at": now,
            }
        )


@router.get("/api-keys")
async def api_keys(
    environment: str = Query("live", description="test or live"),
    user: dict = Depends(get_current_user),
):
    access = _access_from_env(environment)
    db = get_database()
    await ensure_org_keys(user["org_id"])
    filt: dict[str, Any] = {
        "org_id": user["org_id"],
        "access": access,
        "$or": [{"kind": "api"}, {"kind": {"$exists": False}}],
    }
    items = await db.api_keys.find(filt, {"_id": 0}).to_list(20)
    return {
        "items": [serialize(i) for i in items],
        "environment": "test" if access == "sandbox" else "live",
        "access": access,
    }


@router.post("/api-keys/{key_id}/refresh")
async def refresh_key(key_id: str, user: dict = Depends(get_current_user)):
    db = get_database()
    doc = await db.api_keys.find_one({"id": key_id, "org_id": user["org_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Key not found")
    access: Access = "live" if doc.get("access") == "live" else "sandbox"
    new_key = f"{_key_prefix(access, 'api')}{secrets.token_hex(16)}"
    await db.api_keys.update_one(
        {"id": key_id},
        {"$set": {"key": new_key, "kind": "api", "created_at": utcnow()}},
    )
    updated = await db.api_keys.find_one({"id": key_id}, {"_id": 0})
    return serialize(updated)


@router.get("/allowed-ips")
async def list_ips(user: dict = Depends(get_current_user)):
    items = await get_database().allowed_ips.find({"org_id": user["org_id"]}, {"_id": 0}).to_list(100)
    return {"items": [serialize(i) for i in items]}


@router.post("/allowed-ips")
async def add_ip(body: AllowedIpCreate, user: dict = Depends(get_current_user)):
    doc = {
        "id": new_id("ip_"),
        "org_id": user["org_id"],
        "cidr": body.cidr,
        "label": body.label,
        "created_at": utcnow(),
    }
    await get_database().allowed_ips.insert_one(doc)
    return serialize(doc)


@router.delete("/allowed-ips/{ip_id}")
async def delete_ip(ip_id: str, user: dict = Depends(get_current_user)):
    result = await get_database().allowed_ips.delete_one({"id": ip_id, "org_id": user["org_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/webhook-event-types")
async def webhook_event_types(_: dict = Depends(get_current_user)):
    return {"items": WEBHOOK_EVENT_TYPES}


@router.get("/webhooks")
async def list_webhooks(user: dict = Depends(get_current_user)):
    items = await get_database().webhooks.find({"org_id": user["org_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(50)
    return {"items": [serialize(i) for i in items]}


@router.get("/webhooks/{webhook_id}")
async def get_webhook(webhook_id: str, user: dict = Depends(get_current_user)):
    doc = await get_database().webhooks.find_one({"id": webhook_id, "org_id": user["org_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return serialize(doc)


@router.post("/webhooks")
async def create_webhook(body: WebhookCreate, user: dict = Depends(get_current_user)):
    if not body.url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Webhook URL must use HTTPS")
    try:
        events = validate_events(body.events)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    now = utcnow()
    secret = f"whsec_{secrets.token_hex(16)}"
    doc = {
        "id": new_id("wh_"),
        "org_id": user["org_id"],
        "url": body.url,
        "description": body.description or "",
        "secret": secret,
        "enabled": body.enabled,
        "events": events,
        "created_at": now,
        "updated_at": now,
        # ComplyCube-style aliases
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
    }
    await get_database().webhooks.insert_one(doc)
    # Secret only returned at creation (ComplyCube behaviour)
    return serialize(doc)


@router.patch("/webhooks/{webhook_id}")
async def update_webhook(webhook_id: str, body: WebhookUpdate, user: dict = Depends(get_current_user)):
    patch: dict = {}
    data = body.model_dump(exclude_unset=True)
    if "url" in data and data["url"] is not None:
        if not str(data["url"]).startswith("https://"):
            raise HTTPException(status_code=400, detail="Webhook URL must use HTTPS")
        patch["url"] = data["url"]
    if "description" in data:
        patch["description"] = data["description"] or ""
    if "enabled" in data and data["enabled"] is not None:
        patch["enabled"] = data["enabled"]
        if data["enabled"]:
            patch["disabled_reason"] = None
    if "events" in data and data["events"] is not None:
        try:
            patch["events"] = validate_events(data["events"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")
    now = utcnow()
    patch["updated_at"] = now
    patch["updatedAt"] = now.isoformat()
    result = await get_database().webhooks.find_one_and_update(
        {"id": webhook_id, "org_id": user["org_id"]},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0, "secret": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return serialize(result)


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, user: dict = Depends(get_current_user)):
    result = await get_database().webhooks.delete_one({"id": webhook_id, "org_id": user["org_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"ok": True}


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: str, user: dict = Depends(get_current_user)):
    wh = await get_database().webhooks.find_one({"id": webhook_id, "org_id": user["org_id"]}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    event = await emit_event(
        user["org_id"],
        "check.completed",
        {
            "id": new_id("chk_"),
            "status": "complete",
            "outcome": "clear",
            "note": "Trustanova test webhook delivery",
        },
        resource_type="checks",
    )
    return {"ok": True, "event": event}


@router.get("/events")
async def list_events(
    event_type: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    db = get_database()
    filt: dict = {"org_id": user["org_id"]}
    if event_type:
        filt["$or"] = [{"event_type": event_type}, {"type": event_type}]
    if status:
        filt["status"] = status
    total = await db.events.count_documents(filt)
    cursor = db.events.find(filt, {"_id": 0}).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    items = [serialize(i) for i in await cursor.to_list(page_size)]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": _pages(total, page_size)}


@router.get("/webhook-deliveries")
async def list_deliveries(
    webhook_id: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    db = get_database()
    filt: dict = {"org_id": user["org_id"]}
    if webhook_id:
        filt["webhook_id"] = webhook_id
    total = await db.webhook_deliveries.count_documents(filt)
    cursor = (
        db.webhook_deliveries.find(filt, {"_id": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize(i) for i in await cursor.to_list(page_size)]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": _pages(total, page_size)}


@router.get("/logs")
async def list_logs(
    methods: str = Query("POST,GET,DELETE"),
    only_errors: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    db = get_database()
    method_list = [m.strip().upper() for m in methods.split(",") if m.strip()]
    filt: dict = {"org_id": user["org_id"]}
    if method_list:
        filt["method"] = {"$in": method_list}
    if only_errors:
        filt["status_code"] = {"$gte": 400}
    total = await db.api_logs.count_documents(filt)
    cursor = db.api_logs.find(filt, {"_id": 0}).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    items = [serialize(i) for i in await cursor.to_list(page_size)]

    now = utcnow()
    series = []
    for i in range(12, -1, -1):
        start = now - __import__("datetime").timedelta(days=(i + 1) * 7)
        end = now - __import__("datetime").timedelta(days=i * 7)
        count = await db.api_logs.count_documents({"org_id": user["org_id"], "created_at": {"$gte": start, "$lt": end}})
        series.append({"label": start.strftime("%d %b"), "count": count})

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
        "series": series,
    }


@router.get("/mobile")
async def mobile_info(
    environment: str = Query("live"),
    user: dict = Depends(get_current_user),
):
    access = _access_from_env(environment)
    env_label = "test" if access == "sandbox" else "live"
    return {
        "org_id": user["org_id"],
        "environment": env_label,
        "message": "Create a session from a client page, then open the hosted /verify/{token} link on a phone.",
        "verify_url_pattern": "/verify/vfy_YOUR_TOKEN",
    }
