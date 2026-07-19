"""Brand-QA critic: WCAG math, template geometry vs safe zones, and the hard checks.

Browser-dependent paths (pixel sampling under imagery) gate on browser_available() like
test_compositor.py; everything else is pure code and runs everywhere.
"""

from __future__ import annotations

import base64
import struct

import pytest

from creative.qa.checks import run_brand_qa
from creative.qa.contrast import contrast_ratio, relative_luminance
from creative.render.compositor import browser_available, render_context_to_png, render_html_to_png
from creative.render.templates import TemplateContext, get_template
from mimik_contracts import get_format

_browser = pytest.mark.skipif(not browser_available(), reason="playwright not installed")


def _ctx(**over: object) -> TemplateContext:
    base = dict(
        format_key="ig_post",
        headline="Skin boosters, explained",
        subhead="What they do and who they suit",
        cta="Book a consult",
    )
    base.update(over)
    return TemplateContext(**base)  # type: ignore[arg-type]


def _fake_png(width: int, height: int) -> bytes:
    """Just enough PNG for png_size(): magic + fake chunk header + IHDR dims."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)


# --- pure WCAG math -------------------------------------------------------------------


def test_contrast_ratio_known_pairs() -> None:
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast_ratio("#FFFFFF", "#2E5BFF") == pytest.approx(5.17, abs=0.3)
    assert contrast_ratio("#C6F135", "#0B0D12") > 12  # lime chip / ink label
    assert relative_luminance("#FFFFFF") == pytest.approx(1.0)
    assert relative_luminance("#000000") == pytest.approx(0.0)


# --- geometry vs safe zones -----------------------------------------------------------


@pytest.mark.parametrize("template_key", ["centered_hero", "lower_band"])
@pytest.mark.parametrize("format_key", ["ig_post", "ig_story"])
def test_geometry_zones_respect_safe_area(template_key: str, format_key: str) -> None:
    ctx = _ctx(format_key=format_key, logo_ref="logo.png")
    geo = get_template(template_key).geometry(ctx)
    fmt = get_format(format_key)
    sz = fmt.safe_zone
    zones = list(geo.text_zones) + ([geo.logo_zone] if geo.logo_zone else [])
    assert zones, "template must expose at least a headline zone"
    for zone in zones:
        assert zone.x >= sz.left
        assert zone.y >= sz.top
        assert zone.x + zone.w <= fmt.width - sz.right
        assert zone.y + zone.h <= fmt.height - sz.bottom


# --- hard checks, browser-free paths --------------------------------------------------


async def test_dims_mismatch_fails() -> None:
    report = await run_brand_qa(_fake_png(999, 999), _ctx(), "centered_hero", expect_logo=False)
    assert not report.passed
    assert any(f.startswith("dims:") for f in report.failures)


async def test_missing_logo_ref_fails_when_brand_has_logo() -> None:
    report = await run_brand_qa(_fake_png(1080, 1080), _ctx(), "centered_hero", expect_logo=True)
    assert any(f.startswith("logo:") for f in report.failures)


async def test_solid_ground_bad_pairing_fails_without_scrim_flag() -> None:
    # Near-white ground under white headline: unfixable by a scrim — plain failure.
    ctx = _ctx(primary="#F5F5F5")
    report = await run_brand_qa(_fake_png(1080, 1080), ctx, "centered_hero", expect_logo=False)
    assert not report.passed
    assert any(f.startswith("contrast:") for f in report.failures)
    assert not report.needs_scrim


async def test_defaults_pass_on_solid_brand_ground() -> None:
    report = await run_brand_qa(_fake_png(1080, 1080), _ctx(), "centered_hero", expect_logo=False)
    assert report.passed, report.failures
    assert not report.needs_scrim


async def test_unmapped_template_fails_loud() -> None:
    with pytest.raises(KeyError):
        await run_brand_qa(_fake_png(1080, 1080), _ctx(), "no_such_template", expect_logo=False)


# --- imagery path (pixel sampling) ----------------------------------------------------


@_browser
async def test_light_imagery_ground_flags_needs_scrim() -> None:
    # A light-gray image under white text fails WCAG large-text 3.0 → the conditional
    # scrim is requested (and ONLY requested — never auto-applied here).
    tile = await render_html_to_png('<div style="width:16px;height:16px;background:#BBBBBB"></div>', 16, 16)
    data_uri = "data:image/png;base64," + base64.b64encode(tile).decode("ascii")
    ctx = _ctx(image_ref=data_uri, scrim=False)
    png = await render_context_to_png(ctx, "centered_hero")
    report = await run_brand_qa(png, ctx, "centered_hero", expect_logo=False)
    assert not report.passed
    assert report.needs_scrim

    scrimmed = _ctx(image_ref=data_uri, scrim=True)
    png2 = await render_context_to_png(scrimmed, "centered_hero")
    report2 = await run_brand_qa(png2, scrimmed, "centered_hero", expect_logo=False)
    assert report2.passed, report2.failures


# --- geometry estimate vs real DOM layout ---------------------------------------------

_WORST_HEADLINE = "Everything your brand new summer smile makeover truly needs"  # 59ch/9w
_WORST_SUBHEAD = (
    "Implants, aligners, whitening and same-day fittings, all under one roof "
    "with flexible payment plans available."
)  # ~140 chars


@_browser
@pytest.mark.parametrize("template_key", ["centered_hero", "lower_band"])
@pytest.mark.parametrize("format_key", ["ig_post", "ig_story"])
async def test_geometry_zone_contains_real_dom_text_block(
    template_key: str, format_key: str
) -> None:
    """The geometry text zone is an ESTIMATE — this pins it to reality: the actual rendered
    headline block (worst-case house-legal copy) must sit fully inside the estimated zone,
    else safe-zone and contrast sampling are checking the wrong pixels."""
    from playwright.async_api import async_playwright

    ctx = _ctx(
        format_key=format_key,
        headline=_WORST_HEADLINE,
        subhead=_WORST_SUBHEAD,
        cta="Book your consult",
    )
    template = get_template(template_key)
    html = template.render(ctx)
    zone = template.geometry(ctx).text_zones[0]
    w, h = ctx.size()
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>*{margin:0;padding:0;box-sizing:border-box}html,body{margin:0}</style>"
        f"</head><body>{html}</body></html>"
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page(viewport={"width": w, "height": h})
            await page.set_content(doc, wait_until="load")
            # Union of the actual text elements (h1 + siblings) — the parent itself may be
            # a padded flex band (lower_band), which is not the text block.
            rect = await page.evaluate(
                "() => { const kids = [...document.querySelector('h1').parentElement.children];"
                " const rs = kids.map(k => k.getBoundingClientRect());"
                " return {top: Math.min(...rs.map(r => r.top)),"
                " bottom: Math.max(...rs.map(r => r.bottom)),"
                " left: Math.min(...rs.map(r => r.left)),"
                " right: Math.max(...rs.map(r => r.right))}; }"
            )
        finally:
            await browser.close()
    tol = 2  # sub-pixel rounding
    assert rect["top"] >= zone.y - tol, f"real text starts above the QA zone: {rect} vs {zone}"
    assert rect["bottom"] <= zone.y + zone.h + tol, f"real text overflows the QA zone: {rect} vs {zone}"
    assert rect["left"] >= zone.x - tol
    assert rect["right"] <= zone.x + zone.w + tol


# --- logo visibility (the Glo2Go dogfood lesson) --------------------------------------


def _solid_png_data_uri(hex_color: str, size: int = 8) -> str:
    """A real solid-color RGBA PNG as a data URI, stdlib-only (no PIL)."""
    import base64
    import zlib

    r, g, b = (int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    row = b"\x00" + bytes((r, g, b, 255)) * size
    raw = row * size

    def chunk(typ: bytes, data: bytes) -> bytes:
        payload = typ + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def test_luminance_ratio_math() -> None:
    from creative.qa.contrast import luminance_ratio

    assert luminance_ratio(1.0, 0.0) == pytest.approx(21.0)
    assert luminance_ratio(0.2, 0.2) == pytest.approx(1.0)
    assert luminance_ratio(0.0, 1.0) == luminance_ratio(1.0, 0.0)  # order-independent


async def test_logo_luminance_skips_non_data_refs() -> None:
    from creative.qa.contrast import logo_mean_luminance

    # External URLs would mean a network fetch inside QA — skipped, no browser needed.
    assert await logo_mean_luminance("https://cdn.example.com/logo.png") is None


@_browser
async def test_purple_logo_on_purple_ground_fails_visibility() -> None:
    # The dogfood regression: brand-primary mark on the brand-primary hero ground.
    ctx = _ctx(primary="#8C4F8D", logo_ref=_solid_png_data_uri("#8C4F8D"))
    report = await run_brand_qa(_fake_png(1080, 1080), ctx, "centered_hero", expect_logo=True)
    assert any("mark-vs-ground" in f for f in report.failures), report.failures


@_browser
async def test_white_knockout_logo_on_purple_ground_passes_visibility() -> None:
    ctx = _ctx(primary="#8C4F8D", logo_ref=_solid_png_data_uri("#FFFFFF"))
    report = await run_brand_qa(_fake_png(1080, 1080), ctx, "centered_hero", expect_logo=True)
    assert not any("mark-vs-ground" in f for f in report.failures), report.failures
