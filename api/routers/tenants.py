"""Tenant bootstrap: create a tenant and mint its first access token.

P0 keeps auth minimal but real — a tenant gets a token scoped to itself. Full user/password
onboarding lands later; this is enough to prove tenant isolation end-to-end.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, principal_audit_actor, require_role
from api.core.security import create_access_token
from api.db import repo
from api.db.mappers import to_tenant
from api.db.session import get_session
from mimik_contracts import Tenant, UpdateTenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


class CreateTenant(BaseModel):
    name: str
    slug: str


class TenantCreated(BaseModel):
    tenant: Tenant
    access_token: str
    token_type: str = "bearer"


@router.post("", response_model=TenantCreated, status_code=201)
async def create_tenant(
    body: CreateTenant,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_role("super_admin")),
) -> TenantCreated:
    row = await repo.create_tenant(session, name=body.name, slug=body.slug)
    await session.commit()
    # The founding principal of a tenant is its owner (can provision accounts via /admin).
    token = create_access_token(tenant_id=row.id, role="owner")
    return TenantCreated(tenant=to_tenant(row), access_token=token)


@router.get("", response_model=list[Tenant])
async def list_tenants(
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_role("super_admin")),
) -> list[Tenant]:
    rows = await repo.list_tenants(session)
    return [to_tenant(row) for row in rows]


@router.patch("/{tenant_id}", response_model=Tenant)
async def update_tenant_suspension(
    tenant_id: str,
    body: UpdateTenant,
    session: AsyncSession = Depends(get_session),
    principal: Principal = Depends(require_role("super_admin")),
) -> Tenant:
    row = await repo.set_tenant_suspended(
        session,
        tenant_id=tenant_id,
        suspended=body.suspended,
        actor=principal_audit_actor(principal),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await session.commit()
    return to_tenant(row)
