"""WCAG 2.x contrast math + per-template color semantics for the brand-QA critic.

Two grounds, two paths:
- Solid ground (no imagery under the zone): the effective background hex is known from the
  template's own semantics — pure math, no browser.
- Imagery ground: the real pixels under the text are sampled in the browser (text hidden,
  zone screenshot, mean relative luminance) — no PIL/numpy, no network (data-URI assets only).
"""

from __future__ import annotations

import base64
from collections.abc import Callable

from creative.render.templates import TemplateContext, ZoneRect


def relative_luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance of an sRGB hex color (#RRGGBB), in [0, 1]."""
    raw = hex_color.lstrip("#")
    channels = [int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG 2.x contrast ratio (Lmax + 0.05) / (Lmin + 0.05); order-independent, in [1, 21]."""
    la, lb = relative_luminance(hex_a), relative_luminance(hex_b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ---------------------------------------------------------------------------------------
# Solid-ground semantics, keyed by template key. A NEW template MUST add its entry here —
# lookups fail loud (KeyError) so an unmapped template can never silently skip the contrast
# gate. Each resolver returns (headline text hex, effective solid ground hex).
# ---------------------------------------------------------------------------------------
HEADLINE_COLOR_SEMANTICS: dict[str, Callable[[TemplateContext], tuple[str, str]]] = {
    # White headline; without imagery the hero ground is the brand primary.
    "centered_hero": lambda ctx: ("#FFFFFF", ctx.primary),
    # The band is always solid brand primary with on_primary text.
    "lower_band": lambda ctx: (ctx.on_primary, ctx.primary),
}


def headline_colors(template_key: str, ctx: TemplateContext) -> tuple[str, str]:
    """(text hex, solid ground hex) for a template's headline. KeyError = unmapped template."""
    return HEADLINE_COLOR_SEMANTICS[template_key](ctx)


def cta_colors(ctx: TemplateContext) -> tuple[str, str]:
    """(label hex, chip background hex) — the CTA chip is accent/ink in every template."""
    return ctx.ink, ctx.accent


# Mean WCAG relative luminance of a decoded PNG, computed entirely in the browser:
# <img> from a data URI -> canvas -> getImageData -> per-pixel linearization.
_MEAN_LUMINANCE_JS = """
async (src) => {
  const img = new Image();
  await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = src; });
  const canvas = document.createElement('canvas');
  canvas.width = img.width; canvas.height = img.height;
  const g = canvas.getContext('2d');
  g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, img.width, img.height).data;
  const lin = (v) => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) {
    sum += 0.2126 * lin(d[i]) + 0.7152 * lin(d[i + 1]) + 0.0722 * lin(d[i + 2]);
  }
  return sum / (d.length / 4);
}
"""


async def sampled_zone_luminance(
    html: str, zone: ZoneRect, viewport: tuple[int, int]
) -> float:
    """Mean relative luminance of what actually renders under a zone's text.

    Renders the canvas with text hidden (visibility only — layout is untouched), screenshots
    the zone clip, then decodes the PNG in a second page (canvas getImageData) so no Python
    image library is needed.
    """
    from playwright.async_api import async_playwright

    width, height = viewport
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>*{margin:0;padding:0;box-sizing:border-box}"
        "html,body{margin:0;background:transparent}"
        "h1,p,span{visibility:hidden}</style>"
        f"</head><body>{html}</body></html>"
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page(
                viewport={"width": width, "height": height}, device_scale_factor=1
            )
            await page.set_content(doc, wait_until="load")
            png = await page.screenshot(
                clip={"x": zone.x, "y": zone.y, "width": zone.w, "height": zone.h}
            )
            data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
            decoder = await browser.new_page()
            mean = await decoder.evaluate(_MEAN_LUMINANCE_JS, data_uri)
        finally:
            await browser.close()
    return float(mean)


async def zone_contrast_over_imagery(
    html: str, zone: ZoneRect, viewport: tuple[int, int], text_hex: str
) -> float:
    """Effective WCAG ratio of a text color against the sampled mean of its imagery ground.

    With ctx.scrim=True the scrim darkens the lower zone, so a re-render after a needs_scrim
    flag is expected to pass for white text.
    """
    ground = await sampled_zone_luminance(html, zone, viewport)
    text = relative_luminance(text_hex)
    return (max(ground, text) + 0.05) / (min(ground, text) + 0.05)
