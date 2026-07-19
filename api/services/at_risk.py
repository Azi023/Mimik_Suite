"""The at-risk scan: a scheduled background sweep that flags jobs whose approval buffer is
breached and hasn't been approved yet, recording ONE in-app notification per at-risk job.

This is the single deliberately non-tenant-scoped read in the product: it runs in a worker,
not on a request path, so there is no caller tenant to filter by. It therefore MUST NOT be
exposed across a tenant boundary — the notifications it writes are scoped back to each job's
own tenant, and the caller here is a scheduler/cron, never a user.

Idempotent: re-running the sweep does not duplicate an at-risk notification for a job that
already has one (subject prefixed "At risk:"). The scan is pure enough to test with a fixed
`now`; `run_at_risk_sweep` is the thin cron entrypoint that supplies the real clock.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.db import repo
from api.db.mappers import to_job
from mimik_contracts import NotificationChannel

_AT_RISK_PREFIX = "At risk:"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _already_flagged(session: AsyncSession, *, tenant_id: str, job_id: str) -> bool:
    """True if this job already has an at-risk notification (idempotency guard). Targeted to
    the one job so the sweep does not re-scan the whole tenant notification table per job."""
    existing = await repo.list_notifications(session, tenant_id=tenant_id, job_id=job_id)
    return any((n.subject or "").startswith(_AT_RISK_PREFIX) for n in existing)


async def scan_at_risk(session: AsyncSession, *, now: datetime) -> list[dict]:
    """Flag every at-risk job across all tenants, recording one notification per job (idempotent).

    Returns a list of `{"job_id", "tenant_id", "approve_by"}` for the flagged jobs. Commits once
    at the end so a partial failure leaves no half-written notifications.
    """
    rows = await repo.list_scheduled_jobs_all_tenants(session)
    flagged: list[dict] = []
    for row in rows:
        job = to_job(row)  # to_job re-attaches UTC to naive datetimes (see mappers._utc)
        if not job.is_at_risk(now):
            continue
        flagged.append(
            {"job_id": job.id, "tenant_id": job.tenant_id, "approve_by": job.approve_by}
        )
        if await _already_flagged(session, tenant_id=job.tenant_id, job_id=job.id):
            continue  # do not duplicate the nudge
        await repo.create_notification(
            session,
            tenant_id=job.tenant_id,
            client_id=job.client_id,
            job_id=job.id,
            channel=NotificationChannel.IN_APP.value,
            subject=f"{_AT_RISK_PREFIX} {job.title}",
            body=(
                f"Job {job.title!r} must be client-approved by "
                f"{job.approve_by.isoformat() if job.approve_by else 'its deadline'} "
                "to protect its publish buffer."
            ),
        )
    await session.commit()
    return flagged


async def run_at_risk_sweep(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[dict]:
    """Cron entrypoint: open a session and run the scan against the current clock."""
    async with session_factory() as session:
        return await scan_at_risk(session, now=_now())
