"""M-10 brand-font resolution: generation resolves a brand's approved FONT asset and threads it
into the render, tenant-scoped at the data layer. No approved font => None => unchanged render.
"""

from __future__ import annotations

from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.db.base import Base
from api.db.mappers import to_brand
from api.db.models import BrandAssetRow, BrandRow, TenantRow
from api.services.creative_generation import _resolve_brand_font
from mimik_contracts import AssetKind

# A real bundled TTF (built-in font library) so the resolved path points at a genuine font file.
_LATO = str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "builtin" / "lato" / "Lato-Regular.ttf")
_BOLD = str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "builtin" / "lato" / "Lato-Bold.ttf")


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _tenant(session, slug: str) -> TenantRow:
    row = TenantRow(name=slug, slug=slug)
    session.add(row)
    await session.flush()
    return row


async def _brand(session, *, tenant_id: str, slug: str = "g2g") -> BrandRow:
    row = BrandRow(tenant_id=tenant_id, client_id="c1", name="Glo2Go", slug=slug)
    session.add(row)
    await session.flush()
    return row


async def _font_asset(
    session, *, brand: BrandRow, local_path: str, approved: bool
) -> BrandAssetRow:
    row = BrandAssetRow(
        tenant_id=brand.tenant_id,
        client_id=brand.client_id,
        brand_id=brand.id,
        kind=AssetKind.FONT.value,
        filename="brand.ttf",
        mime="font/ttf",
        local_path=local_path,
        approved=approved,
    )
    session.add(row)
    await session.flush()
    return row


async def test_resolve_returns_none_without_font_asset(session) -> None:
    tenant = await _tenant(session, "mimik")
    brand = await _brand(session, tenant_id=tenant.id)
    resolved = await _resolve_brand_font(
        session, tenant_id=tenant.id, brand=to_brand(brand)
    )
    assert resolved is None


async def test_resolve_returns_approved_font_path(session) -> None:
    tenant = await _tenant(session, "mimik")
    brand = await _brand(session, tenant_id=tenant.id)
    await _font_asset(session, brand=brand, local_path=_LATO, approved=True)
    resolved = await _resolve_brand_font(
        session, tenant_id=tenant.id, brand=to_brand(brand)
    )
    assert resolved == _LATO


async def test_resolve_ignores_unapproved_font(session) -> None:
    tenant = await _tenant(session, "mimik")
    brand = await _brand(session, tenant_id=tenant.id)
    await _font_asset(session, brand=brand, local_path=_LATO, approved=False)
    resolved = await _resolve_brand_font(
        session, tenant_id=tenant.id, brand=to_brand(brand)
    )
    assert resolved is None


async def test_resolve_picks_most_recent_approved(session) -> None:
    tenant = await _tenant(session, "mimik")
    brand = await _brand(session, tenant_id=tenant.id)
    # Older approved font, then a newer approved font — the newest wins (created_at order).
    await _font_asset(session, brand=brand, local_path=_LATO, approved=True)
    await _font_asset(session, brand=brand, local_path=_BOLD, approved=True)
    resolved = await _resolve_brand_font(
        session, tenant_id=tenant.id, brand=to_brand(brand)
    )
    assert resolved == _BOLD


async def test_resolve_is_tenant_scoped(session) -> None:
    """Locked #2: a font approved under tenant A must never resolve for tenant B's brand, even
    if the brand ids were to collide — the query filters by tenant_id at the data layer."""
    tenant_a = await _tenant(session, "agency-a")
    tenant_b = await _tenant(session, "agency-b")
    brand_a = await _brand(session, tenant_id=tenant_a.id, slug="brand-a")
    brand_b = await _brand(session, tenant_id=tenant_b.id, slug="brand-b")
    # Only tenant A's brand has an approved font.
    await _font_asset(session, brand=brand_a, local_path=_LATO, approved=True)

    # Tenant B resolving its OWN brand sees nothing.
    assert await _resolve_brand_font(session, tenant_id=tenant_b.id, brand=to_brand(brand_b)) is None
    # And tenant B cannot reach tenant A's font by passing tenant A's brand contract under B's id.
    assert await _resolve_brand_font(session, tenant_id=tenant_b.id, brand=to_brand(brand_a)) is None
    # Tenant A still resolves correctly (control).
    assert await _resolve_brand_font(session, tenant_id=tenant_a.id, brand=to_brand(brand_a)) == _LATO
