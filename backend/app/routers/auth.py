from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo import ReturnDocument

from app.db import get_database
from app.deps import get_current_user
from app.schemas import (
    ActivationBusinessAddress,
    ActivationBusinessDetails,
    ActivationIdentity,
    ActivationUsage,
    ChangePasswordRequest,
    LoginRequest,
    NotificationPrefsUpdate,
    ProfileUpdate,
    SignupRequest,
    TokenResponse,
)
from app.security import create_access_token, hash_password, verify_password
from app.services.seed import ensure_org_defaults, ensure_user_account_defaults, new_id, serialize, utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


def _split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


@router.post("/signup", response_model=TokenResponse)
async def signup(body: SignupRequest):
    db = get_database()
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    now = utcnow()
    org_id = new_id("org_")
    user_id = new_id("usr_")
    first, last = _split_name(body.full_name)
    await db.organizations.insert_one(
        {
            "id": org_id,
            "name": body.organization_name,
            "live_enabled": False,
            "activation": {"step": 1, "completed": False},
            "created_at": now,
        }
    )
    user = {
        "id": user_id,
        "email": body.email.lower(),
        "full_name": body.full_name,
        "first_name": first,
        "last_name": last,
        "password_hash": hash_password(body.password),
        "org_id": org_id,
        "role": "owner",
        "theme": "system",
        "notification_prefs": {"email_checks": True, "email_webhooks": True, "in_app": True},
        "created_at": now,
    }
    await db.users.insert_one(user)
    # Create empty sandbox/live API keys for the new org (stored in Mongo).
    from app.routers.integration import ensure_org_keys

    await ensure_org_keys(org_id)
    token = create_access_token(user_id, {"org_id": org_id})
    safe = serialize({k: v for k, v in user.items() if k != "password_hash"})
    return TokenResponse(access_token=token, user=safe or {})


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    db = get_database()
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(user["id"], {"org_id": user["org_id"]})
    safe = serialize({k: v for k, v in user.items() if k != "password_hash" and k != "_id"})
    return TokenResponse(access_token=token, user=safe or {})


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    db = get_database()
    doc = await db.users.find_one({"id": user["id"]})
    if not doc or not verify_password(body.current_password, doc["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": utcnow()}},
    )
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    db = get_database()
    user = await ensure_user_account_defaults(user)
    await ensure_org_defaults(user["org_id"])
    org = await db.organizations.find_one({"id": user["org_id"]}, {"_id": 0})
    safe = serialize({k: v for k, v in user.items() if k not in {"password_hash", "_id"}})
    org_safe = serialize(org) or {}
    return {
        "user": safe,
        "organization": org_safe,
        "live_enabled": bool(org_safe.get("live_enabled")),
        "activation": org_safe.get("activation") or {"step": 1, "completed": False},
        "notification_prefs": (safe or {}).get("notification_prefs")
        or {"email_checks": True, "email_webhooks": True, "in_app": True},
    }


@router.get("/activation")
async def get_activation(user: dict = Depends(get_current_user)):
    org = await get_database().organizations.find_one({"id": user["org_id"]}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        "live_enabled": bool(org.get("live_enabled")),
        "activation": org.get("activation")
        or {"step": 1, "completed": False},
        "organization_name": org.get("name"),
    }


@router.post("/activation/business-details")
async def activation_business_details(body: ActivationBusinessDetails, user: dict = Depends(get_current_user)):
    db = get_database()
    org = await db.organizations.find_one({"id": user["org_id"]})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    activation = {**(org.get("activation") or {}), "step": 2, "business_details": body.model_dump(), "completed": False}
    await db.organizations.update_one(
        {"id": user["org_id"]},
        {"$set": {"activation": activation, "name": body.legal_company_name, "updated_at": utcnow()}},
    )
    return {"ok": True, "activation": activation}


@router.post("/activation/business-address")
async def activation_business_address(body: ActivationBusinessAddress, user: dict = Depends(get_current_user)):
    db = get_database()
    org = await db.organizations.find_one({"id": user["org_id"]})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    activation = {**(org.get("activation") or {}), "step": 3, "business_address": body.model_dump(), "completed": False}
    await db.organizations.update_one(
        {"id": user["org_id"]},
        {"$set": {"activation": activation, "updated_at": utcnow()}},
    )
    return {"ok": True, "activation": activation}


