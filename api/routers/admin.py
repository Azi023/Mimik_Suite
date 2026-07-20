"""Admin back-office: provision the accounts that map a Supabase identity to a tenant + role.

This is where authorization is granted. Only an `owner` may issue accounts, and only within
their own tenant. A `client` account is bound to exactly one Client in the tenant — the
bounded-portal principal. Every account is a `UserAccount` row (the authZ source of truth);
the Supabase side only ever authenticates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, require_role
from api.core.capabilities import capabilities_matrix
from api.db import repo
from api.db.mappers import to_user_account
from api.db.session import get_session
from mimik_contracts import ActorRole, UserAccount

router = APIRouter(prefix="/admin", tags=["admin"])

_ROLE_VALUES = {r.value for r in ActorRole}


class ProvisionAccount(BaseModel):
    auth_subject: str        # the Supabase user id to bind (from the provider, out of band)
    role: str
    email: str | None = None
    client_id: str | None = None  # required iff role == "client"
    name: str | None = None


@router.post("/accounts", response_model=UserAccount, status_code=201)
async def provision_account(
    body: ProvisionAccount,
    principal: Principal = Depends(require_role("owner")),
    session: AsyncSession = Depends(get_session),
) -> UserAccount:
    if body.role not in _ROLE_VALUES:
        raise HTTPException(status_code=422, detail=f"Unknown role: {body.role}")

    # A client-portal account MUST be bound to one of the tenant's own clients.
    if body.role == ActorRole.CLIENT.value:
        if not body.client_id:
            raise HTTPException(status_code=422, detail="client_id is required for a client account")
        client = await repo.get_client(
            session, tenant_id=principal.tenant_id, client_id=body.client_id
        )
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found")
    elif body.client_id is not None:
        raise HTTPException(status_code=422, detail="client_id only applies to a client account")

    # A provider identity maps to exactly one account, globally (auth_subject is unique). The
    # pre-check is the common path; the unique constraint + IntegrityError handling below closes
    # the TOCTOU race between two concurrent provisions of the same subject (409, not a 500).
    existing = await repo.get_user_account_by_subject(session, auth_subject=body.auth_subject)
    if existing is not None:
        raise HTTPException(status_code=409, detail="This identity already has an account")

    row = await repo.create_user_account(
        session,
        tenant_id=principal.tenant_id,
        auth_subject=body.auth_subject,
        email=body.email,
        role=body.role,
        client_id=body.client_id,
        name=body.name,
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="This identity already has an account")
    return to_user_account(row)


@router.get("/accounts", response_model=list[UserAccount])
async def list_accounts(
    principal: Principal = Depends(require_role("owner", "ops")),
    session: AsyncSession = Depends(get_session),
) -> list[UserAccount]:
    rows = await repo.list_user_accounts(session, tenant_id=principal.tenant_id)
    return [to_user_account(r) for r in rows]


@router.get("/capabilities")
async def get_capabilities(
    principal: Principal = Depends(require_role("owner", "admin", "super_admin")),
) -> dict[str, list[str]]:
    """The role -> capabilities matrix, so the admin Roles & Permissions screen can render
    'what each role can do'. Read-only, static (derived from the code matrix)."""
    return capabilities_matrix()
