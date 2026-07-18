"""Brand CRUD — tenant-scoped. A brand must belong to a client in the caller's tenant."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal
from api.db import repo
from api.db.mappers import to_brand
from api.db.session import get_session
from mimik_contracts import Brand

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
    row = await repo.create_brand(session, tenant_id=principal.tenant_id, **body.model_dump())
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
