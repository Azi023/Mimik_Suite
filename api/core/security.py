"""JWT issue/verify. The token carries the tenant_id — the sole source of truth for tenant
scoping. A caller cannot widen their scope by editing a request body."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from .config import get_settings


def create_access_token(*, tenant_id: str, role: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_ttl_min),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode + verify. Raises jwt.PyJWTError on invalid/expired tokens."""
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
