"""Compositor: a TemplateContext renders to a real PNG at the exact format size.

Skips cleanly where the chromium binary isn't installed (CI without browsers), so the suite
stays green everywhere; runs for real where Playwright is set up.
"""

from __future__ import annotations

import pytest

from creative.render.compositor import browser_available, png_size, render_context_to_png
from creative.render.templates import TemplateContext

pytestmark = pytest.mark.skipif(not browser_available(), reason="playwright not installed")


def _ctx(**over: object) -> TemplateContext:
    base = dict(
        format_key="ig_post",
        headline="Skin boosters, explained",
        cta="Book a consult",
        primary="#2E5BFF",
        accent="#C6F135",
        image_ref=None,  # brand-ground fallback -> no external fetch in the test
    )
    base.update(over)
    return TemplateContext(**base)  # type: ignore[arg-type]


async def test_centered_hero_renders_png_at_format_size() -> None:
    png = await render_context_to_png(_ctx(), "centered_hero", scale=1)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert png_size(png) == (1080, 1080)  # ig_post
    assert len(png) > 1000  # a real, non-empty raster


async def test_lower_band_story_format_size() -> None:
    png = await render_context_to_png(_ctx(format_key="ig_story"), "lower_band", scale=1)
    assert png_size(png) == (1080, 1920)  # ig_story


async def test_scale_factor_doubles_pixels() -> None:
    png = await render_context_to_png(_ctx(format_key="fb_post"), "centered_hero", scale=2)
    assert png_size(png) == (2400, 1260)  # fb_post 1200x630 at 2x device pixels
