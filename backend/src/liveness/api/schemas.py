"""Pydantic request/response schemas for the Checks API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from liveness.types import CheckOutcome, CheckStatus, CheckType, SessionStatus


class ClientCreate(BaseModel):
    email: str | None = None
    full_name: str | None = None
    metadata: dict[str, Any] | None = None


class ClientOut(BaseModel):
    id: str
    email: str | None = None
    full_name: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime


class ResourceOut(BaseModel):
    id: str
    client_id: str
    status: str
    created_at: datetime


class FaceEnrollOut(BaseModel):
    embedding_id: str
    client_id: str
    label: str
    backend: str


class CheckCreate(BaseModel):
    client_id: str
    type: CheckType
    document_id: str | None = None
    live_photo_id: str | None = None
    client_consent: bool = False
    options: dict[str, Any] | None = None
    enable_monitoring: bool = False


class CheckOut(BaseModel):
    id: str
    client_id: str
    type: CheckType
    status: CheckStatus
    document_id: str | None = None
    live_photo_id: str | None = None
    client_consent: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class SessionCreate(BaseModel):
    client_id: str
    workflow_id: str = "standard_kyc"
    redirect_url: str | None = None
    branding: dict[str, Any] | None = None


class SessionOut(BaseModel):
    id: str
    token: str
    client_id: str
    workflow_id: str
    status: SessionStatus
    document_id: str | None = None
    live_photo_id: str | None = None
    check_id: str | None = None
    redirect_url: str | None = None
    branding: dict[str, Any] | None = None
    expires_at: datetime
    created_at: datetime


class SessionConfigOut(BaseModel):
    workflow_id: str
    locale: str = "en"
    branding: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]]


class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    backends: dict[str, str]


class ErrorOut(BaseModel):
    detail: str
