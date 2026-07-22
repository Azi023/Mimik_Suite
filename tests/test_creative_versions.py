"""Creative document lineage and tenant-scoped version history."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.db import repo
from api.db.base import Base


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db_session:
        yield db_session
    await engine.dispose()


async def test_create_creative_doc_builds_and_persists_lineage_chain(
    session: AsyncSession,
) -> None:
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
    first = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id="job-1",
        manifest={"headline": "First"},
    )
    actor = {"id": "designer-1", "role": "designer", "name": "Nadia"}
    second = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id="job-1",
        manifest={"headline": "Second"},
        parent_id=first.id,
        created_by=actor,
        revision_note="Tighten the headline",
    )
    third = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id="job-1",
        manifest={"headline": "Third"},
        parent_id=second.id,
        created_by={"id": "designer-2", "role": "creative_head"},
        revision_note="Final polish",
    )
    await session.commit()

    stored_second = await repo.get_creative_doc(
        session,
        tenant_id=tenant.id,
        creative_doc_id=second.id,
    )
    stored_third = await repo.get_creative_doc(
        session,
        tenant_id=tenant.id,
        creative_doc_id=third.id,
    )

    assert stored_second is not None
    assert stored_second.version == 2
    assert stored_second.parent_id == first.id
    assert stored_second.created_by == actor
    assert stored_second.revision_note == "Tighten the headline"
    assert stored_third is not None
    assert stored_third.version == 3
    assert stored_third.parent_id == second.id


async def test_list_creative_versions_is_ordered_and_tenant_scoped(
    session: AsyncSession,
) -> None:
    tenant_a = await repo.create_tenant(session, name="Agency A", slug="agency-a")
    tenant_b = await repo.create_tenant(session, name="Agency B", slug="agency-b")

    first = await repo.create_creative_doc(
        session, tenant_id=tenant_a.id, job_id="shared-job", manifest={}
    )
    second = await repo.create_creative_doc(
        session,
        tenant_id=tenant_a.id,
        job_id="shared-job",
        manifest={},
        parent_id=first.id,
    )
    third = await repo.create_creative_doc(
        session,
        tenant_id=tenant_a.id,
        job_id="shared-job",
        manifest={},
        parent_id=second.id,
    )
    await repo.create_creative_doc(
        session, tenant_id=tenant_b.id, job_id="shared-job", manifest={}
    )

    versions = await repo.list_creative_versions(
        session, tenant_id=tenant_a.id, job_id="shared-job"
    )

    assert [row.id for row in versions] == [first.id, second.id, third.id]
    assert [row.version for row in versions] == [1, 2, 3]
    assert all(row.tenant_id == tenant_a.id for row in versions)


async def test_create_creative_doc_rejects_cross_tenant_parent(
    session: AsyncSession,
) -> None:
    tenant_a = await repo.create_tenant(session, name="Agency A", slug="agency-a")
    tenant_b = await repo.create_tenant(session, name="Agency B", slug="agency-b")
    foreign_parent = await repo.create_creative_doc(
        session, tenant_id=tenant_a.id, job_id="job-a", manifest={}
    )

    with pytest.raises(
        ValueError,
        match=r"Parent creative document .* was not found in tenant",
    ):
        await repo.create_creative_doc(
            session,
            tenant_id=tenant_b.id,
            job_id="job-b",
            manifest={},
            parent_id=foreign_parent.id,
        )


async def test_create_creative_doc_without_lineage_keeps_default_version(
    session: AsyncSession,
) -> None:
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")

    creative = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id="job-1",
        manifest={"headline": "Original"},
    )

    assert creative.version == 1
    assert creative.parent_id is None
    assert creative.created_by is None
    assert creative.revision_note is None
