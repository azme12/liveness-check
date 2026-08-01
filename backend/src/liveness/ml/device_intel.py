"""Lightweight device fingerprint + velocity signals for fraud scoring."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from liveness.db import get_database
from liveness.types import utc_now


@dataclass
class DeviceFingerprint:
    fingerprint_hash: str
    ip: str | None
    user_agent: str | None
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint_hash": self.fingerprint_hash,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "details": self.details,
        }


def build_fingerprint(
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    client_hints: dict[str, Any] | None = None,
) -> DeviceFingerprint:
    hints = client_hints or {}
    parts = [
        (ip or "").strip(),
        (user_agent or "").strip()[:500],
        str(hints.get("platform") or ""),
        str(hints.get("language") or ""),
        str(hints.get("screen") or ""),
        str(hints.get("timezone") or ""),
    ]
    raw = "|".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return DeviceFingerprint(
        fingerprint_hash=digest,
        ip=ip,
        user_agent=user_agent,
        details={
            "platform": hints.get("platform"),
            "language": hints.get("language"),
            "screen": hints.get("screen"),
            "timezone": hints.get("timezone"),
        },
    )


async def device_velocity(
    *,
    org_id: str,
    fingerprint_hash: str,
    exclude_client_id: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """Count distinct clients that used this device fingerprint recently."""
    db = get_database()
    since = utc_now() - timedelta(days=days)
    query: dict[str, Any] = {
        "org_id": org_id,
        "device.fingerprint_hash": fingerprint_hash,
        "created_at": {"$gte": since},
    }
    client_ids: set[str] = set()
    cursor = db.live_photos.find(query, {"client_id": 1, "_id": 0})
    async for row in cursor:
        cid = row.get("client_id")
        if cid and cid != exclude_client_id:
            client_ids.add(cid)
    count = len(client_ids)
    risk = 0.0
    if count >= 5:
        risk = 80.0
    elif count >= 3:
        risk = 55.0
    elif count >= 2:
        risk = 30.0
    return {
        "distinct_clients": count,
        "risk": risk,
        "window_days": days,
        "client_ids_sample": list(client_ids)[:10],
    }
