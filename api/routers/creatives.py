"""Creative routes — the "generate" step: persist a CreativeDoc (the 5-layer manifest) for a
job, and list a job's creatives. Rendering to a PNG is deterministic from the manifest and
happens at archive time (see api/services/approval_flow.py), so persisting is browser-free.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, require_role
from api.db import repo
from api.db.mappers import to_brand, to_creative_doc
from api.db.session import get_session
from creative.pipeline import build_manifest
from mimik_contracts import ActorRole, CopyBlock, CreativeDoc, JobStatus

router = APIRouter(prefix="/jobs/{job_id}/creatives", tags=["creatives"])


class CreateCreative(BaseModel):
    template_key: str
    copy_block: CopyBlock
    image_artifact: str | None = None  # cached L1/L2 ref; None -> placeholder brand ground


@router.post("", response_model=CreativeDoc, status_code=201)
async def create_creative(
    job_id: str,
    body: CreateCreative,
    # Generating creatives is a team action — clients never author the engine's output.
    principal: Principal = Depends(require_role("owner", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> CreativeDoc:
    job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    brand_row = await repo.get_brand(session, tenant_id=principal.tenant_id, brand_id=job.brand_id)
    if brand_row is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    manifest = build_manifest(
        to_brand(brand_row),
        body.copy_block,
        job.format_key,
        template_key=body.template_key,
        image_artifact=body.image_artifact,
    )
    row = await repo.create_creative_doc(
        session,
        tenant_id=principal.tenant_id,
        job_id=job_id,
        manifest=manifest.model_dump(mode="json"),
    )
    # First creative moves the job into internal review (ops looks before the client does).
    if job.status in (JobStatus.DRAFT.value, JobStatus.GENERATING.value):
        job.status = JobStatus.INTERNAL_REVIEW.value
        # Generation produced output: close the human-paced generation window.
        job.generation_started_at = None
    await session.commit()
    return to_creative_doc(row)


@router.get("", response_model=list[CreativeDoc])
async def list_creatives(
    job_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[CreativeDoc]:
    job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # A client principal may only see its own client's creatives (bounded portal, data-layer authZ).
    if principal.role == ActorRole.CLIENT.value and principal.client_id != job.client_id:
        raise HTTPException(status_code=404, detail="Job not found")
    rows = await repo.list_creative_docs(session, tenant_id=principal.tenant_id, job_id=job_id)
    return [to_creative_doc(r) for r in rows]
