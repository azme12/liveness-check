"""SQLAlchemy async models + session helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from liveness.config import get_settings
from liveness.types import CheckStatus, CheckType, SessionStatus, new_id, utc_now


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cli"))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(320), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("doc"))
    client_id: Mapped[str] = mapped_column(String(40), index=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LivePhoto(Base):
    __tablename__ = "live_photos"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("pho"))
    client_id: Mapped[str] = mapped_column(String(40), index=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("chk"))
    client_id: Mapped[str] = mapped_column(String(40), index=True)
    type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default=CheckStatus.PENDING.value)
    document_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    live_photo_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    client_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CaptureSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("sess"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=lambda: new_id("tok"))
    client_id: Mapped[str] = mapped_column(String(40), index=True)
    workflow_id: Mapped[str] = mapped_column(String(64), default="standard_kyc")
    status: Mapped[str] = mapped_column(String(32), default=SessionStatus.PENDING.value)
    document_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    live_photo_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    check_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    redirect_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    branding: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        if settings.database_url.startswith("sqlite"):
            Path = __import__("pathlib").Path
            Path("./data").mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(settings.database_url, echo=settings.debug)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_check(session: AsyncSession, check_id: str) -> Check | None:
    return await session.scalar(select(Check).where(Check.id == check_id))


# re-export for type hints
__all__ = [
    "Base",
    "Client",
    "Document",
    "LivePhoto",
    "Check",
    "CaptureSession",
    "init_db",
    "get_db",
    "get_session_factory",
    "CheckType",
]
