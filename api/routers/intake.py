"""Storefront intake — the acquisition→fulfillment bridge.

`POST /intake/claim` is the PUBLIC front door (the mimikcreations.com/unlimited "3 free designs"
claim form). It captures a lead as a prospect Client under a storefront tenant and starts a
draft Brief — the fulfillment side then takes over. It is deliberately a lead-capture step
ONLY: it never performs an outbound fetch, because a public unauthenticated endpoint that
fetches an attacker-supplied URL is an SSRF/DoS amplifier. The cold-bootstrap extraction (which
DOES fetch the prospect's site) runs behind team auth at `POST /clients/{id}/bootstrap`.

Abuse note: this endpoint is public. It dedups by email (a resubmit returns the existing
prospect, not a duplicate) and validates input shape, but production still needs edge
rate-limiting + a CAPTCHA in front of it — that belongs at the gateway, not in app code.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, StringConstraints
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, require_role
from api.db import repo
from api.db.mappers import to_brief, to_client
from api.db.session import get_session
from api.services.brief_extraction import extract_brief_sections
from mimik_contracts import Brief, BriefSections, BriefStatus, Client

router = APIRouter(tags=["intake"])


# Bounded strings on a PUBLIC endpoint — cap payload size so an unauthenticated caller can't
# bloat rows with multi-MB values (storage DoS). Defense in depth on top of FastAPI's body limit.
_Short = Annotated[str, StringConstraints(max_length=200, strip_whitespace=True)]
_Url = Annotated[str, StringConstraints(max_length=2048, strip_whitespace=True)]
_Notes = Annotated[str, StringConstraints(max_length=4000)]


class ClaimForm(BaseModel):
    tenant_slug: _Short       # which agency's storefront this claim came through
    name: _Short              # contact / business name
    email: EmailStr
    brand_name: _Short | None = None
    website_url: _Url | None = None
    instagram: _Short | None = None
    notes: _Notes | None = None


class ClaimResult(BaseModel):
    client: Client
    brief: Brief
    created: bool  # False if this email already had a prospect (idempotent resubmit)


def _validate_optional_url(url: str | None) -> str | None:
    """Accept only http(s) URLs by SHAPE. We do NOT resolve DNS here — no fetch, no timing
    oracle from a public endpoint; the SSRF DNS check happens later, behind auth, at fetch time."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=422, detail="website_url must be an http(s) URL")
    return url


async def _existing_prospect_result(
    session: AsyncSession, *, tenant_id: str, existing, brand_name: str | None
) -> ClaimResult:
    """The idempotent branch: return the existing prospect + its brief (minting one only if
    somehow absent). `created=False` — a resubmit never creates a duplicate."""
    briefs = await repo.list_briefs(session, tenant_id=tenant_id, client_id=existing.id)
    if briefs:
        return ClaimResult(client=to_client(existing), brief=to_brief(briefs[0]), created=False)
    brand_rows = await repo.list_brands(session, tenant_id=tenant_id, client_id=existing.id)
    brand = brand_rows[0] if brand_rows else await repo.create_brand(
        session, tenant_id=tenant_id, client_id=existing.id,
        name=brand_name or existing.name, slug="prospect",
    )
    brief_row = await repo.create_brief(
        session, tenant_id=tenant_id, client_id=existing.id, brand_id=brand.id,
        status=BriefStatus.DRAFT.value, sections=BriefSections().model_dump(mode="json"),
    )
    await session.commit()
    return ClaimResult(client=to_client(existing), brief=to_brief(brief_row), created=False)


@router.post("/intake/claim", response_model=ClaimResult, status_code=201)
async def claim(body: ClaimForm, session: AsyncSession = Depends(get_session)) -> ClaimResult:
    tenant = await repo.get_tenant_by_slug(session, body.tenant_slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Unknown storefront")
    website_url = _validate_optional_url(body.website_url)

    # Idempotent: a resubmitted claim for the same email returns the existing prospect + brief.
    existing = await repo.get_client_by_email(session, tenant_id=tenant.id, email=body.email)
    if existing is not None:
        return await _existing_prospect_result(
            session, tenant_id=tenant.id, existing=existing, brand_name=body.brand_name
        )

    try:
        client_row = await repo.create_client(
            session,
            tenant_id=tenant.id,
            name=body.name,
            contact_email=body.email,
            website_url=website_url,
            instagram=body.instagram,
            notes=f"Prospect via claim form. {body.notes or ''}".strip(),
        )
        brand_row = await repo.create_brand(
            session, tenant_id=tenant.id, client_id=client_row.id,
            name=body.brand_name or body.name, slug="prospect",
        )
        brief_row = await repo.create_brief(
            session, tenant_id=tenant.id, client_id=client_row.id, brand_id=brand_row.id,
            status=BriefStatus.DRAFT.value, sections=BriefSections().model_dump(mode="json"),
        )
        await session.commit()
    except IntegrityError:
        # A concurrent claim for the same email won the UNIQUE(tenant_id, contact_email) race —
        # dedup is now atomic: roll back and return that winner's prospect.
        await session.rollback()
        existing = await repo.get_client_by_email(session, tenant_id=tenant.id, email=body.email)
        if existing is None:
            raise
        return await _existing_prospect_result(
            session, tenant_id=tenant.id, existing=existing, brand_name=body.brand_name
        )
    return ClaimResult(client=to_client(client_row), brief=to_brief(brief_row), created=True)


@router.post("/clients/{client_id}/bootstrap", response_model=Brief)
async def cold_bootstrap(
    client_id: str,
    principal: Principal = Depends(require_role("owner", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> Brief:
    """Cold-client bootstrap (team-only): fetch the prospect's own site and auto-draft the
    brief §1-5. The outbound fetch runs HERE, behind auth, with the SSRF guard in
    extract_brief_sections — never on the public claim endpoint."""
    client_row = await repo.get_client(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    if client_row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client_row.website_url:
        raise HTTPException(status_code=422, detail="Client has no website_url to bootstrap from")

    brand_rows = await repo.list_brands(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    if brand_rows:
        brand = brand_rows[0]
    else:
        brand = await repo.create_brand(
            session, tenant_id=principal.tenant_id, client_id=client_id,
            name=client_row.name, slug="prospect",
        )

    try:
        sections = await extract_brief_sections(client_row.website_url)
    except ValueError as exc:  # SSRF guard / unreachable host / bad URL
        raise HTTPException(status_code=422, detail=str(exc))

    brief_row = await repo.create_brief(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
        brand_id=brand.id,
        status=BriefStatus.DRAFT.value,
        sections=sections.model_dump(mode="json"),
    )
    await session.commit()
    return to_brief(brief_row)
