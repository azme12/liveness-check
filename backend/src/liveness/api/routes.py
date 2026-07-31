"""HTTP routes for clients, documents, photos, checks, sessions."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase

from liveness.api.deps import get_blob_store, get_check_engine, require_api_key
from liveness.api.schemas import (
    CheckCreate,
    CheckOut,
    ClientCreate,
    ClientOut,
    FaceEnrollOut,
    ResourceOut,
    SessionConfigOut,
    SessionCreate,
    SessionOut,
)
from liveness.api.worker import process_check
from liveness.checks import CheckEngine
from liveness.config import Settings, get_settings
from liveness.db import get_db, update_one
from liveness.ml import FaceGallery, OpenFaceAnalyzer, decode_image
from liveness.storage import BlobStore
from liveness.types import CheckStatus, CheckType, SessionStatus, new_id, utc_now
from liveness.version import __version__

router = APIRouter(tags=["liveness"])


def _client_out(c: dict[str, Any]) -> ClientOut:
    return ClientOut(
        id=c["id"],
        email=c.get("email"),
        full_name=c.get("full_name"),
        metadata=c.get("metadata"),
        created_at=c["created_at"],
    )


def _check_out(c: dict[str, Any]) -> CheckOut:
    return CheckOut(
        id=c["id"],
        client_id=c["client_id"],
        type=CheckType(c["type"]),
        status=CheckStatus(c["status"]),
        document_id=c.get("document_id"),
        live_photo_id=c.get("live_photo_id"),
        client_consent=bool(c.get("client_consent", False)),
        result=c.get("result"),
        error=c.get("error"),
        created_at=c["created_at"],
        updated_at=c["updated_at"],
    )


def _session_out(s: dict[str, Any], *, status: SessionStatus | None = None) -> SessionOut:
    return SessionOut(
        id=s["id"],
        token=s["token"],
        client_id=s["client_id"],
        workflow_id=s["workflow_id"],
        status=status or SessionStatus(s["status"]),
        document_id=s.get("document_id"),
        live_photo_id=s.get("live_photo_id"),
        check_id=s.get("check_id"),
        redirect_url=s.get("redirect_url"),
        branding=s.get("branding"),
        expires_at=s["expires_at"],
        created_at=s["created_at"],
    )


@router.get("/health", tags=["system"], openapi_extra={"security": []})
async def health(engine: CheckEngine = Depends(get_check_engine)):
    openface = OpenFaceAnalyzer()
    detected_bin = OpenFaceAnalyzer.detect_openface_install()
    return {
        "status": "ok",
        "version": __version__,
        "backends": {
            "ocr": engine.ocr._backend,
            "liveness": engine.liveness._backend,
            "face": engine.faces._backend,
            "face_gallery": engine.faces._backend,
            "active_liveness": openface.backend,
            "openface_bin": detected_bin,
            "db": "mongodb",
        },
        "integrations": {
            "face_recognition_system": "gallery_enroll_1n_via_insightface",
            "openface": "cli_when_bin_set_else_opencv_fallback",
        },
    }


@router.post("/v1/clients", response_model=ClientOut, dependencies=[Depends(require_api_key)])
async def create_client(body: ClientCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    client = {
        "id": new_id("cli"),
        "email": body.email,
        "full_name": body.full_name,
        "metadata": body.metadata,
        "created_at": utc_now(),
    }
    await db.clients.insert_one(client)
    client.pop("_id", None)
    return _client_out(client)


@router.get("/v1/clients/{client_id}", response_model=ClientOut, dependencies=[Depends(require_api_key)])
async def get_client(client_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    client = await db.clients.find_one({"id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _client_out(client)


@router.post("/v1/documents", response_model=ResourceOut, dependencies=[Depends(require_api_key)])
async def upload_document(
    client_id: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    store: BlobStore = Depends(get_blob_store),
):
    client = await db.clients.find_one({"id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    doc_id = new_id("doc")
    key = f"documents/{doc_id}/{file.filename or 'document.jpg'}"
    store.put(key, data)
    doc = {
        "id": doc_id,
        "client_id": client_id,
        "storage_key": key,
        "document_type": None,
        "status": "uploaded",
        "created_at": utc_now(),
    }
    await db.documents.insert_one(doc)
    return ResourceOut(
        id=doc["id"], client_id=doc["client_id"], status=doc["status"], created_at=doc["created_at"]
    )


@router.post("/v1/livePhotos", response_model=ResourceOut, dependencies=[Depends(require_api_key)])
async def upload_live_photo(
    client_id: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    store: BlobStore = Depends(get_blob_store),
):
    client = await db.clients.find_one({"id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    photo_id = new_id("pho")
    key = f"live_photos/{photo_id}/{file.filename or 'selfie.jpg'}"
    store.put(key, data)
    photo = {
        "id": photo_id,
        "client_id": client_id,
        "storage_key": key,
        "status": "uploaded",
        "created_at": utc_now(),
    }
    await db.live_photos.insert_one(photo)
    return ResourceOut(
        id=photo["id"],
        client_id=photo["client_id"],
        status=photo["status"],
        created_at=photo["created_at"],
    )


@router.post(
    "/v1/clients/{client_id}/face-enroll",
    response_model=FaceEnrollOut,
    dependencies=[Depends(require_api_key)],
)
async def enroll_face(
    client_id: str,
    file: UploadFile = File(...),
    label: str | None = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    engine: CheckEngine = Depends(get_check_engine),
):
    """Enroll a reference face for 1:N authentication (Face Recognition System pattern)."""
    client = await db.clients.find_one({"id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    image = decode_image(data)
    gallery = FaceGallery(analyzer=engine.faces)
    try:
        result = await gallery.enroll(
            client_id=client_id,
            image=image,
            label=label or client.get("full_name") or client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FaceEnrollOut(
        embedding_id=result.embedding_id,
        client_id=result.client_id,
        label=result.label,
        backend=result.backend,
    )


@router.post("/v1/checks", response_model=CheckOut, dependencies=[Depends(require_api_key)])
async def create_check(
    body: CheckCreate,
    background: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not body.client_consent:
        raise HTTPException(status_code=400, detail="client_consent must be true")
    client = await db.clients.find_one({"id": body.client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if body.type in {CheckType.DOCUMENT, CheckType.IDENTITY, CheckType.ENHANCED_IDENTITY} and not body.document_id:
        raise HTTPException(status_code=400, detail="document_id required for this check type")
    if body.type in {CheckType.IDENTITY, CheckType.ENHANCED_IDENTITY} and not body.live_photo_id:
        raise HTTPException(status_code=400, detail="live_photo_id required for identity_check")
    if body.type == CheckType.FACE_AUTHENTICATION and not body.live_photo_id:
        raise HTTPException(status_code=400, detail="live_photo_id required for face_authentication_check")

    now = utc_now()
    check = {
        "id": new_id("chk"),
        "client_id": body.client_id,
        "type": body.type.value,
        "status": CheckStatus.PENDING.value,
        "document_id": body.document_id,
        "live_photo_id": body.live_photo_id,
        "client_consent": body.client_consent,
        "options": body.options,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.checks.insert_one(check)
    check.pop("_id", None)
    background.add_task(process_check, check["id"])
    return _check_out(check)


@router.get("/v1/checks/{check_id}", response_model=CheckOut, dependencies=[Depends(require_api_key)])
async def get_check(check_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    check = await db.checks.find_one({"id": check_id}, {"_id": 0})
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return _check_out(check)


@router.get(
    "/v1/clients/{client_id}/checks",
    response_model=list[CheckOut],
    dependencies=[Depends(require_api_key)],
)
async def list_checks(client_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    cursor = db.checks.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1)
    rows = await cursor.to_list(length=200)
    return [_check_out(c) for c in rows]


@router.post("/v1/sessions", response_model=SessionOut, dependencies=[Depends(require_api_key)])
async def create_session(
    body: SessionCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    client = await db.clients.find_one({"id": body.client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    expires = utc_now() + timedelta(minutes=settings.session_ttl_minutes)
    sess = {
        "id": new_id("sess"),
        "token": new_id("tok"),
        "client_id": body.client_id,
        "workflow_id": body.workflow_id,
        "status": SessionStatus.PENDING.value,
        "document_id": None,
        "live_photo_id": None,
        "check_id": None,
        "redirect_url": body.redirect_url,
        "branding": body.branding,
        "expires_at": expires,
        "created_at": utc_now(),
    }
    await db.sessions.insert_one(sess)
    sess.pop("_id", None)
    return _session_out(sess)


async def _session_by_token(db: AsyncIOMotorDatabase, token: str) -> dict[str, Any]:
    sess = await db.sessions.find_one(
        {"$or": [{"token": token}, {"share_token": token}]},
        {"_id": 0},
    )
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess["expires_at"] < utc_now():
        await update_one("sessions", {"id": sess["id"]}, {"status": SessionStatus.EXPIRED.value})
        raise HTTPException(status_code=410, detail="Session expired")
    return sess


@router.get("/v1/sessions/by-token/{token}/config", response_model=SessionConfigOut)
async def session_config(token: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    sess = await _session_by_token(db, token)
    return SessionConfigOut(
        workflow_id=sess["workflow_id"],
        branding=sess.get("branding") or {},
        steps=[
            {"id": "consent", "type": "consent", "required": True},
            {
                "id": "doc",
                "type": "document_capture",
                "docTypes": ["passport", "national_id", "driving_license"],
            },
            {"id": "selfie", "type": "selfie_capture", "livenessMode": "passive"},
            {"id": "check", "type": "run_check", "checkType": "identity_check"},
        ],
    )


@router.post("/v1/sessions/by-token/{token}/documents", response_model=ResourceOut)
async def session_upload_document(
    token: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    store: BlobStore = Depends(get_blob_store),
):
    sess = await _session_by_token(db, token)
    data = await file.read()
    doc_id = new_id("doc")
    key = f"documents/{doc_id}/{file.filename or 'document.jpg'}"
    store.put(key, data)
    doc = {
        "id": doc_id,
        "client_id": sess["client_id"],
        "storage_key": key,
        "document_type": None,
        "status": "uploaded",
        "created_at": utc_now(),
    }
    await db.documents.insert_one(doc)
    await update_one(
        "sessions",
        {"id": sess["id"]},
        {"document_id": doc_id, "status": SessionStatus.CAPTURING.value},
    )
    return ResourceOut(
        id=doc["id"], client_id=doc["client_id"], status=doc["status"], created_at=doc["created_at"]
    )


@router.post("/v1/sessions/by-token/{token}/livePhotos", response_model=ResourceOut)
async def session_upload_photo(
    token: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
    store: BlobStore = Depends(get_blob_store),
):
    sess = await _session_by_token(db, token)
    data = await file.read()
    photo_id = new_id("pho")
    key = f"live_photos/{photo_id}/{file.filename or 'selfie.jpg'}"
    store.put(key, data)
    photo = {
        "id": photo_id,
        "client_id": sess["client_id"],
        "storage_key": key,
        "status": "uploaded",
        "created_at": utc_now(),
    }
    await db.live_photos.insert_one(photo)
    await update_one("sessions", {"id": sess["id"]}, {"live_photo_id": photo_id})
    return ResourceOut(
        id=photo["id"],
        client_id=photo["client_id"],
        status=photo["status"],
        created_at=photo["created_at"],
    )


@router.post("/v1/sessions/by-token/{token}/complete", response_model=SessionOut)
async def session_complete(
    token: str,
    background: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    sess = await _session_by_token(db, token)
    if not sess.get("document_id") or not sess.get("live_photo_id"):
        raise HTTPException(status_code=400, detail="document and live photo required")

    now = utc_now()
    check = {
        "id": new_id("chk"),
        "client_id": sess["client_id"],
        "type": CheckType.IDENTITY.value,
        "status": CheckStatus.PENDING.value,
        "document_id": sess["document_id"],
        "live_photo_id": sess["live_photo_id"],
        "client_consent": True,
        "options": None,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.checks.insert_one(check)
    check.pop("_id", None)
    await update_one(
        "sessions",
        {"id": sess["id"]},
        {"check_id": check["id"], "status": SessionStatus.PROCESSING.value},
    )
    sess["check_id"] = check["id"]
    sess["status"] = SessionStatus.PROCESSING.value
    background.add_task(process_check, check["id"])

    async def _finalize() -> None:
        await asyncio.sleep(0.1)
        await update_one(
            "sessions", {"id": sess["id"]}, {"status": SessionStatus.COMPLETE.value}
        )

    background.add_task(_finalize)
    return _session_out(sess, status=SessionStatus.PROCESSING)


@router.get("/v1/sessions/by-token/{token}", response_model=SessionOut)
async def get_session(token: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    sess = await _session_by_token(db, token)
    return _session_out(sess)
