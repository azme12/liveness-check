"""Application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIVENESS_", env_file=".env", extra="ignore")

    app_name: str = "Liveness"
    debug: bool = False
    api_key: str = "sk_test_liveness_dev"
    database_url: str = "sqlite+aiosqlite:///./data/liveness.db"
    storage_dir: Path = Path("./storage")
    models_dir: Path = Path("./models")
    face_match_threshold: float = 0.45
    liveness_threshold: float = 0.5
    quality_threshold: float = 0.35
    session_ttl_minutes: int = 30
    # When True, heavy ML deps are optional — heuristics / stubs used instead
    allow_heuristic_fallback: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
