"""Brand-memory service: storage path discipline, logo wiring, and ingestion policy
(attach iff critic-fits or human-forced; signals only for attached references)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables)
from api.core import config
from api.db import repo
from api.db.base import Base
from api.db.models import BrandAssetRow, BrandRow, TenantRow
from api.services import brand_memory
from creative.references.fit_critic import FitVerdict, StyleDescriptor
from mimik_contracts import AssetStudy

_PNG = b"\x89PNG\r\n\x1a\n fake-bytes"


@pytest.fixture
def assets_root(tmp_path: Path):
    config._settings = config.Settings(assets_local_root=str(tmp_path / "assets"))
    yield tmp_path / "assets"
    config._settings = None


_TTF = b"\x00\x01\x00\x00" + b"\x00" * 20
_PHP = b"<?php system($_GET[0]); ?>" + b"\x00" * 20
_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def test_store_asset_file_uses_server_named_paths(assets_root: Path) -> None:
    path, mime = brand_memory.store_asset_file(
        tenant_id="t1", brand_id="b1", kind="logo", data=_PNG
    )
    stored = Path(path)
    assert stored.exists() and stored.read_bytes() == _PNG
    assert mime == "image/png", "the TRUSTED mime is sniffed from bytes, not a header"
    # Server-generated name (uuid.ext) under tenant/brand — the client filename never
    # touches the filesystem, and the path shape survives the asset-ref validator.
    assert stored.parent == assets_root / "t1" / "b1"
    assert stored.suffix == ".png"
    assert " " not in path and "'" not in path


def test_store_asset_file_rejects_disguised_scripts_and_svg(assets_root: Path) -> None:
    """The upload gate is the MAGIC BYTES, not the header. A PHP/HTML/script or a scriptable
    SVG disguised as image/png is rejected no matter what Content-Type claims."""
    for payload in (_PHP, _SVG, b"GIF89a" + b"\x00" * 20, b"%PDF-1.4" + b"\x00" * 20):
        with pytest.raises(brand_memory.UnsupportedAssetMime):
            brand_memory.store_asset_file(tenant_id="t1", brand_id="b1", kind="logo", data=payload)


def test_store_asset_file_rejects_oversize_and_cross_kind(assets_root: Path) -> None:
    with pytest.raises(brand_memory.AssetTooLarge):
        brand_memory.store_asset_file(
            tenant_id="t1", brand_id="b1", kind="logo",
            data=b"x" * (brand_memory.MAX_ASSET_BYTES + 1),
        )
    # A real TTF uploaded as an image kind (or a PNG as a font) is cross-kind → rejected.
    with pytest.raises(brand_memory.UnsupportedAssetMime):
        brand_memory.store_asset_file(tenant_id="t1", brand_id="b1", kind="logo", data=_TTF)
    with pytest.raises(brand_memory.UnsupportedAssetMime):
        brand_memory.store_asset_file(tenant_id="t1", brand_id="b1", kind="font", data=_PNG)
    # ...but a real TTF as kind=font is accepted, with the trusted mime.
    _path, mime = brand_memory.store_asset_file(
        tenant_id="t1", brand_id="b1", kind="font", data=_TTF
    )
    assert mime == "font/ttf"


def test_safe_display_filename_strips_paths_and_control_chars() -> None:
    assert brand_memory.safe_display_filename("../../etc/passwd") == "passwd"
    assert brand_memory.safe_display_filename("a\\b\\evil.png") == "evil.png"
    dangerous = brand_memory.safe_display_filename('x"><img>.png')
    assert all(c not in dangerous for c in '"<>'), dangerous
    assert brand_memory.safe_display_filename(None) == "upload"
    assert brand_memory.safe_display_filename("") == "upload"


def _study(**overrides: object) -> AssetStudy:
    base: dict[str, object] = {
        "mood": "clean clinical",
        "palette": ["#8E4B8F", "#FFFFFF"],
        "composition": "centered",
        "complexity": "minimal",
        "copy_text": "Glow from within",
    }
    base.update(overrides)
    return AssetStudy.model_validate(base)


def _fits_verdict() -> str:
    return (
        '{"fit_score": 0.85, "fits": true, "reasoning": "matches the purple-on-white house '
        'style", "style": {"mood": "clean", "palette": ["#8E4B8F"], "composition": "centered", '
        '"lighting": "soft", "complexity": "minimal"}}'
    )


def _no_fit_verdict() -> str:
    return '{"fit_score": 0.2, "fits": false, "reasoning": "off-brand neon rave aesthetic"}'


def test_verdict_shapes_parse() -> None:
    # Sanity-check the canned verdicts against the real FitVerdict model, so the ingestion
    # tests below are exercising realistic critic replies.
    v = FitVerdict.model_validate(json.loads(_fits_verdict()))
    assert v.fits and isinstance(v.style, StyleDescriptor)
    nv = FitVerdict.model_validate(json.loads(_no_fit_verdict()))
    assert not nv.fits


# --- service-level: wire_approved_logo + ingest_reference_creative --------------------


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


async def _brand_and_asset(session, assets_root, *, kind: str = "reference_creative"):
    tenant = TenantRow(name="Mimik", slug="mimik")
    session.add(tenant)
    await session.flush()
    brand = BrandRow(
        tenant_id=tenant.id, client_id="c1", name="Glo2Go", slug="g2g",
        brand_voice="professional yet approachable",
    )
    session.add(brand)
    await session.flush()
    path, _mime = brand_memory.store_asset_file(
        tenant_id=tenant.id, brand_id=brand.id, kind=kind, data=_PNG
    )
    asset = BrandAssetRow(
        tenant_id=tenant.id, client_id="c1", brand_id=brand.id, kind=kind,
        filename="x.png", mime="image/png", local_path=path,
    )
    session.add(asset)
    await session.flush()
    return brand, asset


async def test_wire_approved_logo_sets_data_uri(session, assets_root) -> None:
    brand, asset = await _brand_and_asset(session, assets_root, kind="logo")
    await brand_memory.wire_approved_logo(session, brand=brand, asset=asset)
    ref = brand.tokens["logo"]["ref"]
    assert ref.startswith("data:image/png;base64,")
    # The stored bytes round-trip through the URI.
    assert base64.b64decode(ref.split(",", 1)[1]) == _PNG


async def test_wire_approved_logo_fails_loud_on_missing_file(session, assets_root) -> None:
    brand, asset = await _brand_and_asset(session, assets_root, kind="logo")
    Path(asset.local_path).unlink()
    with pytest.raises(FileNotFoundError):
        await brand_memory.wire_approved_logo(session, brand=brand, asset=asset)


async def test_ingest_service_attach_and_signal(session, assets_root) -> None:
    brand, asset = await _brand_and_asset(session, assets_root)
    result = await brand_memory.ingest_reference_creative(
        session,
        brand=brand,
        asset=asset,
        actor_role="team",
        study_fn=lambda b, m: _study(),
        critic_generate=lambda p: _fits_verdict(),
    )
    assert result.attached and result.signals_recorded == 1
    assert brand.references[0]["url"] == f"asset://{asset.id}"
    assert asset.study["mood"] == "clean clinical"
    # The seeded signal is client-scoped, team-attributed, PICK-sourced.
    signals = await repo.list_preference_signals(
        session, tenant_id=brand.tenant_id, client_id="c1"
    )
    assert len(signals) == 1
    assert signals[0].actor_role == "team"
    assert signals[0].attributes["palette_primary"] == "#8E4B8F"


async def test_ingest_service_no_fit_no_mutation_unless_forced(session, assets_root) -> None:
    brand, asset = await _brand_and_asset(session, assets_root)
    result = await brand_memory.ingest_reference_creative(
        session, brand=brand, asset=asset, actor_role="team",
        study_fn=lambda b, m: _study(), critic_generate=lambda p: _no_fit_verdict(),
    )
    assert not result.attached and result.signals_recorded == 0
    assert not brand.references
    forced = await brand_memory.ingest_reference_creative(
        session, brand=brand, asset=asset, actor_role="team", force_attach=True,
        study_fn=lambda b, m: _study(), critic_generate=lambda p: _no_fit_verdict(),
    )
    assert forced.attached and len(brand.references) == 1
    # The reject verdict is preserved for the audit trail even on a forced attach.
    assert forced.verdict.fits is False


# --- knockout logo derivation ---------------------------------------------------------


def _solid_png(hex_color: str, size: int = 8) -> bytes:
    """A real solid-color RGBA PNG, stdlib-only."""
    import struct
    import zlib

    r, g, b = (int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    row = b"\x00" + bytes((r, g, b, 255)) * size
    raw = row * size

    def chunk(typ: bytes, data: bytes) -> bytes:
        payload = typ + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _browser_available() -> bool:
    from creative.render.compositor import browser_available

    return browser_available()


@pytest.mark.skipif(not _browser_available(), reason="playwright not installed")
async def test_derive_knockout_logo_turns_mark_white(session, assets_root) -> None:
    from creative.qa.contrast import logo_mean_luminance

    tenant = TenantRow(name="Mimik", slug="mimik")
    session.add(tenant)
    await session.flush()
    brand = BrandRow(tenant_id=tenant.id, client_id="c1", name="Glo2Go", slug="g2g")
    session.add(brand)
    await session.flush()
    purple = _solid_png("#8C4F8D")
    path, _mime = brand_memory.store_asset_file(
        tenant_id=tenant.id, brand_id=brand.id, kind="logo", data=purple
    )
    asset = BrandAssetRow(
        tenant_id=tenant.id, client_id="c1", brand_id=brand.id, kind="logo",
        filename="Logo.png", mime="image/png", local_path=path,
    )
    session.add(asset)
    await session.flush()

    variant = await brand_memory.derive_knockout_logo(session, brand=brand, asset=asset)
    assert variant.approved is False  # never born approved — the human still gates it
    assert variant.filename == "knockout-Logo.png"
    assert variant.id != asset.id and Path(variant.local_path).exists()

    # Pixel truth: the derived mark is white (mean opaque luminance ~ 1.0).
    knocked = Path(variant.local_path).read_bytes()
    data_uri = "data:image/png;base64," + base64.b64encode(knocked).decode("ascii")
    lum = await logo_mean_luminance(data_uri)
    assert lum is not None and lum > 0.95
