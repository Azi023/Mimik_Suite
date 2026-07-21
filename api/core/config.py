"""App configuration from environment. No secrets in code; `.env` is gitignored."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://mimik:mimik@localhost:5434/mimik_suite"
    # Optional path to a CA bundle for the DB's TLS cert (only if the host uses a private CA;
    # Supabase's pooler uses publicly-trusted certs and needs none). Enables full verification.
    db_ssl_root_cert: str = ""
    redis_url: str = "redis://localhost:6381/0"
    jwt_secret: str = "dev-only-insecure-change-me-0000000000"  # >=32 bytes; real secret via env
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 60
    app_env: str = "dev"

    # Managed auth (Supabase). Authentication is delegated to Supabase; we only VERIFY its
    # JWTs. `supabase_url` drives the derived JWKS endpoint for asymmetric (ES256/RS256)
    # keys — the modern default. `supabase_jwt_secret` is the legacy HS256 shared secret,
    # used only if a project still signs symmetrically.
    # Where the web app serves the invite-accept screen. The accept-link handed to an admin is
    # f"{app_base_url}/invite/accept?token=...". Config-only; override per environment via env.
    app_base_url: str = "http://localhost:3000"

    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    # Overridable for tests; empty -> derived from supabase_url.
    supabase_jwks_url: str = ""

    # Comma-separated Supabase emails elevated to super_admin (platform operators). Secret-free,
    # env-provided: identity still comes from a verified Supabase token; this only lifts the role.
    superadmin_emails: str = ""

    @property
    def superadmin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.superadmin_emails.split(",") if e.strip()}

    @property
    def resolved_database_url(self) -> str:
        """The DATABASE_URL forced onto the async driver. Managed Postgres consoles (Supabase,
        Neon, RDS) hand out a plain `postgresql://` DSN; we run on asyncpg, so normalize the scheme
        rather than make every operator remember `+asyncpg`. A URL that already names a driver
        (`postgresql+asyncpg://`, `postgresql+psycopg://`, …) is left untouched."""
        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix) :]
        return url

    @property
    def db_connect_args(self) -> dict[str, object]:
        """asyncpg connect args. Managed Postgres (Supabase et al.) REQUIRES TLS and asyncpg does
        not enable it by default, so a remote host gets a full-verification SSLContext built from
        the SYSTEM CA bundle — `ssl.create_default_context()` sets check_hostname=True +
        verify_mode=CERT_REQUIRED (rejects MITM) WITHOUT needing a `~/.postgresql/root.crt` file
        (which the bare `ssl="verify-full"` string demands). Verifies cleanly against Supabase's
        pooler (`*.pooler.supabase.com`, publicly-trusted certs) — the recommended DSN. A local/
        loopback host connects plaintext. Point `DB_SSL_ROOT_CERT` at a bundle for a private CA."""
        from urllib.parse import urlparse

        host = (urlparse(self.resolved_database_url).hostname or "").lower()
        if host in ("", "localhost", "127.0.0.1", "::1", "db"):
            return {}
        import ssl
        from pathlib import Path

        ctx = ssl.create_default_context()
        cafile = self.db_ssl_root_cert
        # Supabase serves its DB behind its OWN CA ("Supabase Root 2021 CA", self-signed) which is
        # not in the public trust store — so full verification fails against the system bundle. We
        # ship that CA (docker/supabase-ca.crt, a PUBLIC cert) and add it to the trust for *.supabase
        # hosts, keeping check_hostname + CERT_REQUIRED. Result: verified TLS, no MITM, no user setup.
        if not cafile and host.endswith(".supabase.com"):
            bundled = Path(__file__).resolve().parents[2] / "docker" / "supabase-ca.crt"
            if bundled.exists():
                cafile = str(bundled)
        if cafile:
            ctx.load_verify_locations(cafile=cafile)
        return {"ssl": ctx}

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

    # Archive backend — Google Drive via USER OAuth (ARCHIVE_BACKEND=google_drive_oauth). This is
    # the working prod path: files are owned by the user and use the user's Drive quota, so it
    # can upload into ordinary My-Drive folders (a service account can't — it has no quota).
    # Obtain the refresh token ONCE via `scripts/drive_oauth.py`. Secrets — provide via env only.
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_refresh_token: str = ""

    # WhatsApp outbound (NotificationChannel.WHATSAPP). Swappable like the image backends:
    # `whatsapp_provider` picks the sink. "none" (default) = inert, no network, no account —
    # a WHATSAPP notification is recorded but left PENDING until a provider is wired.
    # "meta_cloud" = official WhatsApp Business Platform (Cloud API); needs the fields below.
    # The access token is a secret — provide via env only, never commit it.
    whatsapp_provider: str = "none"  # none | meta_cloud
    whatsapp_phone_number_id: str = ""  # the WABA sender's phone-number ID (not the number)
    whatsapp_access_token: str = ""  # SECRET — Meta permanent/system-user token
    whatsapp_template_name: str = "creative_ready"  # a pre-approved Utility template
    whatsapp_template_lang: str = "en"
    whatsapp_api_base: str = "https://graph.facebook.com/v21.0"  # overridable for tests


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
