"""Brand Kit enrichment is tenant-scoped, additive, and idempotent."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.db import repo
from api.db.base import Base
from api.db.mappers import to_brand
from scripts import seed_brand_kit as seed


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

async def test_enrichment_is_additive_tenant_scoped_and_idempotent(
    session: AsyncSession,
) -> None:
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
    client = await repo.create_client(
        session,
        tenant_id=tenant.id,
        name="Glo2Go Aesthetics",
    )
    brand = await repo.create_brand(
        session,
        tenant_id=tenant.id,
        client_id=client.id,
        name="Glo2Go Aesthetics",
        slug="glo2go-aesthetics",
        tokens={
            "colors": [
                {"name": "primary", "hex": "#5A2A6B"},
                {"name": "legacy", "hex": "#123456", "usage": "Operator-added"},
            ],
            "typography": {
                "font_roles": [
                    {
                        "role": "accent",
                        "source": "builtin",
                        "builtin_key": "raleway",
                    }
                ]
            },
        },
        kit={"discovery": {"mission": "Keep this operator-authored mission."}},
    )

    other_tenant = await repo.create_tenant(session, name="Other", slug="other")
    other_client = await repo.create_client(
        session,
        tenant_id=other_tenant.id,
        name="Glo2Go Aesthetics",
    )
    other_brand = await repo.create_brand(
        session,
        tenant_id=other_tenant.id,
        client_id=other_client.id,
        name="Glo2Go Aesthetics",
        slug="glo2go-aesthetics",
        tokens={"colors": []},
    )
    await session.commit()

    summaries = await seed.enrich_brand_kits(session)
    await session.refresh(brand)
    enriched = to_brand(brand)

    assert [summary.slug for summary in summaries] == ["glo2go-aesthetics"]
    assert {color.name for color in enriched.tokens.colors} == {
        "primary",
        "ink",
        "ground",
        "legacy",
    }
    primary = next(color for color in enriched.tokens.colors if color.name == "primary")
    assert primary.display_name == "Clinical Plum"
    assert primary.rationale == (
        "The medical authority: serious depth without corporate coldness."
    )
    assert primary.confirmed is False
    assert next(color for color in enriched.tokens.colors if color.name == "legacy").usage == (
        "Operator-added"
    )

    roles = {role.role: role for role in enriched.tokens.typography.font_roles}
    assert roles["heading"].builtin_key == "montserrat"
    assert roles["body"].builtin_key == "lato"
    assert roles["accent"].builtin_key == "raleway"
    assert enriched.tokens.typography.heading_font == "Montserrat"
    assert enriched.tokens.typography.body_font == "Lato"

    assert enriched.kit.discovery.purpose
    assert enriched.kit.discovery.personality
    assert enriched.kit.discovery.key_usp
    assert enriched.kit.discovery.mission == "Keep this operator-authored mission."
    assert enriched.kit.direction.palette_rationale
    assert enriched.kit.direction.visual_tone
    assert [pending.name for pending in enriched.kit.pending_colors] == ["accent"]
    assert enriched.kit.pending_colors[0].display_name == "Soft Lilac"

    first_counts = (
        len(enriched.tokens.colors),
        len(enriched.tokens.typography.font_roles),
        len(enriched.kit.pending_colors),
    )
    await seed.enrich_brand_kits(session)
    await session.refresh(brand)
    rerun = to_brand(brand)
    assert (
        len(rerun.tokens.colors),
        len(rerun.tokens.typography.font_roles),
        len(rerun.kit.pending_colors),
    ) == first_counts

    await session.refresh(other_brand)
    assert other_brand.tokens == {"colors": []}


async def test_simply_nikah_gets_builtin_amiri_arabic_role(
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
    )
    await session.commit()

    await seed.enrich_brand_kits(session)
    await session.refresh(brand)
    roles = {role.role: role for role in to_brand(brand).tokens.typography.font_roles}

    assert roles["arabic"].source == "builtin"
    assert roles["arabic"].builtin_key == "amiri"
