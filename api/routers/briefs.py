"""Brief routes — tenant-scoped. Create a draft brief for a brand, optionally auto-extracting
§1-5 from a URL; read/list; sign off -> freeze.

Freeze invariant (mirrors `mimik_contracts.Brief`): a FROZEN brief has both `frozen_at` and
`signed_off_by` set, and is locked. Locking is the scope-creep fix — a change after freeze is
a new brief version, never an in-place edit. Signoff on an already-frozen brief is rejected.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal
from api.db import repo
from api.db.mappers import to_brief
from api.db.session import get_session
from api.services.brief_extraction import extract_brief_sections
from mimik_contracts import Brief, BriefSections, BriefStatus

router = APIRouter(prefix="/briefs", tags=["briefs"])


class CreateBrief(BaseModel):
    brand_id: str
    # Optional: if given, §1-5 are auto-extracted from this URL into the draft's sections.
    url: str | None = None


class SignoffBrief(BaseModel):
    signed_off_by: str


@router.post("", response_model=Brief, status_code=201)
async def create_brief(
    body: CreateBrief,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Brief:
    # The brand must exist within the caller's tenant — else cross-tenant attach.
    brand = await repo.get_brand(
        session, tenant_id=principal.tenant_id, brand_id=body.brand_id
    )
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    sections = BriefSections()
    if body.url:
        try:
            sections = await extract_brief_sections(body.url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    row = await repo.create_brief(
        session,
        tenant_id=principal.tenant_id,
        client_id=brand.client_id,
        brand_id=brand.id,
        status=BriefStatus.DRAFT.value,
        sections=sections.model_dump(mode="json"),
    )
    await session.commit()
    return to_brief(row)


@router.get("/{brief_id}", response_model=Brief)
async def get_brief(
    brief_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Brief:
    row = await repo.get_brief(session, tenant_id=principal.tenant_id, brief_id=brief_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    return to_brief(row)


@router.get("", response_model=list[Brief])
async def list_briefs(
    client_id: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Brief]:
    rows = await repo.list_briefs(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    return [to_brief(r) for r in rows]


@router.post("/{brief_id}/signoff", response_model=Brief)
async def signoff_brief(
    brief_id: str,
    body: SignoffBrief,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Brief:
    row = await repo.get_brief(session, tenant_id=principal.tenant_id, brief_id=brief_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    if row.status == BriefStatus.FROZEN.value:
        # Already locked — a change now is a new version, not a re-signoff (non-destructive).
        raise HTTPException(status_code=409, detail="Brief is already frozen.")

    row.status = BriefStatus.FROZEN.value
    row.signed_off_by = body.signed_off_by
    row.frozen_at = datetime.now(timezone.utc)
    await session.commit()
    return to_brief(row)
