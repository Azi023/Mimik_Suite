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

from creative.render.templates import SoftEditorial, TemplateContext, ZoneRect


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
def _soft_editorial_headline(ctx: TemplateContext) -> tuple[str, str]:
    # Same derivation the template renders with — deep brand headline on the tint ground.
    pal = SoftEditorial.palette(ctx)
    return pal["headline"], pal["ground_top"]


HEADLINE_COLOR_SEMANTICS: dict[str, Callable[[TemplateContext], tuple[str, str]]] = {
    # White headline; without imagery the hero ground is the brand primary.
    "centered_hero": lambda ctx: ("#FFFFFF", ctx.primary),
    # The band is always solid brand primary with on_primary text.
    "lower_band": lambda ctx: (ctx.on_primary, ctx.primary),
    "soft_editorial": _soft_editorial_headline,
}


def headline_colors(template_key: str, ctx: TemplateContext) -> tuple[str, str]:
    """(text hex, solid ground hex) for a template's headline. KeyError = unmapped template."""
    return HEADLINE_COLOR_SEMANTICS[template_key](ctx)


def _soft_editorial_cta(ctx: TemplateContext) -> tuple[str, str]:
    return "#FFFFFF", SoftEditorial.palette(ctx)["pill"]


# Per-template CTA semantics. The default chip is accent/ink; templates that render their
# own chip colors declare them here so QA checks what actually renders.
CTA_COLOR_SEMANTICS: dict[str, Callable[[TemplateContext], tuple[str, str]]] = {
    "soft_editorial": _soft_editorial_cta,
}


def cta_colors(ctx: TemplateContext, template_key: str | None = None) -> tuple[str, str]:
    """(label hex, chip background hex) for a template's CTA chip."""
    if template_key is not None and template_key in CTA_COLOR_SEMANTICS:
        return CTA_COLOR_SEMANTICS[template_key](ctx)
    return ctx.ink, ctx.accent


def _soft_editorial_logo_ground(ctx: TemplateContext) -> str:
    return SoftEditorial.palette(ctx)["badge"]


# Per-template LOGO ground: where the mark actually sits. Default is the headline's solid
# ground; templates that place the logo on their own surface (e.g. a badge pill) declare it.
LOGO_GROUND_SEMANTICS: dict[str, Callable[[TemplateContext], str]] = {
    "soft_editorial": _soft_editorial_logo_ground,
}


def logo_ground(template_key: str, ctx: TemplateContext) -> str:
    """Solid hex the logo sits on for this template."""
    if template_key in LOGO_GROUND_SEMANTICS:
        return LOGO_GROUND_SEMANTICS[template_key](ctx)
    return headline_colors(template_key, ctx)[1]


def luminance_ratio(lum_a: float, lum_b: float) -> float:
    """WCAG contrast ratio from two relative luminances; order-independent, in [1, 21]."""
    return (max(lum_a, lum_b) + 0.05) / (min(lum_a, lum_b) + 0.05)


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


# Alpha-weighted variant for logos: only opaque-ish pixels (a >= 16) count, so transparent
# padding can't dilute the mark's real color toward black. Returns null if nothing opaque.
_MEAN_OPAQUE_LUMINANCE_JS = """
async (src) => {
  const img = new Image();
  await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = src; });
  const canvas = document.createElement('canvas');
  canvas.width = img.width; canvas.height = img.height;
  const g = canvas.getContext('2d');
  g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, img.width, img.height).data;
  const lin = (v) => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  let sum = 0, n = 0;
  for (let i = 0; i < d.length; i += 4) {
    if (d[i + 3] >= 16) {
      sum += 0.2126 * lin(d[i]) + 0.7152 * lin(d[i + 1]) + 0.0722 * lin(d[i + 2]);
      n++;
    }
  }
  return n ? sum / n : null;
}
"""


async def logo_mean_luminance(logo_ref: str) -> float | None:
    """Alpha-weighted mean relative luminance of a logo's opaque pixels.

    Data-URI refs only — sampling an external URL would mean a network fetch inside QA
    (house rule: no network here), so anything else returns None and the caller skips the
    check rather than guessing.
    """
    if not logo_ref.startswith("data:image/"):
        return None
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page()
            mean = await page.evaluate(_MEAN_OPAQUE_LUMINANCE_JS, logo_ref)
        finally:
            await browser.close()
    return None if mean is None else float(mean)


async def sampled_zone_luminance(
    html: str, zone: ZoneRect, viewport: tuple[int, int], hide_css: str = "h1,p,span"
) -> float:
    """Mean relative luminance of what actually renders under a zone's text.

    Renders the canvas with `hide_css` elements hidden (visibility only — layout is
    untouched; pass "h1,p,span,img" to sample the ground under a logo), screenshots the
    zone clip, then decodes the PNG in a second page (canvas getImageData) so no Python
    image library is needed.
    """
    from playwright.async_api import async_playwright

    width, height = viewport
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>*{margin:0;padding:0;box-sizing:border-box}"
        "html,body{margin:0;background:transparent}"
        f"{hide_css}{{visibility:hidden}}</style>"
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
