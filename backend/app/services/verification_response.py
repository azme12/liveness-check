"""ComplyCube / CBE-compatible verification response builder."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.db import get_database
from app.services.seed import serialize
from liveness.ml.scores import enrich_verification_scores
from liveness.ml.partner_format import build_identity_result_breakdown

# Internal doc types → partner document types (ComplyCube-style)
DOCUMENT_TYPE_MAP = {
    "fayda": "national_identity_card",
    "kebele_id": "national_identity_card",
    "national_id": "national_identity_card",
    "passport": "passport",
    "driving_license": "driving_license",
}

COUNTRY_MAP = {
    "ethiopia": "ET",
    "kenya": "KE",
    "uganda": "UG",
    "united kingdom": "GB",
    "united states": "US",
}


def _partner_document_type(doc_type: str | None) -> str:
    if not doc_type:
        return "national_identity_card"
    key = doc_type.lower().replace("-", "_")
    return DOCUMENT_TYPE_MAP.get(key, doc_type)


def _issuing_country(code_or_name: str | None) -> str:
    if not code_or_name:
        return "ET"
    v = code_or_name.strip()
    if len(v) == 2 and v.isalpha():
        return v.upper()
    return COUNTRY_MAP.get(v.lower(), v.upper()[:2] if v else "ET")


def _status_upper(outcome: str) -> str:
    return {"clear": "CLEAR", "consider": "ATTENTION", "reject": "REJECTED"}.get(outcome, "PENDING")


def _verification_outcome(outcome: str) -> str:
    return {
        "clear": "verification_clear",
        "consider": "verification_attention",
        "reject": "verification_rejected",
    }.get(outcome, "verification_pending")


def _extract_scores_from_check(check: dict[str, Any] | None) -> dict[str, Any]:
    if not check:
        return enrich_verification_scores({})
    result = check.get("result") or {}
    signals = result.get("signals") or {}
    raw = signals.get("scores")
    if isinstance(raw, dict) and raw:
        return enrich_verification_scores(raw)
    bio = result.get("biometric") or {}
    doc = result.get("document") or {}
    return enrich_verification_scores(
        {
            "document_type": doc.get("document_type"),
            "document_quality": doc.get("quality_score"),
            "liveness_score": bio.get("liveness_score"),
            "liveness_passed": bio.get("liveness") == "live",
            "face_match_score": bio.get("face_match_score"),
            "face_match_passed": bio.get("face_match_passed"),
            "face_detected": bio.get("face_detected"),
        }
    )


def _media_urls(session: dict[str, Any], api_base: str) -> tuple[str | None, str | None]:
    token = session.get("share_token") or session.get("token") or ""
    if not token or not api_base:
        return None, None
    base = api_base.rstrip("/")
    doc_url = f"{base}/api/verify/{token}/media/document" if session.get("document_id") else None
    selfie_url = f"{base}/api/verify/{token}/media/live-photo" if session.get("live_photo_id") else None
    return doc_url, selfie_url


def _client_display_name(client: dict[str, Any] | None) -> str:
    if not client:
        return ""
    if client.get("name"):
        return str(client["name"])
    parts = [client.get("first_name"), client.get("middle_name"), client.get("last_name")]
    return " ".join(p for p in parts if p)


async def build_partner_verification_response(
    session_id: str,
    *,
    api_base: str | None = None,
) -> dict[str, Any] | None:
    """Full CBE / ComplyCube-shaped verification payload."""
    db = get_database()
    session = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        return None

    client = await db.clients.find_one({"id": session.get("client_id")}, {"_id": 0})
    checks = await db.checks.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    identity = next((c for c in checks if c.get("type") == "identity_check"), None)

    doc_row = None
    if session.get("document_id"):
        doc_row = await db.documents.find_one({"id": session["document_id"]}, {"_id": 0})

    settings = get_settings()
    base = (api_base or settings.public_api_url or settings.verification_api_url or "").strip()
    doc_url, selfie_url = _media_urls(session, base)

    scores = _extract_scores_from_check(identity)
    outcomes = [str(c.get("outcome")).lower() for c in checks if c.get("outcome")]
    summary_outcome = "clear"
    if any(o == "reject" for o in outcomes):
        summary_outcome = "reject"
    elif any(o == "consider" for o in outcomes):
        summary_outcome = "consider"

    identity_outcome = str(identity.get("outcome") or summary_outcome).lower() if identity else summary_outcome
    identity_status = "COMPLETE" if identity and (identity.get("status") or "").lower() == "complete" else "PENDING"

    doc_type = _partner_document_type(
        (doc_row or {}).get("document_type") or scores.get("document_type")
    )
    issuing = _issuing_country((doc_row or {}).get("issuing_country") or (client or {}).get("nationality"))

    face_detected = bool(scores.get("face_detected", True))
    result_breakdown = build_identity_result_breakdown(
        scores,
        outcome=identity_outcome,
        face_detected=face_detected,
    )

    facial_score = scores.get("facialSimilarityScore") or 0
    liveness_score = scores.get("livenessCheckScore") or 0

    identity_check_obj: dict[str, Any] = {
        "id": identity.get("id") if identity else None,
        "clientId": session.get("client_id"),
        "documentId": session.get("document_id"),
        "livePhotoId": session.get("live_photo_id"),
        "type": "identity_check",
        "entityName": _client_display_name(client),
        "status": (identity.get("status") or "pending") if identity else "pending",
        "outcome": identity_outcome,
        "initialOutcome": identity_outcome,
        "result": result_breakdown,
        "createdAt": serialize(identity.get("created_at")) if identity else None,
        "updatedAt": serialize(identity.get("updated_at") or identity.get("completed_at")) if identity else None,
    }

    provider_block = {
        "document_id": session.get("document_id"),
        "live_photo_id": session.get("live_photo_id"),
        "document_type": doc_type,
        "identity_check_id": identity.get("id") if identity else None,
        "identity_check": identity_check_obj,
        "document": {
            "id": session.get("document_id"),
            "type": doc_type,
            "classification": "proof_of_identity",
            "issuing_country": issuing,
        },
        "identity_outcome": identity_outcome,
        "identity_status": identity_status,
        "updated_at": serialize(session.get("updated_at")),
    }

    return {
        "client_id": session.get("client_id"),
        "session_id": session_id,
        "full_name": _client_display_name(client),
        "first_name": (client or {}).get("first_name"),
        "middle_name": (client or {}).get("middle_name"),
        "last_name": (client or {}).get("last_name"),
        "email": (client or {}).get("email") or "",
        "phone_number": (client or {}).get("mobile") or (client or {}).get("phone_number"),
        "gender": (client or {}).get("gender"),
        "nationality": (client or {}).get("nationality"),
        "birth_date": serialize((client or {}).get("date_of_birth")),
        "picture": doc_url,
        "selfie_photo": selfie_url,
        "document_front": doc_url,
        "complycube": provider_block,
        "verification": provider_block,
        "status": _status_upper(summary_outcome),
        "outcome": _verification_outcome(summary_outcome),
        "facial_score": facial_score,
        "liveness_score": liveness_score,
        "facialSimilarityScore": facial_score,
        "livenessCheckScore": liveness_score,
        "scores": scores,
        "checks": [serialize(c) for c in checks],
    }
