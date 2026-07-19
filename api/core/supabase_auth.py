"""Supabase JWT verification — the managed-auth half (never self-rolled).

Supabase issues the access token; we only VERIFY it. Modern projects sign with asymmetric
keys (ES256/RS256) exposed at a JWKS endpoint; legacy projects use an HS256 shared secret.
Both are supported. Verification enforces signature, `exp`, audience (`authenticated`), and
issuer — a token that fails any check is rejected.

The JWKS fetch is a single seam (`_fetch_jwks`) with an in-memory TTL cache, so tests inject
a local keypair's JWKS with zero network. On a `kid` miss the cache is refreshed once (key
rotation), then the token is rejected if still unknown.
"""

from __future__ import annotations

import json
import time
import urllib.request

import jwt
from jwt import PyJWKSet

from .config import get_settings

_AUDIENCE = "authenticated"
_JWKS_TTL_SECONDS = 600
_JWKS_MAX_BYTES = 262_144  # a JWKS doc is a few KB; cap the read so a hostile endpoint can't OOM us
# module-level cache: (fetched_at, PyJWKSet)
_jwks_cache: tuple[float, PyJWKSet] | None = None


class SupabaseAuthError(Exception):
    """Verification failed (bad signature, expired, wrong issuer/audience, or misconfig)."""


def _now() -> float:
    return time.time()


def _fetch_jwks(url: str) -> dict:
    """GET the JWKS document. Isolated seam: tests monkeypatch this — no network in tests."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (operator's own project URL)
        return json.loads(resp.read(_JWKS_MAX_BYTES))


def _load_jwks(*, force: bool = False) -> PyJWKSet:
    global _jwks_cache
    settings = get_settings()
    url = settings.resolved_jwks_url
    if not url:
        raise SupabaseAuthError("supabase JWKS url is not configured (set SUPABASE_URL)")
    if not force and _jwks_cache is not None and _now() - _jwks_cache[0] < _JWKS_TTL_SECONDS:
        return _jwks_cache[1]
    try:
        jwks = PyJWKSet.from_dict(_fetch_jwks(url))
    except SupabaseAuthError:
        raise
    except Exception as exc:  # network / parse — surface as an auth error, never a 500
        raise SupabaseAuthError(f"could not load Supabase JWKS: {exc}") from exc
    _jwks_cache = (_now(), jwks)
    return jwks


def _signing_key_for(token: str) -> object:
    """Resolve the asymmetric verifying key for a token's `kid`, refreshing on a miss."""
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise SupabaseAuthError("token header has no kid")
    for force in (False, True):  # refresh once on miss to tolerate key rotation
        jwks = _load_jwks(force=force)
        for key in jwks.keys:
            if key.key_id == kid:
                return key.key
    raise SupabaseAuthError(f"no JWKS key matches kid={kid!r}")


def verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase-issued access token and return its verified claims.

    Raises SupabaseAuthError on any failure. Asymmetric (ES256/RS256) tokens verify against
    the JWKS; HS256 tokens verify against the configured shared secret.
    """
    settings = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg", "")
    except jwt.PyJWTError as exc:
        raise SupabaseAuthError(f"malformed token header: {exc}") from exc

    options = {"require": ["exp", "sub"]}
    issuer = settings.supabase_issuer or None
    try:
        if alg.startswith(("ES", "RS", "PS")):
            key = _signing_key_for(token)
            return jwt.decode(
                token, key, algorithms=[alg], audience=_AUDIENCE, issuer=issuer, options=options
            )
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise SupabaseAuthError("HS256 token but SUPABASE_JWT_SECRET is not configured")
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=_AUDIENCE,
                issuer=issuer,
                options=options,
            )
    except SupabaseAuthError:
        raise
    except jwt.PyJWTError as exc:
        raise SupabaseAuthError(f"token verification failed: {exc}") from exc
    raise SupabaseAuthError(f"unsupported token algorithm: {alg!r}")


def _reset_cache_for_tests() -> None:
    global _jwks_cache
    _jwks_cache = None
