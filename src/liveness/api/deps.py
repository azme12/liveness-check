"""FastAPI dependencies — auth + shared services."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from liveness.checks import CheckEngine
from liveness.config import Settings, get_settings
from liveness.db import get_db
from liveness.storage import BlobStore

_engine: CheckEngine | None = None
_store: BlobStore | None = None


def get_check_engine() -> CheckEngine:
    global _engine
    if _engine is None:
        _engine = CheckEngine()
    return _engine


def get_blob_store() -> BlobStore:
    global _store
    if _store is None:
        _store = BlobStore()
    return _store


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    token = x_api_key
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if token != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return token


DbSession = Depends(get_db)
ApiKey = Depends(require_api_key)
EngineDep = Depends(get_check_engine)
StoreDep = Depends(get_blob_store)
SettingsDep = Depends(get_settings)

# For type annotations in routes
AsyncDb = AsyncSession
