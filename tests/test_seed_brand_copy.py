"""Dogfood brand copy seeding fills gaps without overwriting authored content."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.db import repo
from api.db.base import Base
from api.db.mappers import to_brand, to_brief
from scripts import seed_brand_copy as seed


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


async def _create_brand_and_brief(
    session: AsyncSession,
    *,
    tenant_id: str,
    slug: str,
    kit: dict[str, object] | None = None,
    sections: dict[str, object] | None = None,
) -> tuple[api.db.models.BrandRow, api.db.models.BriefRow]:
    client = await repo.create_client(session, tenant_id=tenant_id, name=slug)
    brand = await repo.create_brand(
        session,
        tenant_id=tenant_id,
        client_id=client.id,
        name=slug,
        slug=slug,
        tokens={
            "colors": [{"name": "primary", "hex": "#123456"}],
            "typography": {"heading_font": "Operator Sans"},
        },
        kit=kit or {},
    )
    brief = await repo.create_brief(
        session,
        tenant_id=tenant_id,
        client_id=client.id,
        brand_id=brand.id,
        sections=sections or {},
    )
    return brand, brief


async def test_copy_fields_are_filled_for_all_three_brands_and_second_run_is_a_noop(
    session: AsyncSession,
) -> None:
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
    rows = {
        slug: await _create_brand_and_brief(session, tenant_id=tenant.id, slug=slug)
        for slug in ("simply-nikah", "glo2go-aesthetics", "island-cart")
    }
    await session.commit()

    first = await seed.seed_brand_copy(session)

    assert [summary.slug for summary in first] == [
        "simply-nikah",
        "glo2go-aesthetics",
        "island-cart",
    ]
    assert all(len(summary.filled) == 14 for summary in first)
    assert all(summary.skipped == () for summary in first)

    for slug, (brand_row, brief_row) in rows.items():
        await session.refresh(brand_row)
        await session.refresh(brief_row)
        brand = to_brand(brand_row)
        brief = to_brief(brief_row)

        assert brand.kit.discovery.vision
        assert brand.kit.discovery.visual_competitor_analysis
        assert brand.kit.discovery.existing_brand_review
        assert brand.kit.direction.personality_alignment
        assert brand.kit.direction.competitor_differentiation

        assert brief.sections.snapshot
        assert brief.sections.logo_notes
        assert brief.sections.voice_tone
        assert brief.sections.imagery_style
        assert brief.sections.guardrails_dos
        assert brief.sections.guardrails_donts
        assert brief.sections.references
        assert brief.sections.deliverable_formats
        assert brief.sections.tokens.colors[0].hex == "#123456"
        assert brief.sections.tokens.typography.heading_font == "Operator Sans"
        assert slug in brief.sections.references[0].url

    snapshots = {
        slug: (brand_row.kit, brief_row.sections) for slug, (brand_row, brief_row) in rows.items()
    }
    second = await seed.seed_brand_copy(session)

    assert all(summary.filled == () for summary in second)
    assert all(len(summary.skipped) == 14 for summary in second)
    for slug, (brand_row, brief_row) in rows.items():
        await session.refresh(brand_row)
        await session.refresh(brief_row)
        assert (brand_row.kit, brief_row.sections) == snapshots[slug]


async def test_operator_content_and_other_tenant_are_not_overwritten(
    session: AsyncSession,
) -> None:
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
    brand, brief = await _create_brand_and_brief(
        session,
        tenant_id=tenant.id,
        slug="simply-nikah",
        kit={"discovery": {"vision": "Operator vision"}},
        sections={
            "voice_tone": "Operator voice",
            "tokens": {"colors": [{"name": "accent", "hex": "#ABCDEF"}]},
        },
    )

    other_tenant = await repo.create_tenant(session, name="Other", slug="other")
    other_brand, other_brief = await _create_brand_and_brief(
        session,
        tenant_id=other_tenant.id,
        slug="simply-nikah",
    )
    await session.commit()

    summaries = await seed.seed_brand_copy(session)
    await session.refresh(brand)
    await session.refresh(brief)
    await session.refresh(other_brand)
    await session.refresh(other_brief)

    assert summaries[0].filled
    assert "kit.discovery.vision" in summaries[0].skipped
    assert "brief.voice_tone" in summaries[0].skipped
    assert "brief.tokens" in summaries[0].skipped
    assert to_brand(brand).kit.discovery.vision == "Operator vision"
    seeded_brief = to_brief(brief)
    assert seeded_brief.sections.voice_tone == "Operator voice"
    assert seeded_brief.sections.tokens.colors[0].hex == "#ABCDEF"
    assert other_brand.kit == {}
    assert other_brief.sections == {}
