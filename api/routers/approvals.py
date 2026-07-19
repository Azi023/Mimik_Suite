"""Approval routes — the same audited Approve / Request-change action from two entry points:

- **In-portal** (authenticated): a team member, or a client bound to the job's client_id.
- **Magic-link** (no login): a signed, expiring capability scoped to one job — the frictionless
  client path. Both converge on the same `submit_approval` procedure and audit trail.

Client-role principals may only act on their OWN client's jobs (bounded portal, authZ at the
data layer). Magic links are minted by a team member for a specific job.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, require_role
from api.core.magic_link import MagicLinkError, issue_magic_link, verify_magic_link
from api.db import repo
from api.db.session import get_session
from api.services.approval_flow import (
    ApprovalConflictError,
    ApprovalFlowError,
    submit_approval,
)
from mimik_contracts import Actor, ActorRole, ApprovalAction, RevisionTarget

router = APIRouter(tags=["approvals"])


class ApprovalRequest(BaseModel):
    job_id: str
    action: ApprovalAction
    creative_doc_id: str | None = None  # None -> the job's latest creative
    note: str | None = None
    # reject-reason taxonomy tag on a change request (feeds the learning loop):
    # "too_busy" | "wrong_color" | "logo_small" | "tone_off" | ...
    reason_tag: str | None = None
    # Pin-pointed change asks (REQUEST_CHANGE only): WHERE (zone/layer) + WHAT. Validated
    # by the contract (enum zones, capped instruction); at most a handful per request.
    targets: list[RevisionTarget] = Field(default_factory=list, max_length=10)


class MagicApprovalRequest(BaseModel):
    token: str
    action: ApprovalAction
    creative_doc_id: str | None = None
    note: str | None = None
    reason_tag: str | None = None
    targets: list[RevisionTarget] = Field(default_factory=list, max_length=10)


def _actor_role(role: str) -> ActorRole:
    try:
        return ActorRole(role)
    except ValueError:
        return ActorRole.TEAM  # first-party bootstrap "owner"/unknown attributes as team


async def _latest_creative_id(
    session: AsyncSession, *, tenant_id: str, job_id: str, given: str | None
) -> str:
    if given is not None:
        return given
    docs = await repo.list_creative_docs(session, tenant_id=tenant_id, job_id=job_id)
    if not docs:
        raise HTTPException(status_code=404, detail="Job has no creative to act on")
    return docs[-1].id


async def _apply(
    session: AsyncSession,
    *,
    tenant_id,
    job_id,
    creative_doc_id,
    actor,
    action,
    note,
    reason_tag,
    targets=None,
):
    if targets and action != ApprovalAction.REQUEST_CHANGE:
        raise HTTPException(
            status_code=422, detail="targets are only valid on a request_change action"
        )
    try:
        return await submit_approval(
            session,
            tenant_id=tenant_id,
            job_id=job_id,
            creative_doc_id=creative_doc_id,
            actor=actor,
            action=action,
            note=note,
            reason_tag=reason_tag,
            targets=targets or None,
        )
    except ApprovalConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ApprovalFlowError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/approvals")
async def create_approval(
    body: ApprovalRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # A client principal is bounded to its own client's jobs (data-layer authZ, not route trust).
    if principal.role == ActorRole.CLIENT.value and principal.client_id != job.client_id:
        raise HTTPException(status_code=404, detail="Job not found")

    creative_doc_id = await _latest_creative_id(
        session, tenant_id=principal.tenant_id, job_id=body.job_id, given=body.creative_doc_id
    )
    actor = Actor(id=principal.user_id or principal.tenant_id, role=_actor_role(principal.role))
    return await _apply(
        session,
        tenant_id=principal.tenant_id,
        job_id=body.job_id,
        creative_doc_id=creative_doc_id,
        actor=actor,
        action=body.action,
        note=body.note,
        reason_tag=body.reason_tag,
        targets=body.targets,
    )


class MintMagicLink(BaseModel):
    ttl_hours: int = 72


@router.post("/jobs/{job_id}/magic-link")
async def mint_magic_link(
    job_id: str,
    body: MintMagicLink,
    principal: Principal = Depends(require_role("owner", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    token = issue_magic_link(
        tenant_id=principal.tenant_id,
        job_id=job_id,
        client_id=job.client_id,
        ttl_hours=body.ttl_hours,
    )
    return {"token": token, "job_id": job_id}


@router.post("/approvals/magic")
async def magic_approval(
    body: MagicApprovalRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        grant = verify_magic_link(body.token)
    except MagicLinkError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    tenant_id = grant["tenant_id"]
    job_id = grant["job_id"]
    creative_doc_id = await _latest_creative_id(
        session, tenant_id=tenant_id, job_id=job_id, given=body.creative_doc_id
    )
    # The grant identifies the client; the actor is that client (bounded, no login).
    actor = Actor(id=grant["client_id"], role=ActorRole.CLIENT)
    return await _apply(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        creative_doc_id=creative_doc_id,
        actor=actor,
        action=body.action,
        note=body.note,
        reason_tag=body.reason_tag,
        targets=body.targets,
    )


@router.get("/jobs/{job_id}/approvals")
async def list_job_approvals(
    job_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """The audit trail for a job: every approval action + every delivery, timestamped."""
    job = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # A client principal may only read its own client's audit trail (bounded portal). 404, not
    # 403, so a client cannot even confirm another client's job exists.
    if principal.role == ActorRole.CLIENT.value and principal.client_id != job.client_id:
        raise HTTPException(status_code=404, detail="Job not found")
    from api.db.mappers import to_approval, to_delivery

    approvals = await repo.list_approvals(session, tenant_id=principal.tenant_id, job_id=job_id)
    deliveries = await repo.list_deliveries(session, tenant_id=principal.tenant_id, job_id=job_id)
    return {
        "approvals": [to_approval(a).model_dump(mode="json") for a in approvals],
        "deliveries": [to_delivery(d).model_dump(mode="json") for d in deliveries],
    }
