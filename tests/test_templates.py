"""Layout-template library: renders clean HTML at exact format size, escapes copy, and only
scrims on request."""

from __future__ import annotations

import pytest

from creative.render.templates import (
    TemplateContext,
    available_templates,
    get_template,
)


def _ctx(**over: object) -> TemplateContext:
    base = dict(
        format_key="ig_post",
        headline="Skin boosters, explained",
        cta="Book a consult",
        image_ref="https://assets.example/base.png",
        logo_ref="https://assets.example/logo.svg",
    )
    base.update(over)
    return TemplateContext(**base)  # type: ignore[arg-type]


def test_registry_has_both_templates() -> None:
    keys = {t["key"] for t in available_templates()}
    assert {"centered_hero", "lower_band"} <= keys


def test_unknown_template_raises() -> None:
    with pytest.raises(KeyError):
        get_template("nope")


def test_render_at_exact_format_size() -> None:
    html = get_template("centered_hero").render(_ctx())
    # ig_post is 1080x1080 — the canvas must be exactly that.
    assert "width:1080px" in html and "height:1080px" in html


def test_headline_and_cta_present_and_logo_embedded() -> None:
    html = get_template("centered_hero").render(_ctx())
    assert "Skin boosters, explained" in html
    assert "Book a consult" in html
    assert "logo.svg" in html


