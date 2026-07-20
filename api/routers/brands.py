"""Brand CRUD — tenant-scoped. A brand must belong to a client in the caller's tenant."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, require_role
from api.db import repo
from api.db.mappers import to_brand
from api.db.session import get_session
from mimik_contracts import Brand, BrandTokens, Reference

router = APIRouter(prefix="/brands", tags=["brands"])


class CreateBrand(BaseModel):
    client_id: str
    name: str
    slug: str
    niche: str | None = None
    services: list[str] = Field(default_factory=list)
    target_audience: str | None = None
    brand_voice: str | None = None
    tone_keywords: list[str] = Field(default_factory=list)
    dos: list[str] = Field(default_factory=list)
    donts: list[str] = Field(default_factory=list)
    handles: dict[str, str] = Field(default_factory=dict)
    imagery_style: str | None = None
    # Design tokens at creation (colors/typography/logo) — validated by the contract, so a
    # payload can't smuggle an unsafe logo ref past the asset-ref validator.
    tokens: BrandTokens = Field(default_factory=BrandTokens)
    # Vetted aesthetic references the client shares at onboarding (Pinterest / existing designs /
    # social posts / websites, with an optional note). fit_score stays None until a later ingest
    # pass scores them; these are the human-curated seeds of the mood board.
    references: list[Reference] = Field(default_factory=list)


@router.post("", response_model=Brand, status_code=201)
async def create_brand(
    body: CreateBrand,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Brand:
    # The client must exist within the caller's tenant — else this is a cross-tenant attach.
    client = await repo.get_client(
        session, tenant_id=principal.tenant_id, client_id=body.client_id
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    fields = body.model_dump()
    fields["tokens"] = body.tokens.model_dump(mode="json")
    fields["references"] = [r.model_dump(mode="json") for r in body.references]
    row = await repo.create_brand(session, tenant_id=principal.tenant_id, **fields)
    await session.commit()
    return to_brand(row)


@router.patch("/{brand_id}", response_model=Brand)
async def update_brand_tokens(
    brand_id: str,
    body: BrandTokens,
    principal: Principal = Depends(require_role("owner", "admin", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> Brand:
    """Update a brand's design tokens (the brand-kit editor). Full-replace of `tokens` — colors,
    typography, logo, and the layout (logo placement/size, margins, header/footer, grid + guides).
    Tenant-scoped: another tenant's brand id 404s. The contract validates the tokens, so an unsafe
    logo ref or an out-of-range layout value is rejected at the boundary."""
    row = await repo.get_brand(session, tenant_id=principal.tenant_id, brand_id=brand_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    row.tokens = body.model_dump(mode="json")
    await session.commit()
    return to_brand(row)


@router.get("/{brand_id}", response_model=Brand)
async def get_brand(
    brand_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Brand:
    row = await repo.get_brand(session, tenant_id=principal.tenant_id, brand_id=brand_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return to_brand(row)
