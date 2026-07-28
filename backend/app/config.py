from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIVENCUBE_", env_file=".env", extra="ignore")

    app_name: str = "Trustanova"
    debug: bool = False
    mongodb_url: str = "mongodb://127.0.0.1:27018"
    mongodb_db: str = "liveness"
    jwt_secret: str = "livencube-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    verification_api_url: str = "http://127.0.0.1:8000"
    verification_api_key: str = "sk_test_liveness_dev"
    # When true, empty DB gets demo admin + sample data (local only). Production: leave false.
    seed_demo: bool = False

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