def test_copy_is_html_escaped() -> None:
    # Copy is AI/human text — it must never inject markup into the canvas.
    html = get_template("centered_hero").render(_ctx(headline="<script>x</script> & co"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp; co" in html


def test_scrim_only_when_requested() -> None:
    without = get_template("centered_hero").render(_ctx(scrim=False))
    withs = get_template("centered_hero").render(_ctx(scrim=True))
    assert "linear-gradient" not in without
    assert "linear-gradient" in withs


def test_lower_band_keeps_text_off_imagery() -> None:
    # The band is a separate solid region below the image — legibility by construction.
    html = get_template("lower_band").render(_ctx(primary="#2E5BFF"))
    assert "#2E5BFF" in html  # brand band color used
    assert "Skin boosters, explained" in html


def test_no_image_falls_back_to_brand_ground() -> None:
    # Without imagery the hero must still be renderable (uses the brand primary as ground).
    html = get_template("centered_hero").render(_ctx(image_ref=None, primary="#2E5BFF"))
    assert "#2E5BFF" in html
    assert "url(" not in html  # no broken image url when none supplied


# The CSS-breakout payload the security review confirmed against real Chromium: html.escape
# alone cannot stop it, so the render sink itself must reject the shape.
_BREAKOUT = "https://ok/a.png'); outline:10px solid rgb(0,255,0); background-image:url('x"


def test_template_context_rejects_css_breakout_refs() -> None:
    for field in ("image_ref", "logo_ref"):
        with pytest.raises(ValueError, match="asset ref"):
            _ctx(**{field: _BREAKOUT})


def test_template_context_accepts_safe_ref_shapes() -> None:
    _ctx(image_ref="data:image/png;base64,aGk=")
    _ctx(image_ref="artifacts/gpt_image_ab12.png")
    _ctx(logo_ref="https://cdn.example.com/logo.png")


# --- soft_editorial (the client-feedback template) -------------------------------------


def test_color_utils_mix_tint_shade() -> None:
    from creative.render.color import mix, shade, tint

    assert tint("#642766", 1.0) == "#FFFFFF"
    assert shade("#642766", 1.0) == "#000000"
    assert mix("#000000", "#FFFFFF", 0.5) == "#808080"
    assert tint("#642766", 0.0) == "#642766"
    assert mix("#642766", "#FFFFFF", 2.0) == "#FFFFFF"  # t clamps


def test_soft_editorial_registered_and_derives_from_brand_only() -> None:
    from creative.render.templates import SoftEditorial

    keys = {t["key"] for t in available_templates()}
    assert "soft_editorial" in keys
    ctx = _ctx(primary="#642766", accent="#C6F135")  # accent deliberately foreign
    html = get_template("soft_editorial").render(ctx)
    # Every rendered color derives from the brand primary; a foreign accent (another
    # company's color) never reaches the canvas.
    assert "#C6F135" not in html
    pal = SoftEditorial.palette(ctx)
    assert pal["headline"] in html and pal["pill"] in html


@pytest.mark.parametrize("format_key", ["ig_post", "ig_story"])
def test_soft_editorial_zones_respect_safe_area(format_key: str) -> None:
    from mimik_contracts import get_format as _gf

    ctx = _ctx(
        format_key=format_key,
        primary="#642766",
        logo_ref="data:image/png;base64,aGk=",
        subhead="Restores skin quality and elasticity naturally",
    )
    geo = get_template("soft_editorial").geometry(ctx)
    fmt = _gf(format_key)
    sz = fmt.safe_zone
    zones = list(geo.text_zones) + ([geo.logo_zone] if geo.logo_zone else [])
    for zone in zones:
        assert zone.x >= sz.left
        assert zone.y >= sz.top
        assert zone.x + zone.w <= fmt.width - sz.right
        assert zone.y + zone.h <= fmt.height - sz.bottom
    assert geo.text_over_imagery is False


def test_soft_editorial_imagery_gets_own_window_not_ground() -> None:
    ctx = _ctx(primary="#642766", image_ref="data:image/png;base64,aGk=")
    html = get_template("soft_editorial").render(ctx)
    # Imagery sits in its rounded window; the ground stays the brand-tint gradient.
    assert "linear-gradient" in html
    assert "center/cover" in html
    assert get_template("soft_editorial").geometry(ctx).text_over_imagery is False


def test_soft_editorial_overflowing_copy_fails_safe_zone_loud() -> None:
    """Review regression: the QA zone is a SUPERSET of the real content — copy that can't
    fit the badge→wave span must breach the bottom safe zone (fail loud, route to human),
    never be silently clamped into a false pass."""
    from mimik_contracts import get_format as _gf

    ctx = _ctx(
        format_key="fb_post",  # short format: least vertical room
        primary="#642766",
        logo_ref="data:image/png;base64,aGk=",
        image_ref="data:image/png;base64,aGk=",  # imagery window eats 40% of height
        headline="A very long headline that wraps across several lines easily here",
        subhead="An equally long supporting line that keeps going and going with detail "
        "after detail so the pill wraps repeatedly",
    )
    geo = get_template("soft_editorial").geometry(ctx)
    fmt = _gf("fb_post")
    zone = geo.text_zones[0]
    # The estimate is honest: it extends past the bottom safe boundary.
    assert zone.y + zone.h > fmt.height - fmt.safe_zone.bottom


def test_brand_layout_anchors_and_sizes_logo() -> None:
    """A BrandLayout drives the logo to its anchor at the requested size; the geometry the QA
    reasons about matches the rendered position."""
    from mimik_contracts import BrandLayout, LogoPlacement

    layout = BrandLayout(
        logo_placement=LogoPlacement.BOTTOM_RIGHT,
        logo_scale=0.2,
        margins={"top": 5, "right": 5, "bottom": 5, "left": 5},
    )
    ctx = _ctx(layout=layout)
    tmpl = get_template("centered_hero")
    geom = tmpl.geometry(ctx)
    assert geom.logo_zone is not None

    w, h = ctx.size()
    short = min(w, h)
    lh = round(0.2 * short)
    margin = round(0.05 * short)
    # Bottom-right: the logo box hugs the bottom-right inside the 5% margins.
    assert geom.logo_zone.h == lh
    assert geom.logo_zone.y == h - margin - lh
    assert geom.logo_zone.x == w - margin - geom.logo_zone.w
    # And the rendered HTML places it at the same spot.
    html = tmpl.render(ctx)
    assert f"top:{h - margin - lh}px" in html


def test_brand_margins_raise_padding_floor() -> None:
    """Brand margins never drop below the platform safe zone but can demand more room."""
    from mimik_contracts import BrandLayout

    from creative.render.templates import _edge_pads

    wide = BrandLayout(margins={"top": 20, "right": 20, "bottom": 20, "left": 20})
    ctx = _ctx(layout=wide)
    top, right, bottom, left = _edge_pads(ctx, 0.05)
    w, h = ctx.size()
    expected = round(0.20 * min(w, h))
    assert top == expected and left == expected  # 20% dominates the 5% house pad


def test_no_layout_keeps_legacy_logo_position() -> None:
    """Without a BrandLayout the logo stays exactly where the template placed it (no regression)."""
    ctx = _ctx()  # layout is None
    tmpl = get_template("centered_hero")
    geom = tmpl.geometry(ctx)
    assert geom.logo_zone is not None
    # Legacy default anchors the logo at the template's own top/left pad, not the canvas edges.
    assert geom.logo_zone.x > 0 and geom.logo_zone.y > 0


def test_header_footer_bands_render_and_inset_content() -> None:
    """A brand that enables header/footer bands gets brand-colour strips on every template, and
    the content safe-zone floor rises so text/logo clear the bands. None = no band (no regression)."""
    from mimik_contracts import BrandLayout

    from creative.render.templates import _band_height, _edge_pads

    banded = BrandLayout(header=True, footer=True)
    ctx = _ctx(layout=banded)
    w, h = ctx.size()
    band = _band_height(w, h)

    for key in ("centered_hero", "lower_band", "soft_editorial"):
        html = get_template(key).render(ctx)
        assert f"height:{band}px" in html, f"{key} did not render a header/footer band"

    # Content clears the bands: top/bottom pad is at least the band height.
    top, _r, bottom, _l = _edge_pads(ctx, 0.05)
    assert top >= band and bottom >= band

    # No layout → no band strips (legacy render unchanged).
    plain = get_template("centered_hero").render(_ctx())
    assert f"height:{band}px" not in plain
