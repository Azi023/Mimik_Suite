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

    # Managed auth (Supabase). Authentication is delegated to Supabase; we only VERIFY its
    # JWTs. `supabase_url` drives the derived JWKS endpoint for asymmetric (ES256/RS256)
    # keys — the modern default. `supabase_jwt_secret` is the legacy HS256 shared secret,
    # used only if a project still signs symmetrically.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    # Overridable for tests; empty -> derived from supabase_url.
    supabase_jwks_url: str = ""

    @property
    def resolved_jwks_url(self) -> str:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return ""

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1" if self.supabase_url else ""

    # Brand Asset Library — where uploaded brand files (logos, reference creatives) live.
    # Local disk during the build; a bucket later is a config change, not a code change.
    assets_local_root: str = "var/assets"

    # Billing (Stripe, TEST mode during the build). Empty until the operator provides test keys;
    # the billing endpoints refuse to call Stripe without them (no accidental live/charge calls).
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    # Where Stripe Checkout returns the customer (the storefront/portal).
    billing_success_url: str = "https://mimikcreations.com/unlimited/welcome"
    billing_cancel_url: str = "https://mimikcreations.com/unlimited"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
