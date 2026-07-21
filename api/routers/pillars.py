"""Content-pillar routes — tenant-scoped. A pillar is adopted from a preset OR defined custom.

Planning phase: the client picks which pillars to run for a client before content is produced.
Presets are templates (not tenant data); adopted/custom pillars are tenant-scoped rows.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, require_role
from api.db import repo
from api.db.mappers import to_pillar
from api.db.session import get_session
from mimik_contracts import PILLAR_PRESETS, ActorRole, ContentPillar, PillarPreset, preset

router = APIRouter(prefix="/pillars", tags=["pillars"])

# Creating a pillar is a TEAM action — a bounded client principal never authors content plans.
_TEAM = require_role("owner", "admin", "ops", "designer", "team")


class CreatePillar(BaseModel):
    """Adopt a preset (give `preset_key`) OR define a custom pillar (give `name`)."""

    client_id: str
    preset_key: str | None = None
    name: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "CreatePillar":
        if bool(self.preset_key) == bool(self.name):
            raise ValueError("Provide exactly one of `preset_key` (adopt) or `name` (custom).")
        return self


@router.get("/presets", response_model=list[PillarPreset])
async def list_presets() -> list[PillarPreset]:
    # Presets are static templates, not tenant data — no auth/tenant scope needed.
    return PILLAR_PRESETS


@router.post("", response_model=ContentPillar, status_code=201)
async def create_pillar(
    body: CreatePillar,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> ContentPillar:
    # The client must exist within the caller's tenant — else this is a cross-tenant attach.
    client = await repo.get_client(
        session, tenant_id=principal.tenant_id, client_id=body.client_id
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if body.preset_key is not None:
        try:
            p: PillarPreset = preset(body.preset_key)
        except KeyError:
            raise HTTPException(status_code=422, detail=f"Unknown preset key: {body.preset_key}")
        name, description, is_custom = p.name, p.description, False
    else:
        name, description, is_custom = body.name, body.description, True

    row = await repo.create_pillar(
        session,
        tenant_id=principal.tenant_id,
        client_id=body.client_id,
        name=name,
        description=description,
        is_custom=is_custom,
    )
    await session.commit()
    return to_pillar(row)


@router.get("", response_model=list[ContentPillar])
async def list_pillars(
    client_id: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ContentPillar]:
    # A client principal is confined to its own client's pillars, whatever the query asks for
    # (bounded portal, data-layer authZ; constraint #2).
    if principal.role == ActorRole.CLIENT.value:
        client_id = principal.client_id
    rows = await repo.list_pillars(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    return [to_pillar(r) for r in rows]
