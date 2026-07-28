from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument

from app.db import get_database
from app.deps import get_current_user
from app.schemas import ClientBulkDelete, ClientCreate, WorkflowCreate, WorkflowVersionUpdate
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


def _make_version(
    *,
    version: int,
    description: str = "",
    status: str = "active",
    steps: list | None = None,
    now: datetime | None = None,
) -> dict:
    ts = now or utcnow()
    return {
        "id": new_id("wfv_"),
        "version": version,
        "description": description,
        "status": status,
        "steps": steps
        or [{"type": "identity_check", "label": "Identity Check"}],
        "created_at": ts,
        "updated_at": ts,
    }


def _ensure_versions(doc: dict) -> dict:
    """Backfill legacy workflows that only have top-level steps/version."""
    if doc.get("versions"):
        return doc
    now = doc.get("updated_at") or doc.get("created_at") or utcnow()
    version = int(doc.get("version") or 1)
    status = doc.get("status") if doc.get("status") in {"active", "inactive"} else "active"
    v = {
        "id": new_id("wfv_"),
        "version": version,
        "description": doc.get("description") or "",
        "status": status if status == "active" else "inactive",
        "steps": doc.get("steps")
        or [{"type": "identity_check", "label": "Identity Check"}],
        "created_at": doc.get("created_at") or now,
        "updated_at": now,
    }
    doc = {**doc, "versions": [v]}
    return doc


def _active_version(doc: dict) -> dict | None:
    versions = doc.get("versions") or []
    for v in versions:
        if v.get("status") == "active":
            return v
    return versions[0] if versions else None


