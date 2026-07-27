from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.db import get_database
from app.deps import get_current_user
from app.schemas import ClientBulkDelete, ClientCreate
from app.services.environment import environment_query, with_org_env
from app.services.seed import new_id, serialize, utcnow
from app.services.webhooks import (
    emit_check_lifecycle,
    emit_client_created,
    emit_client_deleted,
    emit_client_updated,
    emit_session_event,
)

router = APIRouter(tags=["dashboard"])


def _pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size)) if total else 1


@router.get("/overview")
async def overview(
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    org_id = user["org_id"]
    now = utcnow()
    base = with_org_env(org_id, environment)

    async def count_since(coll: str, days: int | None = None) -> int:
        q: dict = {**base}
        if days is not None:
            q["created_at"] = {"$gte": now - timedelta(days=days)}
        return await db[coll].count_documents(q)

    flagged = {
        "sessions": {
            "today": await count_since("sessions", 1),
            "d7": await count_since("sessions", 7),
            "d30": await count_since("sessions", 30),
            "d90": await count_since("sessions", 90),
            "over90": max(0, await count_since("sessions") - await count_since("sessions", 90)),
        },
        "checks": {
            "today": await count_since("checks", 1),
            "d7": await count_since("checks", 7),
            "d30": await count_since("checks", 30),
            "d90": await count_since("checks", 90),
            "over90": max(0, await count_since("checks") - await count_since("checks", 90)),
        },
    }

    # 12-month usage series
    usage = []
    for i in range(11, -1, -1):
        start = (now.replace(day=1) - timedelta(days=30 * i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i == 0:
            end = now
        else:
            end = (start + timedelta(days=32)).replace(day=1)
        identity = await db.checks.count_documents(
            {**base, "type": "identity_check", "created_at": {"$gte": start, "$lt": end}}
        )
        document = await db.checks.count_documents(
            {**base, "type": "document_check", "created_at": {"$gte": start, "$lt": end}}
        )
        aml = await db.checks.count_documents(
            {**base, "type": "standard_screening_check", "created_at": {"$gte": start, "$lt": end}}
        )
        usage.append(
            {
                "month": start.strftime("%b"),
                "identity_check": identity,
                "document_check": document,
                "extensive_aml": aml,
            }
        )

    persons = await db.clients.count_documents({**base, "type": "person"})
    companies = await db.clients.count_documents({**base, "type": "company"})
    return {
        "flagged": flagged,
        "usage": usage,
        "population": {"total": persons + companies, "persons": persons, "companies": companies},
        "environment": environment,
    }


@router.get("/clients")
async def list_clients(
    q: str = Query("", min_length=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    filt: dict = with_org_env(user["org_id"], environment)
    if len(q.strip()) >= 3:
        rx = re.compile(re.escape(q.strip()), re.I)
        filt["$and"] = [{"$or": [{"name": rx}, {"email": rx}, {"id": rx}]}]
    total = await db.clients.count_documents(filt)
    cursor = (
        db.clients.find(filt, {"_id": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize(doc) for doc in await cursor.to_list(page_size)]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
        "environment": environment,
    }


@router.post("/clients")
async def create_client(
    body: ClientCreate,
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    now = utcnow()
    if body.type == "company":
        name = body.company_name or "Company"
    else:
        name = f"{body.first_name or ''} {body.last_name or ''}".strip() or "Unnamed"
    doc = {
        "id": new_id("cli_"),
        "org_id": user["org_id"],
        "environment": environment,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "company_name": body.company_name,
        "name": name,
        "email": str(body.email) if body.email else None,
        "type": body.type,
        "risk": "low",
        "created_at": now,
    }
    await db.clients.insert_one(doc)
    await emit_client_created(user["org_id"], doc)
    return serialize(doc)


@router.patch("/clients/{client_id}")
async def update_client(client_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_database()
    allowed = {k: v for k, v in body.items() if k in {"first_name", "last_name", "company_name", "email", "risk", "type", "name"}}
    if "first_name" in allowed or "last_name" in allowed:
        existing = await db.clients.find_one({"id": client_id, "org_id": user["org_id"]})
        if not existing:
            raise HTTPException(status_code=404, detail="Client not found")
        first = allowed.get("first_name", existing.get("first_name"))
        last = allowed.get("last_name", existing.get("last_name"))
        allowed["name"] = f"{first or ''} {last or ''}".strip() or existing.get("name")
    allowed["updated_at"] = utcnow()
    result = await db.clients.find_one_and_update(
        {"id": client_id, "org_id": user["org_id"]},
        {"$set": allowed},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    await emit_client_updated(user["org_id"], result)
    return serialize(result)


@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: str,
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    result = await db.clients.delete_one({**with_org_env(user["org_id"], environment), "id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    await emit_client_deleted(user["org_id"], client_id)
    return {"ok": True}


@router.post("/clients/bulk-delete")
async def bulk_delete_clients(
    body: ClientBulkDelete,
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    ids = list(dict.fromkeys(body.ids))
    found_docs = await db.clients.find(
        {**with_org_env(user["org_id"], environment), "id": {"$in": ids}},
        {"id": 1, "_id": 0},
    ).to_list(len(ids))
    found = [doc["id"] for doc in found_docs]
    if not found:
        raise HTTPException(status_code=404, detail="No matching clients")
    result = await db.clients.delete_many(
        {**with_org_env(user["org_id"], environment), "id": {"$in": found}}
    )
    for cid in found:
        await emit_client_deleted(user["org_id"], cid)
    return {"ok": True, "deleted": result.deleted_count, "ids": found}


@router.get("/sessions")
async def list_sessions(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    filt: dict = with_org_env(user["org_id"], environment)
    if len(q.strip()) >= 3:
        rx = re.compile(re.escape(q.strip()), re.I)
        filt["$and"] = [{"$or": [{"client_name": rx}, {"id": rx}]}]
    total = await db.sessions.count_documents(filt)
    cursor = (
        db.sessions.find(filt, {"_id": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize(doc) for doc in await cursor.to_list(page_size)]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
        "environment": environment,
    }


@router.post("/sessions")
async def create_session(
    body: dict,
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    client_id = body.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id required")
    client = await db.clients.find_one(
        {**with_org_env(user["org_id"], environment), "id": client_id},
        {"_id": 0},
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    now = utcnow()
    doc = {
        "id": new_id("ses_"),
        "org_id": user["org_id"],
        "environment": environment,
        "client_id": client_id,
        "client_name": client.get("name"),
        "workflow_id": body.get("workflow_id") or "standard_kyc",
        "status": "started",
        "created_at": now,
        "updated_at": now,
    }
    await db.sessions.insert_one(doc)
    await emit_session_event(user["org_id"], doc, "workflow.session.started")
    return serialize(doc)


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_database()
    status = body.get("status")
    patch = {"updated_at": utcnow()}
    if status:
        patch["status"] = status
    result = await db.sessions.find_one_and_update(
        {"id": session_id, "org_id": user["org_id"]},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    status_map = {
        "cancelled": "workflow.session.cancelled",
        "processing": "workflow.session.processing",
        "completed": "workflow.session.completed",
        "abandoned": "workflow.session.abandoned",
        "updated": "workflow.session.updated",
    }
    if status in status_map:
        await emit_session_event(user["org_id"], result, status_map[status])
    elif status:
        await emit_session_event(user["org_id"], result, "workflow.session.updated")
    return serialize(result)


@router.post("/checks")
async def create_check(
    body: dict,
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    """Create a dashboard check and emit check.pending (then complete for demo)."""
    db = get_database()
    client_id = body.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id required")
    client = await db.clients.find_one(
        {**with_org_env(user["org_id"], environment), "id": client_id},
        {"_id": 0},
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    now = utcnow()
    outcome = (body.get("outcome") or "clear").lower()
    doc = {
        "id": new_id("chk_"),
        "org_id": user["org_id"],
        "environment": environment,
        "client_id": client_id,
        "client_name": client.get("name"),
        "type": body.get("type") or "identity_check",
        "status": "pending",
        "outcome": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.checks.insert_one(doc)
    await emit_check_lifecycle(user["org_id"], doc, "check.pending")

    # Complete immediately for dashboard demo flows
    completed = {
        **doc,
        "status": "complete",
        "outcome": outcome,
        "updated_at": utcnow(),
        "completed_at": utcnow(),
    }
    await db.checks.update_one({"id": doc["id"]}, {"$set": completed})
    await emit_check_lifecycle(user["org_id"], completed, "check.completed")
    await emit_check_lifecycle(user["org_id"], completed, "check.updated")
    return serialize(completed)


@router.get("/checks")
async def list_checks(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    filt: dict = with_org_env(user["org_id"], environment)
    if len(q.strip()) >= 3:
        rx = re.compile(re.escape(q.strip()), re.I)
        filt["$and"] = [{"$or": [{"client_name": rx}, {"id": rx}]}]
    total = await db.checks.count_documents(filt)
    cursor = (
        db.checks.find(filt, {"_id": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize(doc) for doc in await cursor.to_list(page_size)]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
        "environment": environment,
    }


@router.get("/workflows")
async def list_workflows(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    filt: dict = with_org_env(user["org_id"], environment)
    if len(q.strip()) >= 3:
        rx = re.compile(re.escape(q.strip()), re.I)
        filt["$and"] = [{"$or": [{"name": rx}, {"id": rx}]}]
    total = await db.workflows.count_documents(filt)
    cursor = (
        db.workflows.find(filt, {"_id": 0})
        .sort("updated_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize(doc) for doc in await cursor.to_list(page_size)]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
        "environment": environment,
    }


@router.post("/workflows")
async def create_workflow(
    body: dict,
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    now = utcnow()
    doc = {
        "id": new_id("wf_"),
        "org_id": user["org_id"],
        "environment": environment,
        "name": body.get("name") or "Untitled workflow",
        "description": body.get("description") or "",
        "status": "active",
        "version": 1,
        "steps": body.get("steps")
        or [{"type": "identity_check", "label": "Identity Check"}],
        "created_at": now,
        "updated_at": now,
    }
    await db.workflows.insert_one(doc)
    return serialize(doc)


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, user: dict = Depends(get_current_user)):
    db = get_database()
    doc = await db.workflows.find_one({"id": workflow_id, "org_id": user["org_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return serialize(doc)


@router.patch("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_database()
    patch = {k: v for k, v in body.items() if k in {"name", "description", "status", "steps", "version"} and v is not None}
    patch["updated_at"] = utcnow()
    result = await db.workflows.find_one_and_update(
        {"id": workflow_id, "org_id": user["org_id"]},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return serialize(result)
