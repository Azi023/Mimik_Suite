"""Public brand-book read — the ONE bearer-less surface (the magic-link pattern).

`GET /brand-book/{token}` resolves a signed brand-book token to the full `Brand`, which the
public web route `/book/{token}` renders. There is NO user auth here: the token IS the
capability. Trust is bounded tightly:

- The token's signature is verified; only its verified brand_id/tenant_id are trusted (a forged
  or tampered token fails verification and 404s).
- The row is re-read tenant-scoped from those verified claims — the token is a pointer, not the
  authority.
- For a SHARE token, `kit.published` must be True on the freshly-read row, else 404 (the flag is
  the authority; unpublishing kills every outstanding link without revoking tokens). Existence is
  never revealed — every failure returns the same 404.
- An EXPORT token bypasses the published gate (internal render of an unpublished book), but is
  short-lived and only ever minted server-side for the Playwright exporter.

The returned Brand is read-only DATA the client renders; it carries no tools and no cross-tenant
visibility (constraint #3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.brand_book_token import BrandBookTokenError, verify_brand_book_token
from api.db import repo
from api.db.mappers import to_brand
from api.db.session import get_session
from mimik_contracts import Brand

router = APIRouter(tags=["brand-book"])

_NOT_FOUND = HTTPException(status_code=404, detail="Brand book not found")


@router.get("/brand-book/{token}", response_model=Brand)
async def read_brand_book(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> Brand:
    try:
        claims = verify_brand_book_token(token)
    except BrandBookTokenError:
        # Same calm 404 for every failure mode — never reveal why (existence, expiry, tamper).
        raise _NOT_FOUND
    row = await repo.get_brand(
        session, tenant_id=claims["tenant_id"], brand_id=claims["brand_id"]
    )
    if row is None:
        raise _NOT_FOUND
    brand = to_brand(row)
    # SHARE links honour the live published flag; EXPORT tokens (internal render) bypass it.
    if claims["kind"] == "share" and not brand.kit.published:
        raise _NOT_FOUND
    return brand