@router.post("/activation/usage")
async def activation_usage(body: ActivationUsage, user: dict = Depends(get_current_user)):
    db = get_database()
    org = await db.organizations.find_one({"id": user["org_id"]})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    activation = {**(org.get("activation") or {}), "step": 4, "usage": body.model_dump(), "completed": False}
    await db.organizations.update_one(
        {"id": user["org_id"]},
        {"$set": {"activation": activation, "updated_at": utcnow()}},
    )
    return {"ok": True, "activation": activation}


@router.post("/activation/identity")
async def activation_identity(body: ActivationIdentity, user: dict = Depends(get_current_user)):
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="Confirmation required")
    db = get_database()
    org = await db.organizations.find_one({"id": user["org_id"]})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    activation = {
        **(org.get("activation") or {}),
        "step": 4,
        "identity": body.model_dump(),
        "completed": True,
        "completed_at": utcnow().isoformat(),
    }
    await db.organizations.update_one(
        {"id": user["org_id"]},
        {"$set": {"activation": activation, "live_enabled": True, "updated_at": utcnow()}},
    )
    return {"ok": True, "live_enabled": True, "activation": serialize(activation)}


@router.patch("/profile")
async def update_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    db = get_database()
    patch: dict = {"updated_at": utcnow()}
    data = body.model_dump(exclude_unset=True)

    if "email" in data and data["email"]:
        email = str(data["email"]).lower()
        clash = await db.users.find_one({"email": email, "id": {"$ne": user["id"]}})
        if clash:
            raise HTTPException(status_code=409, detail="Email already in use")
        patch["email"] = email

    first = data.get("first_name")
    last = data.get("last_name")
    if "full_name" in data and data["full_name"]:
        first, last = _split_name(data["full_name"])
        patch["full_name"] = data["full_name"]
        patch["first_name"] = first
        patch["last_name"] = last
    else:
        if first is not None:
            patch["first_name"] = first
        if last is not None:
            patch["last_name"] = last
        if first is not None or last is not None:
            existing = await db.users.find_one({"id": user["id"]}) or {}
            f = patch.get("first_name", existing.get("first_name") or "")
            l = patch.get("last_name", existing.get("last_name") or "")
            patch["full_name"] = f"{f} {l}".strip() or existing.get("full_name") or "User"

    updated = await db.users.find_one_and_update(
        {"id": user["id"]},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0, "password_hash": 0},
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": serialize(updated)}


@router.patch("/notification-prefs")
async def update_notification_prefs(body: NotificationPrefsUpdate, user: dict = Depends(get_current_user)):
    db = get_database()
    current = user.get("notification_prefs") or {"email_checks": True, "email_webhooks": True, "in_app": True}
    patch = {**current, **{k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}}
    await db.users.update_one({"id": user["id"]}, {"$set": {"notification_prefs": patch, "updated_at": utcnow()}})
    return {"notification_prefs": patch}


@router.patch("/theme")
async def update_theme(body: dict, user: dict = Depends(get_current_user)):
    theme = body.get("theme")
    if theme not in {"light", "dark", "system"}:
        raise HTTPException(status_code=400, detail="theme must be light, dark, or system")
    await get_database().users.update_one({"id": user["id"]}, {"$set": {"theme": theme, "updated_at": utcnow()}})
    return {"theme": theme}


@router.get("/notifications")
async def list_notifications(
    q: str = "",
    unread: bool = False,
    days: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    from datetime import timedelta
    import math
    import re

    db = get_database()
    filt: dict = {"user_id": user["id"]}
    if unread:
        filt["read"] = False
    if days:
        filt["created_at"] = {"$gte": utcnow() - timedelta(days=days)}
    if len(q.strip()) >= 2:
        rx = re.compile(re.escape(q.strip()), re.I)
        filt["$or"] = [{"title": rx}, {"body": rx}, {"type": rx}]
    total = await db.notifications.count_documents(filt)
    cursor = (
        db.notifications.find(filt, {"_id": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize(i) for i in await cursor.to_list(page_size)]
    unread_count = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    pages = max(1, math.ceil(total / page_size)) if total else 1
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages, "unread_count": unread_count}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user)):
    result = await get_database().notifications.update_one(
        {"id": notification_id, "user_id": user["id"]},
        {"$set": {"read": True, "read_at": utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await get_database().notifications.update_many(
        {"user_id": user["id"], "read": False},
        {"$set": {"read": True, "read_at": utcnow()}},
    )
    return {"ok": True}
