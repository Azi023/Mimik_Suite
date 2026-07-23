"""Tenant-scoped creative-render usage aggregation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from importlib import import_module
from importlib.util import find_spec
from types import ModuleType

import pytest_asyncio
from mimik_contracts import UsageReport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.core.config import get_settings
from api.db import repo
from api.db.base import Base


@pytest_asyncio.fixture
async def sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


def _usage_module() -> ModuleType:
    spec = find_spec("api.services.usage")
    assert spec is not None, "api.services.usage must exist"
    return import_module("api.services.usage")


def _manifest(*, kind: str, image_source: object, profile: object) -> dict:
    return {
        "layers": [
            {"kind": "L4_message", "recipe": {"params": {}}},
            {
                "kind": kind,
                "recipe": {
                    "params": {
                        "image_source": image_source,
                        "style_profile_id": profile,
                    }
                },
            },
        ]
    }


async def test_usage_report_groups_l1_params_and_excludes_other_tenants(
    sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch,
) -> None:
    usage = _usage_module()
    window_start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    window_end = datetime(2026, 7, 31, 23, 59, tzinfo=timezone.utc)

    async with sessionmaker() as session:
        tenant = await repo.create_tenant(session, name="Usage tenant", slug="usage-tenant")
        other = await repo.create_tenant(session, name="Other tenant", slug="other-tenant")
        rows = [
            (
                tenant.id,
                "job-at-start",
                window_start,
                _manifest(
                    kind="L1_base",
                    image_source="pexels",
                    profile="glo2go-aesthetics",
                ),
            ),
            (
                tenant.id,
                "job-in-window",
                window_start + timedelta(days=10),
                _manifest(
                    kind="L1_BASE",
                    image_source="ai_illustration",
                    profile="simply-nikah",
                ),
            ),
            (
                tenant.id,
                "job-at-end",
                window_end,
                _manifest(kind="L1_base", image_source=None, profile=123),
            ),
            (
                tenant.id,
                "job-before",
                window_start - timedelta(microseconds=1),
                _manifest(
                    kind="L1_base",
                    image_source="placeholder",
                    profile="outside-window",
                ),
            ),
            (
                tenant.id,
                "job-after",
                window_end + timedelta(microseconds=1),
                _manifest(
                    kind="L1_base",
                    image_source="placeholder",
                    profile="outside-window",
                ),
            ),
            (
                other.id,
                "job-other-tenant",
                window_start + timedelta(days=5),
                _manifest(
                    kind="L1_base",
                    image_source="pexels",
                    profile="glo2go-aesthetics",
                ),
            ),
        ]
        for tenant_id, job_id, created_at, manifest in rows:
            await repo.create_creative_doc(
                session,
                tenant_id=tenant_id,
                job_id=job_id,
                manifest=manifest,
                created_at=created_at,
            )
        await session.commit()

        monkeypatch.setattr(get_settings(), "generation_monthly_cap", 120)
        report = await usage.usage_report(
            session,
            tenant_id=tenant.id,
            window_start=window_start,
            window_end=window_end,
        )

    assert isinstance(report, UsageReport)
    assert UsageReport.model_validate(report.model_dump(mode="json")) == report
    assert report.window_start == window_start
    assert report.window_end == window_end
    assert report.renders == 3
    assert report.by_image_source == {
        "pexels": 1,
        "ai_illustration": 1,
        "unknown": 1,
    }
    assert report.by_profile == {
        "glo2go-aesthetics": 1,
        "simply-nikah": 1,
        "unknown": 1,
    }
    assert report.monthly_cap == 120
