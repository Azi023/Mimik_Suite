"""Invite accept tokens: a signed, expiring capability that identifies ONE pending invitation
so its matching Supabase identity can consume it and be provisioned a UserAccount.

Like magic_link.py this is our own HMAC, pinned to `typ=invite` so it can never be confused
with an access token or a magic-link grant. It carries the tenant + email it is scoped to; the
accept endpoint still re-checks the DB invitation state and the caller's verified email — the
token is a pointer, not the authority. Tokens are secrets: never log them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from .config import get_settings

_TYP = "invite"
INVITE_TTL_HOURS = 168  # 7 days — the single source of truth for the invite window (DB + token)


class InviteTokenError(Exception):
    """The token is invalid, expired, or not an invite token."""


def issue_invite_token(
    *, invitation_id: str, tenant_id: str, email: str, ttl_hours: int = INVITE_TTL_HOURS
) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "typ": _TYP,
        "invitation_id": invitation_id,
        "tenant_id": tenant_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def verify_invite_token(token: str) -> dict:
    """Return the invite claims, or raise InviteTokenError. Enforces typ + expiry + scope."""
    s = get_settings()
    try:
        claims = jwt.decode(
            token,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],
            options={"require": ["exp", "invitation_id", "tenant_id", "email"]},
        )
    except jwt.PyJWTError as exc:
        raise InviteTokenError(f"invalid invite token: {exc}") from exc
    if claims.get("typ") != _TYP:
        raise InviteTokenError("not an invite token")
    return claims
