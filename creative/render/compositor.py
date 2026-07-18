"""Playwright compositor: render the code layers (L3 scaffold, L4 message, L5 finish) as an
HTML canvas over the AI imagery, screenshotting to a pixel-perfect PNG at the exact format
size. This is the half of the hybrid engine that guarantees legible text, exact logo
placement, and exact brand-hex — the things pure generation cannot.

`render_context_to_png` is the entrypoint used today. Assembling a `TemplateContext` from a
full `CreativeManifest` (brand-token + copy + cached L1/L2 artifact lookup) is a thin service
concern layered on top later — see the P2 build sequence in the plan.
"""

from __future__ import annotations

import struct

from creative.render.templates import TemplateContext, get_template

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def browser_available() -> bool:
    """True if the Playwright package imports. (The chromium binary is a separate install.)"""
    try:
        import playwright.async_api  # noqa: F401
    except ImportError:
        return False
    return True


def png_size(png: bytes) -> tuple[int, int]:
    """Read (width, height) from a PNG's IHDR header — no image library needed."""
    if png[:8] != _PNG_MAGIC:
        raise ValueError("not a PNG")
    width, height = struct.unpack(">II", png[16:24])
    return width, height


async def render_html_to_png(html: str, width: int, height: int, *, scale: int = 1) -> bytes:
    """Render an HTML fragment to PNG at exactly width×height CSS px (×`scale` device pixels).

    The fragment is dropped into a zero-margin document; the template already sizes its own
    canvas to the format, so the screenshot clip is the format rectangle.
    """
    from playwright.async_api import async_playwright

    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>*{margin:0;padding:0;box-sizing:border-box}"
        "html,body{margin:0;background:transparent}</style>"
        f"</head><body>{html}</body></html>"
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page(
                viewport={"width": width, "height": height}, device_scale_factor=scale
            )
            await page.set_content(doc, wait_until="load")
            png = await page.screenshot(clip={"x": 0, "y": 0, "width": width, "height": height})
        finally:
            await browser.close()
    return png


async def render_context_to_png(ctx: TemplateContext, template_key: str, *, scale: int = 1) -> bytes:
    """Compose L3/L4/L5 via the chosen layout template and render to PNG at the format size."""
    html = get_template(template_key).render(ctx)
    width, height = ctx.size()
    return await render_html_to_png(html, width, height, scale=scale)


class Compositor:
    """Object wrapper for the render pipeline (convenient for injection/testing)."""

    async def render(self, ctx: TemplateContext, template_key: str, *, scale: int = 1) -> bytes:
        return await render_context_to_png(ctx, template_key, scale=scale)
