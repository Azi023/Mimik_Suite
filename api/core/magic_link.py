"""Magic-link grants: a signed, expiring capability to approve/request-change ONE job with
no login — the frictionless client path (WhatsApp-shareable).

This is a capability token, not user auth: it authorizes a single bounded action on a single
job, and carries the tenant + client it is scoped to. It is our own HMAC (typ=magic_link),
kept distinct from access tokens by the `typ` claim so one can never be used as the other.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from .config import get_settings

_TYP = "magic_link"
_DEFAULT_TTL_HOURS = 72


class MagicLinkError(Exception):
    """The grant is invalid, expired, or not a magic-link token."""


def issue_magic_link(
    *, tenant_id: str, job_id: str, client_id: str, ttl_hours: int = _DEFAULT_TTL_HOURS
) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "typ": _TYP,
        "tenant_id": tenant_id,
        "job_id": job_id,
        "client_id": client_id,
        "iat": now,
        "exp": now + timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def verify_magic_link(token: str) -> dict:
    """Return the grant claims, or raise MagicLinkError. Enforces typ + expiry + required scope."""
    s = get_settings()
    try:
        claims = jwt.decode(
            token,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],
            options={"require": ["exp", "tenant_id", "job_id", "client_id"]},
        )
    except jwt.PyJWTError as exc:
        raise MagicLinkError(f"invalid magic link: {exc}") from exc
    if claims.get("typ") != _TYP:
        raise MagicLinkError("not a magic-link token")
    return claims
