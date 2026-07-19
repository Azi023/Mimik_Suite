"""JWT issue/verify. The token carries the tenant_id — the sole source of truth for tenant
scoping. A caller cannot widen their scope by editing a request body."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from .config import get_settings


_TYP = "access"


def create_access_token(*, tenant_id: str, role: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "typ": _TYP,  # distinguishes this from a magic-link token signed with the same secret
        "sub": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_ttl_min),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode + verify. Raises jwt.PyJWTError on invalid/expired tokens, or if the token is
    not an access token — access and magic-link tokens share a secret, so `typ` MUST be
    pinned on each verifier to prevent one being replayed as the other."""
    s = get_settings()
    claims = jwt.decode(
        token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["sub", "exp"]}
    )
    if claims.get("typ") != _TYP:
        raise jwt.InvalidTokenError("not an access token")
    return claims
