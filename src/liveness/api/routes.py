"""HTTP routes for clients, documents, photos, checks, sessions."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from liveness.api.deps import get_blob_store, get_check_engine, require_api_key
from liveness.api.schemas import (
    CheckCreate,
    CheckOut,
    ClientCreate,
    ClientOut,
    ResourceOut,
    SessionConfigOut,
    SessionCreate,
    SessionOut,
)
from liveness.api.worker import process_check
from liveness.checks import CheckEngine
from liveness.config import Settings, get_settings
from liveness.db import CaptureSession, Check, Client, Document, LivePhoto, get_db
from liveness.storage import BlobStore
from liveness.types import CheckStatus, CheckType, SessionStatus, new_id, utc_now
from liveness.version import __version__

router = APIRouter()


def _client_out(c: Client) -> ClientOut:
    return ClientOut(
        id=c.id,
        email=c.email,
        full_name=c.full_name,
        metadata=c.metadata_json,
        created_at=c.created_at,
    )


def _check_out(c: Check) -> CheckOut:
    return CheckOut(
        id=c.id,
        client_id=c.client_id,
        type=CheckType(c.type),
        status=CheckStatus(c.status),
        document_id=c.document_id,
        live_photo_id=c.live_photo_id,
        client_consent=c.client_consent,
        result=c.result,
        error=c.error,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/health")
async def health(engine: CheckEngine = Depends(get_check_engine)):
    return {
        "status": "ok",
        "version": __version__,
        "backends": {
            "ocr": engine.ocr._backend,
            "liveness": engine.liveness._backend,
            "face": engine.faces._backend,
        },
    }


@router.post("/v1/clients", response_model=ClientOut, dependencies=[Depends(require_api_key)])
async def create_client(body: ClientCreate, db: AsyncSession = Depends(get_db)):
    client = Client(email=body.email, full_name=body.full_name, metadata_json=body.metadata)
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return _client_out(client)


@router.get("/v1/clients/{client_id}", response_model=ClientOut, dependencies=[Depends(require_api_key)])
async def get_client(client_id: str, db: AsyncSession = Depends(get_db)):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _client_out(client)


@router.post("/v1/documents", response_model=ResourceOut, dependencies=[Depends(require_api_key)])
async def upload_document(
    client_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    store: BlobStore = Depends(get_blob_store),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    doc = Document(client_id=client_id, storage_key="")
    db.add(doc)
    await db.flush()
    key = f"documents/{doc.id}/{file.filename or 'document.jpg'}"
    store.put(key, data)
    doc.storage_key = key
    await db.commit()
    await db.refresh(doc)
    return ResourceOut(id=doc.id, client_id=doc.client_id, status=doc.status, created_at=doc.created_at)


@router.post("/v1/livePhotos", response_model=ResourceOut, dependencies=[Depends(require_api_key)])
async def upload_live_photo(
    client_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    store: BlobStore = Depends(get_blob_store),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    photo = LivePhoto(client_id=client_id, storage_key="")
    db.add(photo)
    await db.flush()
    key = f"live_photos/{photo.id}/{file.filename or 'selfie.jpg'}"
    store.put(key, data)
    photo.storage_key = key
    await db.commit()
    await db.refresh(photo)
    return ResourceOut(
        id=photo.id, client_id=photo.client_id, status=photo.status, created_at=photo.created_at
    )


@router.post("/v1/checks", response_model=CheckOut, dependencies=[Depends(require_api_key)])
async def create_check(
    body: CheckCreate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    if not body.client_consent:
        raise HTTPException(status_code=400, detail="client_consent must be true")
    client = await db.get(Client, body.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if body.type in {CheckType.DOCUMENT, CheckType.IDENTITY} and not body.document_id:
        raise HTTPException(status_code=400, detail="document_id required for this check type")
    if body.type == CheckType.IDENTITY and not body.live_photo_id:
        raise HTTPException(status_code=400, detail="live_photo_id required for identity_check")

    check = Check(
        client_id=body.client_id,
        type=body.type.value,
        document_id=body.document_id,
        live_photo_id=body.live_photo_id,
        client_consent=body.client_consent,
        options=body.options,
        status=CheckStatus.PENDING.value,
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)
    background.add_task(process_check, check.id)
    return _check_out(check)


@router.get("/v1/checks/{check_id}", response_model=CheckOut, dependencies=[Depends(require_api_key)])
async def get_check(check_id: str, db: AsyncSession = Depends(get_db)):
    check = await db.get(Check, check_id)
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    return _check_out(check)


@router.get(
    "/v1/clients/{client_id}/checks",
    response_model=list[CheckOut],
    dependencies=[Depends(require_api_key)],
)
async def list_checks(client_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(select(Check).where(Check.client_id == client_id).order_by(Check.created_at.desc()))
    ).all()
    return [_check_out(c) for c in rows]


@router.post("/v1/sessions", response_model=SessionOut, dependencies=[Depends(require_api_key)])
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    client = await db.get(Client, body.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    expires = utc_now() + timedelta(minutes=settings.session_ttl_minutes)
    sess = CaptureSession(
        client_id=body.client_id,
        workflow_id=body.workflow_id,
        redirect_url=body.redirect_url,
        branding=body.branding,
        expires_at=expires,
        token=new_id("tok"),
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return SessionOut(
        id=sess.id,
        token=sess.token,
        client_id=sess.client_id,
        workflow_id=sess.workflow_id,
        status=SessionStatus(sess.status),
        document_id=sess.document_id,
        live_photo_id=sess.live_photo_id,
        check_id=sess.check_id,
        redirect_url=sess.redirect_url,
        branding=sess.branding,
        expires_at=sess.expires_at,
        created_at=sess.created_at,
    )


async def _session_by_token(db: AsyncSession, token: str) -> CaptureSession:
    sess = await db.scalar(select(CaptureSession).where(CaptureSession.token == token))
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess.expires_at < utc_now():
        sess.status = SessionStatus.EXPIRED.value
        await db.commit()
        raise HTTPException(status_code=410, detail="Session expired")
    return sess


@router.get("/v1/sessions/by-token/{token}/config", response_model=SessionConfigOut)
async def session_config(token: str, db: AsyncSession = Depends(get_db)):
    sess = await _session_by_token(db, token)
    return SessionConfigOut(
        workflow_id=sess.workflow_id,
        branding=sess.branding or {},
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
    db: AsyncSession = Depends(get_db),
    store: BlobStore = Depends(get_blob_store),
):
    sess = await _session_by_token(db, token)
    data = await file.read()
    doc = Document(client_id=sess.client_id, storage_key="")
    db.add(doc)
    await db.flush()
    key = f"documents/{doc.id}/{file.filename or 'document.jpg'}"
    store.put(key, data)
    doc.storage_key = key
    sess.document_id = doc.id
    sess.status = SessionStatus.CAPTURING.value
    await db.commit()
    await db.refresh(doc)
    return ResourceOut(id=doc.id, client_id=doc.client_id, status=doc.status, created_at=doc.created_at)


@router.post("/v1/sessions/by-token/{token}/livePhotos", response_model=ResourceOut)
async def session_upload_photo(
    token: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    store: BlobStore = Depends(get_blob_store),
):
    sess = await _session_by_token(db, token)
    data = await file.read()
    photo = LivePhoto(client_id=sess.client_id, storage_key="")
    db.add(photo)
    await db.flush()
    key = f"live_photos/{photo.id}/{file.filename or 'selfie.jpg'}"
    store.put(key, data)
    photo.storage_key = key
    sess.live_photo_id = photo.id
    await db.commit()
    await db.refresh(photo)
    return ResourceOut(
        id=photo.id, client_id=photo.client_id, status=photo.status, created_at=photo.created_at
    )


@router.post("/v1/sessions/by-token/{token}/complete", response_model=SessionOut)
async def session_complete(
    token: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    sess = await _session_by_token(db, token)
    if not sess.document_id or not sess.live_photo_id:
        raise HTTPException(status_code=400, detail="document and live photo required")
    check = Check(
        client_id=sess.client_id,
        type=CheckType.IDENTITY.value,
        document_id=sess.document_id,
        live_photo_id=sess.live_photo_id,
        client_consent=True,
        status=CheckStatus.PENDING.value,
    )
    db.add(check)
    await db.flush()
    sess.check_id = check.id
    sess.status = SessionStatus.PROCESSING.value
    await db.commit()
    await db.refresh(sess)
    background.add_task(process_check, check.id)

    # Mark session complete once check finishes (poller-friendly; also wait briefly)
    async def _finalize():
        await asyncio.sleep(0.1)
        factory = __import__("liveness.db", fromlist=["get_session_factory"]).get_session_factory()
        async with factory() as s:
            row = await s.get(CaptureSession, sess.id)
            if row:
                row.status = SessionStatus.COMPLETE.value
                await s.commit()

    background.add_task(_finalize)

    return SessionOut(
        id=sess.id,
        token=sess.token,
        client_id=sess.client_id,
        workflow_id=sess.workflow_id,
        status=SessionStatus.PROCESSING,
        document_id=sess.document_id,
        live_photo_id=sess.live_photo_id,
        check_id=sess.check_id,
        redirect_url=sess.redirect_url,
        branding=sess.branding,
        expires_at=sess.expires_at,
        created_at=sess.created_at,
    )


@router.get("/v1/sessions/by-token/{token}", response_model=SessionOut)
async def get_session(token: str, db: AsyncSession = Depends(get_db)):
    sess = await _session_by_token(db, token)
    return SessionOut(
        id=sess.id,
        token=sess.token,
        client_id=sess.client_id,
        workflow_id=sess.workflow_id,
        status=SessionStatus(sess.status),
        document_id=sess.document_id,
        live_photo_id=sess.live_photo_id,
        check_id=sess.check_id,
        redirect_url=sess.redirect_url,
        branding=sess.branding,
        expires_at=sess.expires_at,
        created_at=sess.created_at,
    )
