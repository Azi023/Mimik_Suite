"""Job routes — tenant-scoped. A job references a brand (and thus a client) in the caller's
tenant; optionally a brief and a content pillar. Cross-tenant references are rejected 404.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal
from api.db import repo
from api.db.mappers import to_job
from api.db.session import get_session
from mimik_contracts import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


class CreateJob(BaseModel):
    brand_id: str
    title: str
    format_key: str
    brief_id: str | None = None
    pillar_id: str | None = None
    publish_date: datetime | None = None
    approval_lead_days: int = 3
    assignee: str | None = None


@router.post("", response_model=Job, status_code=201)
async def create_job(
    body: CreateJob,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Job:
    # The brand must belong to the caller's tenant (this also fixes the client_id from the row).
    brand = await repo.get_brand(
        session, tenant_id=principal.tenant_id, brand_id=body.brand_id
    )
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Any referenced brief/pillar must also be the caller's — never trust the body's ids alone.
    if body.brief_id is not None:
        brief = await repo.get_brief(
            session, tenant_id=principal.tenant_id, brief_id=body.brief_id
        )
        if brief is None:
            raise HTTPException(status_code=404, detail="Brief not found")
    if body.pillar_id is not None:
        pillar = await repo.get_pillar(
            session, tenant_id=principal.tenant_id, pillar_id=body.pillar_id
        )
        if pillar is None:
            raise HTTPException(status_code=404, detail="Pillar not found")

    row = await repo.create_job(
        session,
        tenant_id=principal.tenant_id,
        client_id=brand.client_id,
        brand_id=brand.id,
        brief_id=body.brief_id,
        pillar_id=body.pillar_id,
        title=body.title,
        format_key=body.format_key,
        publish_date=body.publish_date,
        approval_lead_days=body.approval_lead_days,
        assignee=body.assignee,
    )
    await session.commit()
    return to_job(row)


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Job:
    row = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return to_job(row)


@router.get("", response_model=list[Job])
async def list_jobs(
    client_id: str | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Job]:
    rows = await repo.list_jobs(session, tenant_id=principal.tenant_id, client_id=client_id)
    return [to_job(r) for r in rows]