def _workflow_list_item(doc: dict) -> dict:
    doc = _ensure_versions(doc)
    active = _active_version(doc)
    out = serialize(doc)
    out["status"] = "active" if active and active.get("status") == "active" else "inactive"
    out["version"] = active.get("version") if active else doc.get("version") or 1
    out["steps"] = active.get("steps") if active else doc.get("steps") or []
    out["version_count"] = len(doc.get("versions") or [])
    return out


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

    # Run flagged counters in parallel (was ~12 sequential awaits).
    (
        s_today,
        s_d7,
        s_d30,
        s_d90,
        s_all,
        c_today,
        c_d7,
        c_d30,
        c_d90,
        c_all,
        persons,
        companies,
    ) = await asyncio.gather(
        count_since("sessions", 1),
        count_since("sessions", 7),
        count_since("sessions", 30),
        count_since("sessions", 90),
        count_since("sessions"),
        count_since("checks", 1),
        count_since("checks", 7),
        count_since("checks", 30),
        count_since("checks", 90),
        count_since("checks"),
        db.clients.count_documents({**base, "type": "person"}),
        db.clients.count_documents({**base, "type": "company"}),
    )

    flagged = {
        "sessions": {
            "today": s_today,
            "d7": s_d7,
            "d30": s_d30,
            "d90": s_d90,
            "over90": max(0, s_all - s_d90),
        },
        "checks": {
            "today": c_today,
            "d7": c_d7,
            "d30": c_d30,
            "d90": c_d90,
            "over90": max(0, c_all - c_d90),
        },
    }

    # 12-month usage — parallelize each month's 3 counts
    month_ranges: list[tuple[datetime, datetime, str]] = []
    for i in range(11, -1, -1):
        start = (now.replace(day=1) - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if i == 0:
            end = now
        else:
            end = (start + timedelta(days=32)).replace(day=1)
        month_ranges.append((start, end, start.strftime("%b")))

    async def month_counts(start: datetime, end: datetime, label: str) -> dict:
        identity, document, aml = await asyncio.gather(
            db.checks.count_documents(
                {**base, "type": "identity_check", "created_at": {"$gte": start, "$lt": end}}
            ),
            db.checks.count_documents(
                {**base, "type": "document_check", "created_at": {"$gte": start, "$lt": end}}
            ),
            db.checks.count_documents(
                {
                    **base,
                    "type": "standard_screening_check",
                    "created_at": {"$gte": start, "$lt": end},
                }
            ),
        )
        return {
            "month": label,
            "identity_check": identity,
            "document_check": document,
            "extensive_aml": aml,
        }

    usage = await asyncio.gather(
        *[month_counts(start, end, label) for start, end, label in month_ranges]
    )

    return {
        "flagged": flagged,
        "usage": list(usage),
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
        parts = [body.first_name, body.middle_name, body.last_name]
        name = " ".join(p for p in parts if p).strip() or "Unnamed"
    doc = {
        "id": new_id("cli_"),
        "org_id": user["org_id"],
        "environment": environment,
        "first_name": body.first_name,
        "middle_name": body.middle_name,
        "last_name": body.last_name,
        "company_name": body.company_name,
        "name": name,
        "email": str(body.email) if body.email else None,
        "mobile": body.mobile,
        "nationality": body.nationality,
        "date_of_birth": body.date_of_birth,
        "external_id": body.external_id or new_id("ext"),
        "type": body.type,
        "risk": "low",
        "created_at": now,
        "updated_at": now,
    }
    await db.clients.insert_one(doc)
    await emit_client_created(user["org_id"], doc)
    return serialize(doc)


@router.get("/clients/{client_id}")
async def get_client(
    client_id: str,
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    doc = await db.clients.find_one(
        {**with_org_env(user["org_id"], environment), "id": client_id},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Client not found")
    checks = await db.checks.count_documents(
        {**with_org_env(user["org_id"], environment), "client_id": client_id}
    )
    sessions = await db.sessions.count_documents(
        {**with_org_env(user["org_id"], environment), "client_id": client_id}
    )
    documents = await db.documents.count_documents({"client_id": client_id})
    out = serialize(doc)
    out["counts"] = {"checks": checks, "sessions": sessions, "documents": documents}
    return out


@router.get("/clients/{client_id}/checks")
async def client_checks(
    client_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    client = await db.clients.find_one(
        {**with_org_env(user["org_id"], environment), "id": client_id},
        {"_id": 0},
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    filt = {**with_org_env(user["org_id"], environment), "client_id": client_id}
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
    }


@router.get("/clients/{client_id}/sessions")
async def client_sessions(
    client_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    client = await db.clients.find_one(
        {**with_org_env(user["org_id"], environment), "id": client_id},
        {"_id": 0},
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    filt = {**with_org_env(user["org_id"], environment), "client_id": client_id}
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
    }


@router.get("/clients/{client_id}/documents")
async def client_documents(
    client_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    client = await db.clients.find_one(
        {**with_org_env(user["org_id"], environment), "id": client_id},
        {"_id": 0},
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    filt = {"client_id": client_id}
    total = await db.documents.count_documents(filt)
    cursor = (
        db.documents.find(filt, {"_id": 0})
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
    }


@router.patch("/clients/{client_id}")
async def update_client(client_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_database()
    allowed = {
        k: v
        for k, v in body.items()
        if k
        in {
            "first_name",
            "middle_name",
            "last_name",
            "company_name",
            "email",
            "mobile",
            "nationality",
            "date_of_birth",
            "external_id",
            "risk",
            "type",
            "name",
        }
    }
    if any(k in allowed for k in ("first_name", "middle_name", "last_name")):
        existing = await db.clients.find_one({"id": client_id, "org_id": user["org_id"]})
        if not existing:
            raise HTTPException(status_code=404, detail="Client not found")
        first = allowed.get("first_name", existing.get("first_name"))
        middle = allowed.get("middle_name", existing.get("middle_name"))
        last = allowed.get("last_name", existing.get("last_name"))
        allowed["name"] = " ".join(p for p in (first, middle, last) if p).strip() or existing.get("name")
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
    raw = await cursor.to_list(page_size)
    items = [_workflow_list_item(doc) for doc in raw]
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
    body: WorkflowCreate,
    user: dict = Depends(get_current_user),
    environment: str = Depends(environment_query),
):
    db = get_database()
    now = utcnow()
    steps = body.steps or [{"type": "identity_check", "label": "Identity Check"}]
    version = _make_version(
        version=1,
        description=body.description or "",
        status="active",
        steps=steps,
        now=now,
    )
    doc = {
        "id": new_id("wf_"),
        "org_id": user["org_id"],
        "environment": environment,
        "name": body.name.strip() or "Untitled workflow",
        "description": body.description or "",
        "status": "active",
        "version": 1,
        "steps": steps,
        "versions": [version],
        "created_at": now,
        "updated_at": now,
    }
    await db.workflows.insert_one(doc)
    return serialize(_ensure_versions(doc))


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, user: dict = Depends(get_current_user)):
    db = get_database()
    doc = await db.workflows.find_one({"id": workflow_id, "org_id": user["org_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Workflow not found")
    ensured = _ensure_versions(doc)
    if not doc.get("versions"):
        await db.workflows.update_one(
            {"id": workflow_id, "org_id": user["org_id"]},
            {"$set": {"versions": ensured["versions"]}},
        )
    out = serialize(ensured)
    out["versions"] = [serialize(v) for v in ensured.get("versions") or []]
    out["versions"].sort(key=lambda v: int(v.get("version") or 0), reverse=True)
    return out


@router.patch("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_database()
    patch = {
        k: v
        for k, v in body.items()
        if k in {"name", "description", "status"} and v is not None
    }
    patch["updated_at"] = utcnow()
    result = await db.workflows.find_one_and_update(
        {"id": workflow_id, "org_id": user["org_id"]},
        {"$set": patch},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return serialize(_ensure_versions(result))


@router.post("/workflows/{workflow_id}/versions")
async def create_workflow_version(
    workflow_id: str,
    body: dict | None = None,
    user: dict = Depends(get_current_user),
):
    db = get_database()
    body = body or {}
    doc = await db.workflows.find_one({"id": workflow_id, "org_id": user["org_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Workflow not found")
    ensured = _ensure_versions(doc)
    versions = list(ensured.get("versions") or [])
    next_num = max((int(v.get("version") or 0) for v in versions), default=0) + 1
    source = None
    source_id = body.get("from_version_id")
    if source_id:
        source = next((v for v in versions if v.get("id") == source_id), None)
    if source is None:
        source = _active_version(ensured) or (versions[0] if versions else None)
    now = utcnow()
    # New versions start inactive (ComplyCube-style); activate explicitly
    new_v = _make_version(
        version=next_num,
        description=body.get("description")
        or (source.get("description") if source else ensured.get("description") or ""),
        status="inactive",
        steps=body.get("steps")
        or (source.get("steps") if source else [{"type": "identity_check", "label": "Identity Check"}]),
        now=now,
    )
    versions.append(new_v)
    await db.workflows.update_one(
        {"id": workflow_id, "org_id": user["org_id"]},
        {
            "$set": {
                "versions": versions,
                "version": next_num,
                "updated_at": now,
            }
        },
    )
    return serialize(new_v)


@router.get("/workflows/{workflow_id}/versions/{version_id}")
async def get_workflow_version(
    workflow_id: str,
    version_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_database()
    doc = await db.workflows.find_one({"id": workflow_id, "org_id": user["org_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Workflow not found")
    ensured = _ensure_versions(doc)
    version = next((v for v in ensured.get("versions") or [] if v.get("id") == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    return {
        "workflow": {
            "id": ensured["id"],
            "name": ensured.get("name"),
            "description": ensured.get("description"),
            "status": ensured.get("status"),
        },
        "version": serialize(version),
    }


@router.patch("/workflows/{workflow_id}/versions/{version_id}")
async def update_workflow_version(
    workflow_id: str,
    version_id: str,
    body: WorkflowVersionUpdate,
    user: dict = Depends(get_current_user),
):
    db = get_database()
    doc = await db.workflows.find_one({"id": workflow_id, "org_id": user["org_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Workflow not found")
    ensured = _ensure_versions(doc)
    versions = list(ensured.get("versions") or [])
    idx = next((i for i, v in enumerate(versions) if v.get("id") == version_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    now = utcnow()
    updated = {**versions[idx]}
    if body.description is not None:
        updated["description"] = body.description
    if body.steps is not None:
        updated["steps"] = body.steps
    if body.status is not None:
        updated["status"] = body.status
        if body.status == "active":
            for i, v in enumerate(versions):
                if i != idx:
                    versions[i] = {**v, "status": "inactive", "updated_at": now}
    updated["updated_at"] = now
    versions[idx] = updated

    active = next((v for v in versions if v.get("status") == "active"), None)
    top_patch: dict = {
        "versions": versions,
        "updated_at": now,
        "status": "active" if active else "inactive",
    }
    if active:
        top_patch["version"] = active.get("version")
        top_patch["steps"] = active.get("steps")
        top_patch["description"] = active.get("description") or ensured.get("description") or ""

    await db.workflows.update_one(
        {"id": workflow_id, "org_id": user["org_id"]},
        {"$set": top_patch},
    )
    return serialize(updated)
