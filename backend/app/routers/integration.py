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
Kind = Literal["api", "web_sdk"]


def _pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size)) if total else 1


def _access_from_env(environment: str) -> Access:
    if environment in {"test", "sandbox"}:
        return "sandbox"
    if environment == "live":
        return "live"
    raise HTTPException(status_code=400, detail="environment must be test or live")


def _key_prefix(access: Access, kind: Kind) -> str:
    if kind == "web_sdk":
        return "pk_live_" if access == "live" else "pk_test_"
    return "sk_live_" if access == "live" else "sk_test_"


async def ensure_org_keys(org_id: str) -> None:
    """Make sure each org has secret + web SDK keys for sandbox and live."""
    db = get_database()
    now = utcnow()
    needed = [
        ("live", "api", "10 requests per second"),
        ("sandbox", "api", "5 requests per second"),
        ("live", "web_sdk", "browser / SDK only"),
        ("sandbox", "web_sdk", "browser / SDK only"),
    ]
    for access, kind, rate in needed:
        filt: dict[str, Any] = {"org_id": org_id, "access": access}
        # Older seeds had no kind — treat missing kind as api
        if kind == "api":
            existing = await db.api_keys.find_one(
                {**filt, "$or": [{"kind": "api"}, {"kind": {"$exists": False}}]}
            )
        else:
            existing = await db.api_keys.find_one({**filt, "kind": kind})
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
                "key": f"{_key_prefix(access, kind)}{secrets.token_hex(16)}",  # type: ignore[arg-type]
                "rate_limit": rate,
                "created_at": now,
            }
        )


@router.get("/api-keys")
async def api_keys(
    environment: str = Query("live", description="test or live"),
    kind: str = Query("api", description="api or web_sdk"),
    user: dict = Depends(get_current_user),
):
    access = _access_from_env(environment)
    if kind not in {"api", "web_sdk", "all"}:
        raise HTTPException(status_code=400, detail="kind must be api, web_sdk, or all")
    db = get_database()
    await ensure_org_keys(user["org_id"])
    filt: dict[str, Any] = {"org_id": user["org_id"], "access": access}
    if kind == "api":
        filt["$or"] = [{"kind": "api"}, {"kind": {"$exists": False}}]
    elif kind == "web_sdk":
        filt["kind"] = "web_sdk"
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
    kind: Kind = "web_sdk" if doc.get("kind") == "web_sdk" else "api"
    access: Access = "live" if doc.get("access") == "live" else "sandbox"
    new_key = f"{_key_prefix(access, kind)}{secrets.token_hex(16)}"
    await db.api_keys.update_one(
        {"id": key_id},
        {"$set": {"key": new_key, "kind": kind, "created_at": utcnow()}},
    )
    updated = await db.api_keys.find_one({"id": key_id}, {"_id": 0})
    return serialize(updated)


@router.get("/sdk")
async def sdk_credentials(
    environment: str = Query("live"),
    user: dict = Depends(get_current_user),
):
    """Return API + Web SDK credentials for the selected environment."""
    access = _access_from_env(environment)
    env_label = "test" if access == "sandbox" else "live"
    db = get_database()
    await ensure_org_keys(user["org_id"])

    api_key = await db.api_keys.find_one(
        {
            "org_id": user["org_id"],
            "access": access,
            "$or": [{"kind": "api"}, {"kind": {"$exists": False}}],
        },
        {"_id": 0},
    )
    web_key = await db.api_keys.find_one(
        {"org_id": user["org_id"], "access": access, "kind": "web_sdk"},
        {"_id": 0},
    )
    api_secret = (api_key or {}).get("key") or ""
    publishable = (web_key or {}).get("key") or ""
    snippet = (
        f"<!-- 1) Create a verification session in the dashboard (Start verification → Use SDK token),\n"
        f"     or via your server with the secret sk_* key. You get a token like vfy_.... -->\n"
        f'<div id="trustanova-root"></div>\n'
        f'<script src="/sdk/v1.js"></script>\n'
        f"<script>\n"
        f"  const trustanova = new Trustanova({{\n"
        f"    apiKey: '{publishable}',\n"
        f"    environment: '{env_label}',\n"
        f"  }});\n\n"
        f"  // Pass the session token from Start verification (SDK method)\n"
        f"  trustanova.mount('#trustanova-root', {{\n"
        f"    token: 'vfy_your_session_token',\n"
        f"  }});\n"
        f"</script>"
    )
    return {
        "environment": env_label,
        "access": access,
        "api_key": serialize(api_key),
        "web_sdk_key": serialize(web_key),
        "snippet": snippet,
        "mobile": {
            "qr_payload": f"trustanova://link?org={user['org_id']}&env={env_label}&pk={publishable}",
            "deeplink": f"trustanova://link?org={user['org_id']}&env={env_label}",
        },
        "notes": {
            "api": "Use the secret sk_* key only on your server (X-Api-Key).",
            "web_sdk": "Load /sdk/v1.js in the browser with your public pk_* key, then mount with a session token from Start verification (SDK method).",
        },
    }


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
    await ensure_org_keys(user["org_id"])
    web_key = await get_database().api_keys.find_one(
        {"org_id": user["org_id"], "access": access, "kind": "web_sdk"},
        {"_id": 0},
    )
    pk = (web_key or {}).get("key") or ""
    return {
        "org_id": user["org_id"],
        "environment": env_label,
        "web_sdk_key": serialize(web_key),
        "qr_payload": f"trustanova://link?org={user['org_id']}&env={env_label}&pk={pk}",
        "message": f"Scan to link a device using the {env_label} Web/Mobile SDK key.",
    }
