"""Brand-book share/export tokens: a signed, expiring capability that names ONE brand and the
tenant it lives in, so a bearer-less reader (the public /book/{token} page) or the internal
Playwright exporter can resolve exactly that brand — nothing else.

Mirrors invite_token.py / magic_link.py: our own HMAC, pinned to `typ=brand_book` and further
discriminated by `kind` so a share token can never be confused with an access token, a
magic-link grant, or an export token. It carries brand_id + tenant_id + kind; the reader
endpoint still re-reads the row and re-checks `kit.published` (for share kind) — the token is a
pointer, not the authority. Tokens are secrets: never log them or echo them in errors.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

from .config import get_settings

_TYP = "brand_book"

BrandBookKind = Literal["share", "export"]

# The client share link is long-lived (a link the studio hands a client and forgets); the
# internal export capability is short-lived (minted per render, used within seconds).
SHARE_TTL_DAYS = 30
EXPORT_TTL_MINUTES = 5


class BrandBookTokenError(Exception):
    """The token is invalid, expired, of the wrong type, or of an unknown kind."""


def issue_brand_book_token(
    *,
    brand_id: str,
    tenant_id: str,
    kind: BrandBookKind,
) -> str:
    """Mint a signed capability for one brand book. `kind` picks the TTL and gates read rules."""
    if kind not in ("share", "export"):
        raise BrandBookTokenError("unknown brand-book token kind")
    s = get_settings()
    now = datetime.now(timezone.utc)
    ttl = timedelta(days=SHARE_TTL_DAYS) if kind == "share" else timedelta(minutes=EXPORT_TTL_MINUTES)
    payload = {
        "typ": _TYP,
        "kind": kind,
        "brand_id": brand_id,
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def verify_brand_book_token(token: str) -> dict:
    """Return the brand-book claims, or raise BrandBookTokenError. Enforces typ + kind + expiry
    + presence of brand_id/tenant_id. A tampered or forged token fails signature verification."""
    s = get_settings()
    try:
        claims = jwt.decode(
            token,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],
            options={"require": ["exp", "brand_id", "tenant_id", "kind"]},
        )
    except jwt.PyJWTError as exc:
        # Never include the token in the error — it is a secret capability.
        raise BrandBookTokenError(f"invalid brand-book token: {exc}") from exc
    if claims.get("typ") != _TYP:
        raise BrandBookTokenError("not a brand-book token")
    if claims.get("kind") not in ("share", "export"):
        raise BrandBookTokenError("unknown brand-book token kind")
    return claims
