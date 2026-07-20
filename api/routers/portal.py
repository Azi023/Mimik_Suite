"""Magic-link portal READ path — a no-login client opens a shared job to review it.

A magic link is a signed, expiring capability scoped to ONE job (issued by a team member via
`POST /jobs/{id}/magic-link`). It already authorizes approve/comment with no login via
`POST /approvals/magic`; this endpoint completes the loop so the client can SEE what they are
approving — the same one job, its creatives, its brand, and its audit trail, and NOTHING else.

Security posture (see docs/SECURITY_FINDINGS.md D-001):
- Everything is derived from the signed grant claims (tenant_id / job_id / client_id). No client
  input selects the job, so there is no enumeration or cross-job/cross-tenant reach.
- The token travels in the POST body (not the query string) so it stays out of API access logs.
- Anyone holding the link can view+approve — the intended shareable-link trade-off, documented.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.magic_link import MagicLinkError, verify_magic_link
from api.db import repo
from api.db.mappers import to_approval, to_brand, to_creative_doc, to_delivery, to_job
from api.db.session import get_session

router = APIRouter(prefix="/portal", tags=["portal"])


class PortalSessionRequest(BaseModel):
    token: str


@router.post("/session")
async def portal_session(
    body: PortalSessionRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Resolve a magic-link grant to its single job's review bundle (job + creatives + brand + trail)."""
    try:
        grant = verify_magic_link(body.token)
    except MagicLinkError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    tenant_id = grant["tenant_id"]
    job_id = grant["job_id"]
    client_id = grant["client_id"]

    job = await repo.get_job(session, tenant_id=tenant_id, job_id=job_id)
    # The grant names its own client; a job whose client drifted is not this grant's job.
    if job is None or job.client_id != client_id:
        raise HTTPException(status_code=404, detail="Job not found")

    brand = await repo.get_brand(session, tenant_id=tenant_id, brand_id=job.brand_id)
    creatives = await repo.list_creative_docs(session, tenant_id=tenant_id, job_id=job_id)
    approvals = await repo.list_approvals(session, tenant_id=tenant_id, job_id=job_id)
    deliveries = await repo.list_deliveries(session, tenant_id=tenant_id, job_id=job_id)

    return {
        "job": to_job(job).model_dump(mode="json"),
        "brand": to_brand(brand).model_dump(mode="json") if brand is not None else None,
        "creatives": [to_creative_doc(c).model_dump(mode="json") for c in creatives],
        "approvals": [to_approval(a).model_dump(mode="json") for a in approvals],
        "deliveries": [to_delivery(d).model_dump(mode="json") for d in deliveries],
    }
