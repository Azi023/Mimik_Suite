"""Brand Kit creative curation stays additive, tenant-scoped, and idempotent."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.db import repo
from api.db.base import Base
from api.db.mappers import to_brand
from scripts import curate_brand_kit as curate


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
    async with maker() as test_session:
        yield test_session
    await engine.dispose()


async def _approved_creative(
    session: AsyncSession,
    *,
    tenant_id: str,
    client_id: str,
    brand_id: str,
    title: str,
    format_key: str,
    pillar_id: str | None = None,
) -> str:
    job = await repo.create_job(
        session,
        tenant_id=tenant_id,
        client_id=client_id,
        brand_id=brand_id,
        title=title,
        format_key=format_key,
        pillar_id=pillar_id,
    )
    creative = await repo.create_creative_doc(
        session,
        tenant_id=tenant_id,
        job_id=job.id,
        manifest={
            "format_key": format_key,
            "brand_id": brand_id,
            "template_key": "centered_hero",
            "layers": [],
        },
    )
    await repo.create_approval(
        session,
        tenant_id=tenant_id,
        job_id=job.id,
        creative_doc_id=creative.id,
        actor={"id": "reviewer", "role": "owner", "name": "Reviewer"},
        action="approve",
    )
    return creative.id


async def test_curation_is_tenant_scoped_additive_and_idempotent(
    session: AsyncSession,
) -> None:
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
    client = await repo.create_client(session, tenant_id=tenant.id, name="Simply Nikah")
    brand = await repo.create_brand(
        session,
        tenant_id=tenant.id,
        client_id=client.id,
        name="Simply Nikah",
        slug="simply-nikah",
        tokens={"colors": []},
        kit={
            "applications": [
                {"kind": "business_card", "asset_id": "existing-card", "caption": "Keep me"}
            ],
            "launch_templates": [
                {"name": "Existing", "format_key": "ig_story", "asset_id": "existing-story"}
            ],
        },
    )
    pillar = await repo.create_pillar(
        session,
        tenant_id=tenant.id,
        client_id=client.id,
        name="Faith Education",
    )
    creative_ids = [
        await _approved_creative(
            session,
            tenant_id=tenant.id,
            client_id=client.id,
            brand_id=brand.id,
            title=f"Launch concept {index}",
            format_key="ig_post" if index % 2 else "ig_story",
            pillar_id=pillar.id if index == 2 else None,
        )
        for index in range(1, 8)
    ]

    unapproved_job = await repo.create_job(
        session,
        tenant_id=tenant.id,
        client_id=client.id,
        brand_id=brand.id,
        title="Unapproved",
        format_key="ig_post",
    )
    unapproved = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id=unapproved_job.id,
        manifest={"format_key": "ig_post", "brand_id": brand.id, "layers": []},
    )

    other_tenant = await repo.create_tenant(session, name="Other", slug="other")
    other_client = await repo.create_client(
        session,
        tenant_id=other_tenant.id,
        name="Simply Nikah",
    )
    other_brand = await repo.create_brand(
        session,
        tenant_id=other_tenant.id,
        client_id=other_client.id,
        name="Simply Nikah",
        slug="simply-nikah",
        tokens={"colors": []},
    )
    await session.commit()

    first = await curate.curate_brand_kits(
        session,
        slug="simply-nikah",
        curate_all=False,
        artifact_exists=lambda creative_id: creative_id != creative_ids[3],
    )
    await session.refresh(brand)
    curated = to_brand(brand)

    assert len(first) == 1
    assert first[0].templates_added == 6
    assert first[0].applications_added == 2
    assert curated.kit.launch_templates[0].asset_id == "existing-story"
    assert curated.kit.applications[0].caption == "Keep me"
    expected_ids = [
        creative_ids[6],
        creative_ids[5],
        creative_ids[4],
        creative_ids[2],
        creative_ids[1],
        creative_ids[0],
    ]
    assert [item.creative_id for item in curated.kit.launch_templates[1:]] == expected_ids
    assert curated.kit.launch_templates[-1].format_key in {"ig_post", "ig_story"}
    pillar_template = next(
        item for item in curated.kit.launch_templates if item.creative_id == creative_ids[1]
    )
    assert pillar_template.name == "Faith Education"
    assert [item.creative_id for item in curated.kit.applications[1:]] == creative_ids[-1:-3:-1]
    assert unapproved.id not in {item.creative_id for item in curated.kit.launch_templates}
    assert creative_ids[3] not in {item.creative_id for item in curated.kit.launch_templates}

    second = await curate.curate_brand_kits(
        session,
        slug="simply-nikah",
        curate_all=False,
        artifact_exists=lambda creative_id: creative_id != creative_ids[3],
    )
    await session.refresh(brand)
    rerun = to_brand(brand)
    assert second[0].templates_added == 0
    assert second[0].applications_added == 0
    assert rerun.kit.model_dump(mode="json") == curated.kit.model_dump(mode="json")

    await session.refresh(other_brand)
    assert other_brand.kit == {}
