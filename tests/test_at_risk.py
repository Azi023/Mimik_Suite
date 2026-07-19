"""The at-risk sweep, tested directly against a session (no HTTP — it's a background worker).

A local in-memory SQLite engine + sessionmaker mirrors conftest's harness, so the scan can seed
rows via the repo and call `scan_at_risk` with a FIXED `now`. That fixed clock is what makes the
buffer-breach deterministic. Idempotency is the second assertion: a second sweep must not add a
duplicate notification for an already-flagged job.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.db import repo
from api.db.base import Base
from api.services.at_risk import scan_at_risk


@pytest_asyncio.fixture
async def sessionmaker() -> async_sessionmaker:
    """A fresh in-memory DB + sessionmaker per test (same recipe as conftest's client)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _seed_at_risk_job(
    session, *, publish_date: datetime, approval_lead_days: int = 3
) -> tuple[str, str]:
    """Create tenant → client → brand → job (with a publish_date). Returns (tenant_id, job_id)."""
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
    client = await repo.create_client(session, tenant_id=tenant.id, name="RCD Central")
    brand = await repo.create_brand(
        session, tenant_id=tenant.id, client_id=client.id, name="RCD", slug="rcd"
    )
    job = await repo.create_job(
        session,
        tenant_id=tenant.id,
        client_id=client.id,
        brand_id=brand.id,
        title="August offer",
        format_key="ig_post",
        publish_date=publish_date,
        approval_lead_days=approval_lead_days,
    )
    await session.commit()
    return tenant.id, job.id


async def test_scan_flags_at_risk_job_and_records_notification(sessionmaker) -> None:
    now = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)
    # publish_date in the near past -> approve_by (publish - 3d) already breached.
    publish = now - timedelta(days=1)

    async with sessionmaker() as session:
        tenant_id, job_id = await _seed_at_risk_job(session, publish_date=publish)

    async with sessionmaker() as session:
        flagged = await scan_at_risk(session, now=now)

    assert [f["job_id"] for f in flagged] == [job_id]
    assert flagged[0]["tenant_id"] == tenant_id
    assert flagged[0]["approve_by"] == publish - timedelta(days=3)

    # One at-risk notification row was written for the job.
    async with sessionmaker() as session:
        notes = await repo.list_notifications(session, tenant_id=tenant_id)
    at_risk = [n for n in notes if (n.subject or "").startswith("At risk:")]
    assert len(at_risk) == 1
    assert at_risk[0].job_id == job_id
    assert at_risk[0].channel == "in_app"


async def test_scan_is_idempotent_no_duplicate_notification(sessionmaker) -> None:
    now = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)
    publish = now - timedelta(days=1)

    async with sessionmaker() as session:
        tenant_id, job_id = await _seed_at_risk_job(session, publish_date=publish)

    # First sweep flags + notifies; second sweep flags again but must NOT duplicate the row.
    async with sessionmaker() as session:
        first = await scan_at_risk(session, now=now)
    async with sessionmaker() as session:
        second = await scan_at_risk(session, now=now)

    assert [f["job_id"] for f in first] == [job_id]
    assert [f["job_id"] for f in second] == [job_id]  # still reported as at risk

    async with sessionmaker() as session:
        notes = await repo.list_notifications(session, tenant_id=tenant_id)
    at_risk = [n for n in notes if (n.subject or "").startswith("At risk:")]
    assert len(at_risk) == 1  # idempotent: exactly one notification, not two


async def test_scan_ignores_jobs_within_buffer(sessionmaker) -> None:
    now = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)
    # publish far in the future -> approve_by not yet reached -> not at risk.
    publish = now + timedelta(days=30)

    async with sessionmaker() as session:
        tenant_id, _job_id = await _seed_at_risk_job(session, publish_date=publish)

    async with sessionmaker() as session:
        flagged = await scan_at_risk(session, now=now)

    assert flagged == []
    async with sessionmaker() as session:
        notes = await repo.list_notifications(session, tenant_id=tenant_id)
    assert [n for n in notes if (n.subject or "").startswith("At risk:")] == []
