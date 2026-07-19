"""Assembly: Brand tokens + manifest copy + cached imagery → a render-ready TemplateContext."""

from __future__ import annotations

import pytest

from creative.assemble import AssemblyError, assemble_context
from mimik_contracts import (
    Brand,
    BrandTokens,
    ColorRole,
    CopyBlock,
    CopyStatus,
    CreativeManifest,
    Layer,
    LayerKind,
    LayerRecipe,
    LogoSpec,
    Typography,
)


def _brand(**overrides: object) -> Brand:
    tokens = BrandTokens(
        colors=[
            ColorRole(name="primary", hex="#0147D3"),
            ColorRole(name="accent", hex="#fc0"),  # 3-digit hex must normalize
            ColorRole(name="ink", hex="#101418"),
        ],
        typography=Typography(heading_font="DM Sans", body_font="Inter"),
        logo=LogoSpec(ref="assets/rcd_logo.png"),
    )
    defaults: dict[str, object] = dict(
        tenant_id="t1", client_id="c1", name="RCD Central", slug="rcd", tokens=tokens
    )
    defaults.update(overrides)
    return Brand(**defaults)  # type: ignore[arg-type]


def _manifest(brand: Brand, **overrides: object) -> CreativeManifest:
    defaults: dict[str, object] = dict(
        format_key="ig_post",
        brand_id=brand.id,
        template_key="centered_hero",
        copy_block=CopyBlock(headline="Smiles, made easy", subhead="Same-day fittings", cta="Book now"),
    )
    defaults.update(overrides)
    return CreativeManifest(**defaults)  # type: ignore[arg-type]


def test_assembles_brand_tokens_and_copy() -> None:
    brand = _brand()
    ctx = assemble_context(brand, _manifest(brand))
    assert ctx.headline == "Smiles, made easy"
    assert ctx.primary == "#0147D3"
    assert ctx.accent == "#ffcc00"  # normalized from #fc0
    assert ctx.ink == "#101418"
    assert ctx.logo_ref == "assets/rcd_logo.png"
    assert ctx.heading_font.startswith("'DM Sans',")
    assert ctx.image_ref is None  # no cached imagery → placeholder brand ground
    assert not ctx.scrim


def test_image_ref_prefers_l2_over_l1() -> None:
    brand = _brand()
    layers = [
        Layer(kind=LayerKind.L1_BASE, recipe=LayerRecipe(), artifact_ref="l1.png"),
        Layer(kind=LayerKind.L2_CONCEPT, recipe=LayerRecipe(), artifact_ref="l2.png"),
    ]
    ctx = assemble_context(brand, _manifest(brand, layers=layers))
    assert ctx.image_ref == "l2.png"


def test_tokenless_brand_falls_back_to_house_defaults() -> None:
    brand = _brand(tokens=BrandTokens())
    ctx = assemble_context(brand, _manifest(brand))
    assert ctx.primary == "#2E5BFF"
    assert ctx.logo_ref is None


def test_font_names_are_sanitized_for_css_context() -> None:
    brand = _brand()
    brand.tokens.typography.heading_font = "Evil'; background:url(x)"
    ctx = assemble_context(brand, _manifest(brand))
    assert "'" not in ctx.heading_font.split(",")[0].strip("'")
    assert "url(" not in ctx.heading_font


def test_missing_copy_or_template_fails_loud() -> None:
    brand = _brand()
    with pytest.raises(AssemblyError, match="copy"):
        assemble_context(brand, _manifest(brand, copy_block=None))
    with pytest.raises(AssemblyError, match="template"):
        assemble_context(brand, _manifest(brand, template_key=None))
    with pytest.raises(KeyError):
        assemble_context(brand, _manifest(brand, template_key="nope"))


def test_brand_manifest_mismatch_rejected() -> None:
    brand = _brand()
    other = _brand(slug="other")
    with pytest.raises(AssemblyError, match="brand_id"):
        assemble_context(other, _manifest(brand))


def test_delivery_path_requires_approved_copy() -> None:
    brand = _brand()
    manifest = _manifest(brand)
    with pytest.raises(AssemblyError, match="draft"):
        assemble_context(brand, manifest, require_approved_copy=True)
    manifest.copy_block = manifest.copy_block.model_copy(update={"status": CopyStatus.APPROVED})
    ctx = assemble_context(brand, manifest, require_approved_copy=True)
    assert ctx.headline == manifest.copy_block.headline
