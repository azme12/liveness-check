"""Webhook emit + delivery (ComplyCube-compatible behaviour)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import timedelta
from typing import Any

import httpx

from app.db import get_database
from app.services.seed import new_id, serialize, utcnow
from app.services.webhook_events import (
    MAX_ATTEMPTS,
    RETRY_DELAYS_SECONDS,
    resource_type_for_event,
)

logger = logging.getLogger(__name__)

_retry_task: asyncio.Task | None = None


def _sign(secret: str, timestamp: int, body: str) -> str:
    payload = f"{timestamp}.{body}".encode()
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _webhook_matches(webhook_events: list[str], event_type: str) -> bool:
    if "*" in webhook_events:
        return True
    if event_type in webhook_events:
        return True
    # Prefix subscriptions e.g. check.completed matches check.completed.clear if subscribed to check.completed
    # ComplyCube lists specific types; exact match is enough. Also allow parent:
    parts = event_type.split(".")
    for i in range(len(parts) - 1, 0, -1):
        parent = ".".join(parts[:i])
        if parent in webhook_events:
            return True
    return False


async def emit_event(
    org_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    resource_type: str | None = None,
) -> dict[str, Any]:
    """Create an event and dispatch to matching enabled webhooks."""
    db = get_database()
    now = utcnow()
    rtype = resource_type or resource_type_for_event(event_type)
    event = {
        "id": new_id("evt_"),
        "org_id": org_id,
        "type": event_type,
        "event_type": event_type,  # alias for existing UI filters
        "resourceType": rtype,
        "resource_type": rtype,
        "payload": payload,
        "created_at": now,
        "createdAt": now.isoformat(),
    }
    await db.events.insert_one(event)

    webhooks = await db.webhooks.find({"org_id": org_id, "enabled": True}, {"_id": 0}).to_list(200)
    for wh in webhooks:
        if not _webhook_matches(wh.get("events") or [], event_type):
            continue
        await _queue_delivery(wh, event, attempt=1)

    return serialize(event) or event


async def _queue_delivery(webhook: dict[str, Any], event: dict[str, Any], attempt: int) -> None:
    db = get_database()
    delivery = {
        "id": new_id("dlv_"),
        "org_id": webhook["org_id"],
        "webhook_id": webhook["id"],
        "event_id": event["id"],
        "event_type": event["type"],
        "url": webhook["url"],
        "attempt": attempt,
        "status": "sending" if attempt == 1 else "pending",
        "next_attempt_at": utcnow(),
        "created_at": utcnow(),
    }
    await db.webhook_deliveries.insert_one(delivery)
    # Fire immediately for attempt 1; retries are picked up by the worker.
    if attempt == 1:
        asyncio.create_task(_deliver_now(delivery["id"]))


async def _deliver_now(delivery_id: str) -> None:
    db = get_database()
    delivery = await db.webhook_deliveries.find_one({"id": delivery_id})
    if not delivery:
        return
    webhook = await db.webhooks.find_one({"id": delivery["webhook_id"]})
    event = await db.events.find_one({"id": delivery["event_id"]}, {"_id": 0})
    if not webhook or not event:
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {"status": "failed", "error": "Missing webhook or event", "finished_at": utcnow()}},
        )
        return
    if not webhook.get("enabled", True):
        await db.webhook_deliveries.update_one(
            {"id": delivery_id},
            {"$set": {"status": "skipped", "error": "Webhook disabled", "finished_at": utcnow()}},
        )
        return

    body_obj = {
        "id": event["id"],
        "type": event["type"],
        "resourceType": event.get("resourceType") or event.get("resource_type"),
        "payload": event.get("payload") or {},
        "createdAt": event.get("createdAt")
        or (event["created_at"].isoformat() if hasattr(event.get("created_at"), "isoformat") else str(event.get("created_at"))),
    }
    body = json.dumps(body_obj, default=str, separators=(",", ":"))
    ts = int(utcnow().timestamp())
    signature = _sign(webhook.get("secret") or "", ts, body)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Trustanova-Webhooks/1.0",
        "Trustanova-Signature": signature,
        "Trustanova-Event": event["type"],
        "Trustanova-Delivery": delivery_id,
    }

    attempt = int(delivery.get("attempt") or 1)
    status = "failed"
    error = None
    http_status = None
    response_text = None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(webhook["url"], content=body, headers=headers)
            http_status = resp.status_code
            response_text = resp.text[:4000]
            if 200 <= resp.status_code < 300:
                status = "succeeded"
            else:
                error = f"HTTP {resp.status_code}: {resp.text[:300]}"
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        response_text = None

    await db.webhook_deliveries.update_one(
        {"id": delivery_id},
        {
            "$set": {
                "status": status,
                "http_status": http_status,
                "error": error,
                "request_body": body_obj,
                "response_body": response_text,
                "finished_at": utcnow(),
            }
        },
    )
    # Mirror into events UI shape (latest delivery status on a delivery log entry)
    await db.events.update_one(
        {"id": event["id"]},
        {
            "$set": {
                "status": status,
                "attempt": attempt,
                "last_delivery_id": delivery_id,
                "last_http_status": http_status,
            }
        },
    )

    if status == "succeeded":
        return

    if attempt >= MAX_ATTEMPTS:
        await db.webhooks.update_one(
            {"id": webhook["id"]},
            {"$set": {"enabled": False, "disabled_reason": "max_delivery_attempts", "updated_at": utcnow()}},
        )
        logger.warning("Disabled webhook %s after %s failed attempts", webhook["id"], attempt)
        return

    delay = RETRY_DELAYS_SECONDS[min(attempt - 1, len(RETRY_DELAYS_SECONDS) - 1)]
    next_attempt = attempt + 1
    retry_doc = {
        "id": new_id("dlv_"),
        "org_id": webhook["org_id"],
        "webhook_id": webhook["id"],
        "event_id": event["id"],
        "event_type": event["type"],
        "url": webhook["url"],
        "attempt": next_attempt,
        "status": "pending",
        "next_attempt_at": utcnow() + timedelta(seconds=delay),
        "created_at": utcnow(),
    }
    await db.webhook_deliveries.insert_one(retry_doc)


async def process_due_deliveries(limit: int = 50) -> int:
    db = get_database()
    now = utcnow()
    due = (
        await db.webhook_deliveries.find(
            {"status": "pending", "next_attempt_at": {"$lte": now}},
            {"_id": 0},
        )
        .sort("next_attempt_at", 1)
        .to_list(limit)
    )
    for item in due:
        # Mark in-flight to avoid double pickup
        result = await db.webhook_deliveries.update_one(
            {"id": item["id"], "status": "pending"},
            {"$set": {"status": "sending"}},
        )
        if result.modified_count:
            await _deliver_now(item["id"])
    return len(due)


async def retry_worker_loop() -> None:
    while True:
        try:
            await process_due_deliveries()
        except Exception:  # noqa: BLE001
            logger.exception("webhook retry worker error")
        await asyncio.sleep(15)


def start_webhook_worker() -> None:
    global _retry_task
    if _retry_task is None or _retry_task.done():
        _retry_task = asyncio.create_task(retry_worker_loop())


def stop_webhook_worker() -> None:
    global _retry_task
    if _retry_task and not _retry_task.done():
        _retry_task.cancel()
    _retry_task = None


async def emit_client_created(org_id: str, client: dict[str, Any]) -> None:
    await emit_event(org_id, "client.created", serialize(client) or client, resource_type="clients")


async def emit_client_updated(org_id: str, client: dict[str, Any]) -> None:
    await emit_event(org_id, "client.updated", serialize(client) or client, resource_type="clients")


async def emit_client_deleted(org_id: str, client_id: str) -> None:
    await emit_event(org_id, "client.deleted", {"id": client_id}, resource_type="clients")


OUTCOME_WEBHOOK_EVENT = {
    "clear": "check.completed.clear",
    "consider": "check.completed.attention",
    "reject": "check.completed.rejected",
}


def _extract_check_scores(check: dict[str, Any]) -> dict[str, Any]:
    result = check.get("result") or {}
    if not isinstance(result, dict):
        return {}
    signals = result.get("signals") or {}
    scores = signals.get("scores")
    if isinstance(scores, dict):
        return scores
    document = result.get("document") or {}
    biometric = result.get("biometric") or {}
    return {
        "document_type": document.get("document_type"),
        "document_quality": document.get("quality_score"),
        "document_valid": document.get("valid"),
        "liveness_score": biometric.get("liveness_score"),
        "liveness_passed": biometric.get("liveness") == "live",
        "liveness_label": biometric.get("liveness"),
        "face_match_score": biometric.get("face_match_score"),
        "face_match_passed": biometric.get("face_match_passed"),
        "face_detected": biometric.get("face_detected"),
    }


def _build_check_webhook_payload(check: dict[str, Any]) -> dict[str, Any]:
    result = check.get("result") if isinstance(check.get("result"), dict) else None
    scores = _extract_check_scores(check)
    payload = {
        "id": check.get("id"),
        "status": check.get("status"),
        "outcome": check.get("outcome"),
        "type": check.get("type"),
        "client_id": check.get("client_id"),
        "session_id": check.get("session_id"),
        "document_id": check.get("document_id"),
        "live_photo_id": check.get("live_photo_id"),
        "scores": scores,
        "createdAt": check.get("created_at"),
        "updatedAt": check.get("updated_at") or check.get("completed_at"),
    }
    if result:
        payload["result"] = result
    return payload


async def emit_check_lifecycle(org_id: str, check: dict[str, Any], event_type: str) -> None:
    payload = _build_check_webhook_payload(check)
    await emit_event(org_id, event_type, payload, resource_type="checks")
    if event_type == "check.completed" and check.get("outcome"):
        outcome = str(check["outcome"]).lower()
        specific = OUTCOME_WEBHOOK_EVENT.get(outcome) or f"check.completed.{outcome}"
        from app.services.webhook_events import ALLOWED_EVENT_VALUES

        if specific in ALLOWED_EVENT_VALUES:
            await emit_event(org_id, specific, payload, resource_type="checks")
        if outcome == "clear":
            scores = payload.get("scores") or {}
            if scores_passed_face_match(scores):
                if "check.completed.match_confirmed" in ALLOWED_EVENT_VALUES:
                    await emit_event(org_id, "check.completed.match_confirmed", payload, resource_type="checks")


def scores_passed_face_match(scores: dict[str, Any]) -> bool:
    return bool(scores.get("face_match_passed")) and bool(scores.get("liveness_passed"))


async def build_verification_result_payload(session_id: str) -> dict[str, Any] | None:
    db = get_database()
    session = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        return None
    checks = await db.checks.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    check_payloads = [_build_check_webhook_payload(c) for c in checks]
    identity = next((c for c in checks if c.get("type") == "identity_check"), None)
    scores = _extract_check_scores(identity) if identity else {}
    outcomes = [str(c.get("outcome")).lower() for c in checks if c.get("outcome")]
    summary_outcome = "clear"
    if any(o == "reject" for o in outcomes):
        summary_outcome = "reject"
    elif any(o == "consider" for o in outcomes):
        summary_outcome = "consider"
    return {
        "session_id": session_id,
        "client_id": session.get("client_id"),
        "client_name": session.get("client_name"),
        "status": session.get("status"),
        "document_id": session.get("document_id"),
        "live_photo_id": session.get("live_photo_id"),
        "share_token": session.get("share_token"),
        "summary": {
            "outcome": summary_outcome,
            "checks_total": len(checks),
            "checks_complete": sum(1 for c in checks if (c.get("status") or "").lower() == "complete"),
        },
        "scores": scores,
        "checks": check_payloads,
        "completed_at": session.get("completed_at") or session.get("updated_at"),
    }


async def emit_verification_completed(org_id: str, session_id: str) -> None:
    """Send one webhook with full verification request/response (all checks + scores)."""
    payload = await build_verification_result_payload(session_id)
    if not payload:
        return
    session = await get_database().sessions.find_one({"id": session_id}, {"_id": 0})
    if session:
        payload["session"] = serialize(session) or session
    await emit_event(org_id, "workflow.session.completed", payload, resource_type="sessions")


async def maybe_emit_verification_completed(check_id: str) -> None:
    db = get_database()
    check = await db.checks.find_one({"id": check_id}, {"_id": 0})
    if not check or not check.get("session_id"):
        return
    org_id = check.get("org_id")
    if not org_id:
        client = await db.clients.find_one({"id": check.get("client_id")}, {"_id": 0})
        org_id = (client or {}).get("org_id")
    if not org_id:
        return
    session_id = check["session_id"]
    pending = await db.checks.count_documents(
        {"session_id": session_id, "status": {"$nin": ["complete", "failed"]}}
    )
    if pending > 0:
        return
    await emit_verification_completed(org_id, session_id)


async def emit_session_event(org_id: str, session: dict[str, Any], event_type: str) -> None:
    if event_type == "workflow.session.completed" and session.get("id"):
        payload = await build_verification_result_payload(session["id"])
        if payload:
            payload["session"] = serialize(session) or session
            await emit_event(org_id, event_type, payload, resource_type="sessions")
            return
    await emit_event(org_id, event_type, serialize(session) or session, resource_type="sessions")


async def emit_check_finished_from_id(check_id: str) -> None:
    """Called from verification worker after a check completes/fails."""
    db = get_database()
    check = await db.checks.find_one({"id": check_id}, {"_id": 0})
    if not check:
        return
    org_id = check.get("org_id")
    if not org_id:
        client = await db.clients.find_one({"id": check.get("client_id")}, {"_id": 0})
        org_id = (client or {}).get("org_id")
    if not org_id:
        return

    status = (check.get("status") or "").lower()
    if status in {"failed", "fail"}:
        await emit_check_lifecycle(org_id, check, "check.failed")
        return

    # Map result outcome if present
    result = check.get("result") or {}
    outcome = check.get("outcome")
    if not outcome and isinstance(result, dict):
        outcome = result.get("outcome") or (result.get("breakdown") or {}).get("outcome")
    if outcome:
        check = {**check, "outcome": str(outcome).lower()}
    await emit_check_lifecycle(org_id, check, "check.completed")
    await emit_check_lifecycle(org_id, check, "check.updated")
    try:
        await maybe_emit_verification_completed(check_id)
    except Exception:  # noqa: BLE001
        pass
