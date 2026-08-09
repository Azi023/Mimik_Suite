"""TLS trust for the database connection.

Supabase fronts Postgres with its OWN root CA on BOTH DSN shapes it hands out — the pooler
(`aws-0-<region>.pooler.supabase.com`) and the direct host (`db.<ref>.supabase.co`). Matching only
`.supabase.com` silently dropped the bundled root for direct hosts, so every such connection died
with CERTIFICATE_VERIFY_FAILED. These tests pin both TLDs.
"""

from __future__ import annotations

import ssl
from pathlib import Path

from api.core.config import Settings

BUNDLED_CA = Path(__file__).resolve().parents[1] / "docker" / "supabase-ca.crt"


def _settings(host: str, **kw: object) -> Settings:
    return Settings(
        database_url=f"postgresql://u:p@{host}:5432/postgres",
        db_ssl_root_cert="",
        **kw,
    )


def test_bundled_supabase_ca_is_present() -> None:
    assert BUNDLED_CA.exists(), "docker/supabase-ca.crt is load-bearing for prod TLS"


def test_local_hosts_connect_plaintext() -> None:
    for host in ("localhost", "127.0.0.1", "db"):
        assert _settings(host).db_connect_args == {}


def test_supabase_pooler_host_trusts_bundled_ca() -> None:
    args = _settings("aws-0-ap-southeast-1.pooler.supabase.com").db_connect_args
    ctx = args["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is True
    assert ctx.verify_mode is ssl.CERT_REQUIRED
    assert _bundled_root_loaded(ctx)


def test_supabase_direct_host_trusts_bundled_ca() -> None:
    """The `.supabase.co` direct DSN — the case the old `.supabase.com`-only check missed."""
    ctx = _settings("db.abcdefghijklmnop.supabase.co").db_connect_args["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    assert _bundled_root_loaded(ctx)


def test_non_supabase_remote_host_uses_system_trust_only() -> None:
    ctx = _settings("db.example.com").db_connect_args["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    assert not _bundled_root_loaded(ctx)


def _bundled_root_loaded(ctx: ssl.SSLContext) -> bool:
    subjects = {
        rdn[0][1]
        for cert in ctx.get_ca_certs()
        for rdn in cert.get("subject", ())
        if rdn and rdn[0][0] == "commonName"
    }
    return "Supabase Root 2021 CA" in subjects
