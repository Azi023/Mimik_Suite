"""App configuration from environment. No secrets in code; `.env` is gitignored."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://mimik:mimik@localhost:5434/mimik_suite"
    redis_url: str = "redis://localhost:6381/0"
    jwt_secret: str = "dev-only-insecure-change-me-0000000000"  # >=32 bytes; real secret via env
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 60
    app_env: str = "dev"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
