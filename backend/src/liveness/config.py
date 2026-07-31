"""Application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIVENESS_", env_file=".env", extra="ignore")

    app_name: str = "Liveness"
    debug: bool = False
    api_key: str = "sk_test_liveness_dev"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "liveness"
    storage_dir: Path = Path("./storage")
    models_dir: Path = Path("./models")
    face_match_threshold: float = 0.45
    face_gallery_threshold: float = 0.45
    liveness_threshold: float = 0.5
    quality_threshold: float = 0.35
    session_ttl_minutes: int = 30
    allow_heuristic_fallback: bool = True
    # Disable on Render free tier (512MB) — uses OpenCV Haar + histogram embeddings instead.
    insightface_enabled: bool = True
    # OpenFace CLI (head pose / AU signals) — set LIVENESS_OPENFACE_BIN to enable
    openface_bin: Path | None = None
    openface_enabled: bool = False
    openface_max_yaw: float = 25.0
    openface_max_pitch: float = 20.0
    openface_max_roll: float = 15.0
    openface_min_certainty: float = 0.5
    openface_auto_detect: bool = True
    # Selfie upload head-pose gate (OpenFace / InsightFace / bbox proxy)
    selfie_max_yaw: float = 20.0
    selfie_max_pitch: float = 15.0
    selfie_max_roll: float = 12.0
    selfie_min_pose_certainty: float = 0.45
    # Strict live-selfie profile gate (glasses, background, blur, etc.)
    selfie_min_face_area_ratio: float = 0.14
    selfie_min_blur_laplacian: float = 90.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
