"""Ops routes — the internal Kanban board + calendar + card status-transitions.

Tenant-scoped like every request path: `tenant_id` comes from the auth token, never the body,
so a caller can only see and move its own tenant's jobs (IDOR defence at the data layer).

The →Approved transition is special: it does NOT set the status directly. It converges on the
same `submit_approval` procedure the client-approval route uses, so the auto-archive side-effect
(render → archive → Delivery → status ARCHIVED) fires from one place regardless of entry point.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, get_principal, require_role
from api.db import repo
from api.db.mappers import to_job
from api.db.session import get_session
from api.routers.jobs import _TEAM
from api.services import command_center, generation_queue, usage
from api.services.approval_flow import ApprovalFlowError, submit_approval
from api.services.command_center import CommandParseError
from mimik_contracts import (
    Actor,
    ActorRole,
    ApprovalAction,
    BoardCard,
    BoardResponse,
    CalendarEntry,
    CommandExecutionResult,
    CommandPlan,
    CommandRequest,
    GenerationQueueItem,
    Job,
    JobStatus,
    QueueStats,
    UsageReport,
)

router = APIRouter(tags=["ops"])

# Stable column order for the board — every JobStatus, left-to-right through the pipeline.
_COLUMN_ORDER: tuple[JobStatus, ...] = (
    JobStatus.DRAFT,
    JobStatus.GENERATING,
    JobStatus.INTERNAL_REVIEW,
    JobStatus.CLIENT_REVIEW,
    JobStatus.APPROVED,
    JobStatus.DELIVERED,
    JobStatus.ARCHIVED,
    JobStatus.BLOCKED,
)

# Forward-ish pipeline transitions. BLOCKED is reachable from anywhere and can return to the
# stage a job was blocked at; nonsense jumps (e.g. archived -> draft) are rejected 409.
_ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.DRAFT: {JobStatus.GENERATING, JobStatus.INTERNAL_REVIEW},
    JobStatus.GENERATING: {JobStatus.INTERNAL_REVIEW, JobStatus.DRAFT},
    JobStatus.INTERNAL_REVIEW: {JobStatus.CLIENT_REVIEW, JobStatus.GENERATING},
    JobStatus.CLIENT_REVIEW: {JobStatus.APPROVED, JobStatus.INTERNAL_REVIEW},
    JobStatus.APPROVED: {JobStatus.DELIVERED, JobStatus.ARCHIVED},
    JobStatus.DELIVERED: {JobStatus.ARCHIVED},
    JobStatus.ARCHIVED: set(),
    JobStatus.BLOCKED: {
        JobStatus.DRAFT,
        JobStatus.GENERATING,
        JobStatus.INTERNAL_REVIEW,
        JobStatus.CLIENT_REVIEW,
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _actor_role(role: str) -> ActorRole:
    """Map a principal role to a contract ActorRole; unknown/bootstrap roles attribute as TEAM."""
    try:
        return ActorRole(role)
    except ValueError:
        return ActorRole.TEAM


def _card(job: Job, now: datetime) -> BoardCard:
    """A board/calendar card: the serialized Job plus the computed at-risk flag. `to_job`
    already re-attaches UTC to naive datetimes (see mappers._utc), so is_at_risk never mixes
    naive/aware datetimes."""
    return BoardCard(job=job, at_risk=job.is_at_risk(now))


def _transition_allowed(current: JobStatus, target: JobStatus) -> bool:
    if target == current:
        return False
    if target == JobStatus.BLOCKED:
        return True  # a job may be blocked from any state
    return target in _ALLOWED_TRANSITIONS.get(current, set())


class TransitionRequest(BaseModel):
    to_status: JobStatus
    note: str | None = None
    creative_doc_id: str | None = None


class EnqueueGenerationRequest(BaseModel):
    client_id: str
    topic: str
    pillar: str | None = None
    format_key: str = "ig_post"


@router.get("/ops/queue", response_model=list[GenerationQueueItem])
async def get_queue(
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> list[GenerationQueueItem]:
    return await generation_queue.list_queue(
        session,
        tenant_id=principal.tenant_id,
    )


@router.get("/ops/queue/stats", response_model=QueueStats)
async def get_queue_stats(
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> QueueStats:
    return await generation_queue.queue_stats(
        session,
        tenant_id=principal.tenant_id,
    )


@router.post("/ops/queue", response_model=GenerationQueueItem, status_code=201)
async def enqueue_generation(
    body: EnqueueGenerationRequest,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> GenerationQueueItem:
    return await generation_queue.enqueue_generation(
        session,
        principal=principal,
        client_id=body.client_id,
        topic=body.topic,
        pillar=body.pillar,
        format_key=body.format_key,
    )


@router.post("/ops/command", response_model=CommandPlan)
async def preview_command(
    body: CommandRequest,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> CommandPlan:
    """The ⌘K cockpit — dry-run. Parse operator free text ("generate 5 Educational posts for
    Glo2Go this week") into a constrained CommandPlan for confirmation. Team-gated (operator-only,
    same gate as the queue routes); nothing is enqueued here. Unresolvable references → 422."""
    try:
        return await command_center.build_plan(
            session, principal=principal, text=body.text
        )
    except CommandParseError as exc:
        raise HTTPException(status_code=422, detail=exc.message)


@router.post("/ops/command/execute", response_model=CommandExecutionResult, status_code=201)
async def execute_command(
    body: CommandRequest,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> CommandExecutionResult:
    """Confirm step: re-parse under the operator's tenant scope and fan out into N queued
    generation jobs via the existing A-03 queue path. Team-gated; every job is tenant-scoped +
    audited. Unresolvable references → 422 (nothing is enqueued)."""
    try:
        return await command_center.execute_plan(
            session, principal=principal, text=body.text
        )
    except CommandParseError as exc:
        raise HTTPException(status_code=422, detail=exc.message)


@router.get("/ops/usage", response_model=UsageReport)
async def get_usage(
    start: datetime | None = None,
    end: datetime | None = None,
    principal: Principal = Depends(_TEAM),
    session: AsyncSession = Depends(get_session),
) -> UsageReport:
    now = _now()
    window_start = start or now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    window_end = end or now
    if window_start > window_end:
        raise HTTPException(status_code=422, detail="start must be <= end")
    return await usage.usage_report(
        session,
        tenant_id=principal.tenant_id,
        window_start=window_start,
        window_end=window_end,
    )


@router.get("/ops/board", response_model=BoardResponse)
async def board(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> BoardResponse:
    """The Kanban board: every job grouped by status into a stable column order. Each card is
    `{"job": <Job>, "at_risk": bool}`; every column key is present even when empty."""
    now = _now()
    # A client principal (should it reach this internal view) sees ONLY its own client's jobs —
    # never the whole tenant's board (bounded portal, data-layer authZ; constraint #2).
    client_filter = (
        principal.client_id if principal.role == ActorRole.CLIENT.value else None
    )
    rows = await repo.list_jobs(session, tenant_id=principal.tenant_id, client_id=client_filter)
    columns: dict[JobStatus, list[BoardCard]] = {status: [] for status in _COLUMN_ORDER}
    for row in rows:
        job = to_job(row)
        columns[job.status].append(_card(job, now))
    return BoardResponse(columns=columns)


@router.get("/ops/calendar", response_model=list[CalendarEntry])
async def calendar(
    start: datetime | None = None,
    end: datetime | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[BoardCard]:
    """Jobs whose publish_date falls in [start, end]. Defaults to a 30-day window from now."""
    now = _now()
    if start is None:
        start = now
    if end is None:
        end = start + timedelta(days=30)
    if start > end:
        raise HTTPException(status_code=422, detail="start must be <= end")
    rows = await repo.list_jobs_in_publish_window(
        session, tenant_id=principal.tenant_id, start=start, end=end
    )
    # Confine a client principal to its own client's jobs (bounded portal; constraint #2).
    if principal.role == ActorRole.CLIENT.value:
        rows = [r for r in rows if r.client_id == principal.client_id]
    return [_card(to_job(row), now) for row in rows]


@router.post("/ops/jobs/{job_id}/transition", response_model=dict[str, object])
async def transition(
    job_id: str,
    body: TransitionRequest,
    principal: Principal = Depends(require_role("owner", "ops", "designer", "team")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Move a card. Team roles only. →Approved converges on the shared approval procedure so the
    auto-archive side-effect fires; every other move validates the transition then sets status."""
    row = await repo.get_job(session, tenant_id=principal.tenant_id, job_id=job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    current = JobStatus(row.status)
    target = body.to_status
    if not _transition_allowed(current, target):
        raise HTTPException(
            status_code=409, detail=f"Illegal transition {current.value} -> {target.value}"
        )

    if target == JobStatus.APPROVED:
        # Resolve the creative (explicit id, else the job's latest) and run the shared approval
        # procedure — the SAME auto-archive path the client-approval route uses.
        creative_doc_id = body.creative_doc_id
        if creative_doc_id is None:
            docs = await repo.list_creative_docs(
                session, tenant_id=principal.tenant_id, job_id=job_id
            )
            if not docs:
                raise HTTPException(status_code=404, detail="Job has no creative to approve")
            creative_doc_id = docs[-1].id
        actor = Actor(
            id=principal.user_id or principal.tenant_id, role=_actor_role(principal.role)
        )
        try:
            return await submit_approval(
                session,
                tenant_id=principal.tenant_id,
                job_id=job_id,
                creative_doc_id=creative_doc_id,
                actor=actor,
                action=ApprovalAction.APPROVE,
                note=body.note,
            )
        except ApprovalFlowError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    # Track the human-paced generation window: stamp on entering GENERATING, clear on leaving,
    # so the board can show an honest "generating since X" rather than imply instant output.
    if target == JobStatus.GENERATING:
        row.generation_started_at = _now()
    elif current == JobStatus.GENERATING:
        row.generation_started_at = None

    row.status = target.value
    await session.commit()
    return {"job": to_job(row)}
