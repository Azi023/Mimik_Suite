"""Playwright compositor: render the code layers (L3 scaffold, L4 message, L5 finish) as an
HTML canvas over the AI imagery, screenshotting to a pixel-perfect PNG at the exact format
size. This is the half of the hybrid engine that guarantees legible text, exact logo
placement, and exact brand-hex — the things pure generation cannot.

`render_context_to_png` is the entrypoint used today. Assembling a `TemplateContext` from a
full `CreativeManifest` (brand-token + copy + cached L1/L2 artifact lookup) is a thin service
concern layered on top later — see the P2 build sequence in the plan.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
import struct
from typing import TYPE_CHECKING

from creative.render.templates import TemplateContext, get_template

if TYPE_CHECKING:
    from playwright.async_api import Page

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# One canonical Chromium launch profile for every render path in this module.
_LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]

# Scroll-reveal chrome hides content until an intersection observer fires — which never happens
# in a headless single-shot capture. Force everything visible and freeze motion before capture.
_FREEZE_CSS = "*{opacity:1!important;animation:none!important;transition:none!important}"


@dataclass(frozen=True)
class TextMeasureRequest:
    key: str
    text: str
    font_family: str
    font_size: int
    font_weight: int
    direction: str = "ltr"


@dataclass(frozen=True)
class TextMeasurement:
    x: float
    y: float
    width: float
    height: float


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
    async with chromium_page(width, height, scale=scale) as page:
        return await render_html_on_page(page, html, width, height)


@asynccontextmanager
async def chromium_page(
    width: int,
    height: int,
    *,
    scale: int = 1,
) -> AsyncIterator[Page]:
    """Yield one compositor page so measurement and final capture share a browser instance."""
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=_LAUNCH_ARGS)
        try:
            page = await browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=scale,
            )
            yield page
        finally:
            await browser.close()


async def render_html_on_page(page: Page, html: str, width: int, height: int) -> bytes:
    """Render and capture on an already-open compositor page."""
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>*{margin:0;padding:0;box-sizing:border-box}"
        "html,body{margin:0;background:transparent}</style>"
        f"</head><body>{html}</body></html>"
    )
    await page.set_content(doc, wait_until="load")
    await page.evaluate("document.fonts.ready")
    return await page.screenshot(clip={"x": 0, "y": 0, "width": width, "height": height})


async def render_svg_with_geometry_on_page(
    page: Page,
    svg: str,
    width: int,
    height: int,
) -> tuple[str, bytes]:
    """Render SVG, replace declared bboxes with final DOM geometry, and capture on one page."""
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>*{margin:0;padding:0;box-sizing:border-box}"
        "html,body{margin:0;background:transparent}</style>"
        f"</head><body>{svg}</body></html>"
    )
    await page.set_content(doc, wait_until="load")
    await page.evaluate("document.fonts.ready")
    final_svg = await page.evaluate(
        """() => {
          const root = document.querySelector("svg");
          if (!root) throw new Error("render document has no SVG root");
          const rootRect = root.getBoundingClientRect();
          for (const element of root.querySelectorAll("[data-bbox], text")) {
            if (element.dataset.hidden === "true") continue;
            const rect = element.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) continue;
            const values = [
              Math.round(rect.left - rootRect.left),
              Math.round(rect.top - rootRect.top),
              Math.max(1, Math.round(rect.width)),
              Math.max(1, Math.round(rect.height)),
            ];
            element.setAttribute("data-bbox", values.join(" "));
          }
          return root.outerHTML;
        }"""
    )
    png = await page.screenshot(clip={"x": 0, "y": 0, "width": width, "height": height})
    return '<?xml version="1.0" encoding="utf-8"?>\n' + final_svg, png


async def measure_svg_text(
    page: Page,
    requests: list[TextMeasureRequest],
    *,
    font_css: str = "",
) -> dict[str, TextMeasurement]:
    """Measure SVG text with Chromium's actual font engine on the active render page."""
    await page.set_content(
        (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{font_css}</style></head><body>"
            '<svg id="measure-root" xmlns="http://www.w3.org/2000/svg"></svg>'
            "</body></html>"
        ),
        wait_until="load",
    )
    await page.evaluate("document.fonts.ready")
    raw = await page.evaluate(
        """async requests => {
          const root = document.getElementById("measure-root");
          const ns = "http://www.w3.org/2000/svg";
          const results = {};
          const elements = [];
          for (const request of requests) {
            const text = document.createElementNS(ns, "text");
            text.setAttribute("x", "0");
            text.setAttribute("y", "0");
            text.setAttribute("font-family", request.font_family);
            text.setAttribute("font-size", String(request.font_size));
            text.setAttribute("font-weight", String(request.font_weight));
            text.setAttribute("direction", request.direction);
            text.textContent = request.text;
            root.appendChild(text);
            elements.push([request, text]);
          }
          await document.fonts.ready;
          for (const [request, text] of elements) {
            const bbox = text.getBBox();
            results[request.key] = {
              x: bbox.x,
              y: bbox.y,
              width: text.getComputedTextLength(),
              height: bbox.height,
            };
            text.remove();
          }
          return results;
        }""",
        [
            {
                "key": request.key,
                "text": request.text,
                "font_family": request.font_family,
                "font_size": request.font_size,
                "font_weight": request.font_weight,
                "direction": request.direction,
            }
            for request in requests
        ],
    )
    return {
        key: TextMeasurement(
            x=float(value["x"]),
            y=float(value["y"]),
            width=float(value["width"]),
            height=float(value["height"]),
        )
        for key, value in raw.items()
    }


async def render_context_to_png(ctx: TemplateContext, template_key: str, *, scale: int = 1) -> bytes:
    """Compose L3/L4/L5 via the chosen layout template and render to PNG at the format size."""
    html = get_template(template_key).render(ctx)
    width, height = ctx.size()
    return await render_html_to_png(html, width, height, scale=scale)


async def render_url_to_pdf(url: str) -> bytes:
    """Navigate to `url` (the internal /book/{token}?export=pdf page) and return its print PDF.

    Reuses this module's single Chromium launch profile — the ONE Playwright pattern. Waits for
    network idle so lazy content settles, then freezes scroll-reveal animations so nothing is
    left hidden in the headless single-shot render. `prefer_css_page_size` honours the page's own
    @page size; `print_background` keeps brand colours/grounds in the output.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=_LAUNCH_ARGS)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            await page.add_style_tag(content=_FREEZE_CSS)
            pdf = await page.pdf(print_background=True, prefer_css_page_size=True)
        finally:
            await browser.close()
    return pdf


async def render_url_element_to_png(url: str, selector: str, *, scale: int = 2) -> bytes:
    """Navigate to `url` (the internal /book/{token}?export=png&section=… page) and screenshot the
    one element matching `selector` at `scale`× device pixels (2× for crisp export by default).

    Reuses this module's single Chromium launch profile. Freezes scroll-reveal animations before
    capture so the section isn't left transparent in the headless render.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=_LAUNCH_ARGS)
        try:
            page = await browser.new_page(device_scale_factor=scale)
            await page.goto(url, wait_until="networkidle")
            await page.add_style_tag(content=_FREEZE_CSS)
            element = await page.wait_for_selector(selector, state="visible")
            if element is None:
                raise ValueError(f"section element not found for selector {selector!r}")
            png = await element.screenshot()
        finally:
            await browser.close()
    return png


class Compositor:
    """Object wrapper for the render pipeline (convenient for injection/testing)."""

    async def render(self, ctx: TemplateContext, template_key: str, *, scale: int = 1) -> bytes:
        return await render_context_to_png(ctx, template_key, scale=scale)
