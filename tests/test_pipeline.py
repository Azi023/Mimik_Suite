"""End-to-end P2 pipeline: copy → manifest → assemble → composite → QA, on the FREE
placeholder path (no imagery, no spend) and the cached-imagery path with conditional scrim.
"""

from __future__ import annotations

import base64
import json

import pytest

from creative.pipeline import build_manifest, generate_creative, suggest_template
from creative.render.compositor import browser_available, png_size, render_html_to_png
from mimik_contracts import (
    Brand,
    BrandTokens,
    ColorRole,
    CopyBlock,
    CopyStatus,
    LayerKind,
    Typography,
)

_browser = pytest.mark.skipif(not browser_available(), reason="playwright not installed")


def _brand() -> Brand:
    return Brand(
        tenant_id="t1",
        client_id="c1",
        name="RCD Central",
        slug="rcd",
        niche="dental clinic",
        brand_voice="warm, expert, reassuring",
        tokens=BrandTokens(
            colors=[
                ColorRole(name="primary", hex="#0147D3"),
                ColorRole(name="accent", hex="#C6F135"),
            ],
            typography=Typography(heading_font="DM Sans"),
        ),
    )


def _canned_copy(_: str) -> str:
    return json.dumps(
        {"headline": "Smiles, made easy", "subhead": "Same-day fittings", "cta": "Book now"}
    )


def test_suggest_template_by_copy_density() -> None:
    short = CopyBlock(headline="Big smile")
    dense = CopyBlock(
        headline="Everything your new smile needs this season",
        subhead="Implants, aligners and same-day fittings under one roof",
    )
    # With imagery: density decides hero vs band.
    assert suggest_template(short, "ig_post", has_imagery=True) == "centered_hero"
    assert suggest_template(dense, "ig_post", has_imagery=True) == "lower_band"
    # Without imagery: never a flat color plate — the designed soft ground carries it.
    assert suggest_template(short, "ig_post") == "soft_editorial"
    assert suggest_template(dense, "ig_post") == "soft_editorial"


def test_build_manifest_layers_and_template_default() -> None:
    brand = _brand()
    copy = CopyBlock(headline="Big smile")
    bare = build_manifest(brand, copy, "ig_post")
    assert bare.template_key == "soft_editorial"  # placeholder path gets the designed ground
    assert bare.layers == []  # no imagery → free placeholder ground
    with_img = build_manifest(brand, copy, "ig_post", image_artifact="l1.png")
    l1 = with_img.layer(LayerKind.L1_BASE)
    assert l1 is not None and l1.artifact_ref == "l1.png"
    assert with_img.template_key == "centered_hero"


@_browser
async def test_e2e_placeholder_creative_passes_qa() -> None:
    """The P2 gate path: brief+pillar+topic → AI copy (injected) → placeholder brand
    ground → composited PNG that clears the brand-QA hard checks. Zero spend."""
    result = await generate_creative(
        _brand(),
        "promotional",
        "August smile-makeover offer",
        "ig_post",
        generate=_canned_copy,
    )
    assert result.qa.passed, result.qa.failures
    assert png_size(result.png) == (1080, 1080)
    assert not result.scrim_applied
    assert result.manifest.copy_block is not None
    assert result.manifest.copy_block.status == CopyStatus.DRAFT  # human gate still ahead
    assert result.manifest.template_key == "soft_editorial"


@_browser
async def test_e2e_light_imagery_triggers_conditional_scrim() -> None:
    tile = await render_html_to_png('<div style="width:16px;height:16px;background:#BBBBBB"></div>', 16, 16)
    data_uri = "data:image/png;base64," + base64.b64encode(tile).decode("ascii")
    result = await generate_creative(
        _brand(),
        "promotional",
        "August smile-makeover offer",
        "ig_post",
        template_key="centered_hero",
        image_artifact=data_uri,
        generate=_canned_copy,
    )
    assert result.scrim_applied  # contrast flagged → ONE re-render with scrim
    assert result.qa.passed, result.qa.failures
    assert result.context.scrim


@_browser
async def test_e2e_approved_copy_skips_drafting() -> None:
    approved = CopyBlock(headline="Big smile", cta="Book now", status=CopyStatus.APPROVED)
    result = await generate_creative(
        _brand(),
        "promotional",
        "ignored — copy provided",
        "ig_post",
        copy_block=approved,
        require_approved_copy=True,
    )
    assert result.qa.passed, result.qa.failures
    assert result.manifest.copy_block == approved
