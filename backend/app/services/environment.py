"""Workspace environment helpers (test vs live data partitions)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import Depends, HTTPException, Query

from app.db import get_database
from app.deps import get_current_user

Environment = Literal["test", "live"]


def parse_environment(value: str = "test") -> Environment:
    v = (value or "test").strip().lower()
    if v in {"test", "sandbox"}:
        return "test"
    if v == "live":
        return "live"
    raise HTTPException(status_code=400, detail="environment must be test or live")


async def environment_query(
    environment: str = Query("test", description="test or live workspace"),
    user: dict = Depends(get_current_user),
) -> Environment:
    env = parse_environment(environment)
    if env == "live":
        org = await get_database().organizations.find_one({"id": user["org_id"]}, {"live_enabled": 1})
        if not org or not org.get("live_enabled"):
            raise HTTPException(
                status_code=403,
                detail="Activate account to access live data.",
            )
    return env


def env_match(environment: Environment) -> dict[str, Any]:
    """
    Filter docs for an environment.
    Legacy docs without `environment` count as live.
    """
    if environment == "live":
        return {"$or": [{"environment": "live"}, {"environment": {"$exists": False}}]}
    return {"environment": "test"}


def with_org_env(org_id: str, environment: Environment) -> dict[str, Any]:
    return {"org_id": org_id, **env_match(environment)}
