"""Client CRUD — every operation scoped to the caller's tenant (from the token, not the body)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, is_client_in_scope, require_role
from api.db import repo
from api.db.mappers import to_client, to_creative_doc
from api.db.session import get_session
from api.services.creative_generation import (
    GenerateCreativeRequest,
    GeneratedCreative,
    generate_client_creative,
    generated_creative_response,
)
from mimik_contracts import ActorRole, Client

router = APIRouter(prefix="/clients", tags=["clients"])

# Creating tenant resources is a TEAM action — a bounded client principal never provisions
# clients/brands/jobs/pillars/briefs (constraint #3: the portal is a review-only surface).
_TEAM = require_role("owner", "admin", "ops", "designer", "team")


class CreateClient(BaseModel):
    name: str
    contact_email: EmailStr | None = None
    phone: str | None = None
    industry: str | None = None
    website_url: str | None = None
    instagram: str | None = None
    notes: str | None = None


@router.post("", response_model=Client, status_code=201)
async def create_client(
    body: CreateClient,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> Client:
    row = await repo.create_client(
        session, tenant_id=principal.tenant_id, **body.model_dump()
    )
    await session.commit()
    return to_client(row)


@router.get("", response_model=list[Client])
async def list_clients(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Client]:
    rows = await repo.list_clients(session, tenant_id=principal.tenant_id)
    # A client principal may only ever see its OWN client — never enumerate the tenant's other
    # clients (their names + contact PII). Bounded portal, data-layer authZ (constraint #2).
    if principal.role == ActorRole.CLIENT.value:
        rows = [r for r in rows if r.id == principal.client_id]
    return [to_client(r) for r in rows]


@router.get("/{client_id}", response_model=Client)
async def get_client(
    client_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Client:
    row = await repo.get_client(session, tenant_id=principal.tenant_id, client_id=client_id)
    if row is None:
        # 404 (not 403) — do not reveal that the id exists under another tenant.
        raise HTTPException(status_code=404, detail="Client not found")
    # A client principal may only read its OWN client record; another client's id is a 404, not 403,
    # so it cannot even confirm the other client exists (bounded portal, constraint #2).
    if principal.role == ActorRole.CLIENT.value and row.id != principal.client_id:
        raise HTTPException(status_code=404, detail="Client not found")
    return to_client(row)


@router.post("/{client_id}/creatives:generate", response_model=GeneratedCreative)
async def generate_creative(
    client_id: str,
    body: GenerateCreativeRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> GeneratedCreative:
    return await generate_client_creative(
        session,
        principal=principal,
        client_id=client_id,
        body=body,
    )


@router.get("/{client_id}/creatives/latest", response_model=GeneratedCreative)
async def get_latest_creative(
    client_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> GeneratedCreative:
    client = await repo.get_client(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
    )
    if client is None or not is_client_in_scope(principal, client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    row = await repo.get_latest_creative_doc_for_client(
        session,
        tenant_id=principal.tenant_id,
        client_id=client_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Creative not found")
    return generated_creative_response(to_creative_doc(row))
