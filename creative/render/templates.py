"""Layout-template library — clean, sleek, uncluttered composited creatives.

Each template renders a self-contained HTML canvas at the EXACT format dimensions, ready for
the Playwright compositor to screenshot to PNG (L3 scaffold + L4 message + L5 finish). The
library encodes the house taste ("don't overcomplicate": one focal message, real whitespace,
limited text). Text placement is deterministic per template; a scrim is applied ONLY when
requested (the QA contrast check drives it) so output stays clean.

Layout is chosen FIRST (this library), then imagery is generated to keep the text zones quiet.
"""

from __future__ import annotations

import abc
import math
from html import escape

from pydantic import BaseModel, Field, field_validator

from mimik_contracts import get_format, validate_asset_ref


class TemplateContext(BaseModel):
    """Everything a template needs to render one creative. Colors default to the Mimik
    brand tokens; a real render passes the client's brand tokens instead."""

    format_key: str
    headline: str
    subhead: str | None = None
    cta: str | None = None
    primary: str = Field(default="#2E5BFF", pattern=r"^#[0-9a-fA-F]{6}$")
    accent: str = Field(default="#C6F135", pattern=r"^#[0-9a-fA-F]{6}$")
    on_primary: str = Field(default="#FFFFFF", pattern=r"^#[0-9a-fA-F]{6}$")
    ink: str = Field(default="#0B0D12", pattern=r"^#[0-9a-fA-F]{6}$")
    heading_font: str = "system-ui, -apple-system, sans-serif"
    body_font: str = "system-ui, -apple-system, sans-serif"
    logo_ref: str | None = None   # asset reference / data-URI for the approved logo
    image_ref: str | None = None  # the L1/L2 imagery artifact / data-URI
    scrim: bool = False

    # Both refs are interpolated into CSS url('...') / HTML src="..." below; html.escape
    # cannot protect the CSS string context, so the render sink re-validates their shape
    # no matter which path constructed the context (contracts validate at rest too).
    _refs_are_safe = field_validator("logo_ref", "image_ref")(staticmethod(validate_asset_ref))

    def size(self) -> tuple[int, int]:
        fmt = get_format(self.format_key)
        return fmt.width, fmt.height


class ZoneRect(BaseModel):
    """Axis-aligned pixel rectangle in canvas coordinates (top-left origin)."""

    x: int
    y: int
    w: int
    h: int


class TemplateGeometry(BaseModel):
    """Where a template puts important content — lets QA reason about text/logo placement
    (safe zones, contrast sampling) without pixel-parsing the render. text_zones[0] is the
    headline block; text_over_imagery means the headline sits on the L1/L2 image."""

    text_zones: list[ZoneRect]
    logo_zone: ZoneRect | None
    text_over_imagery: bool


def _base_pad(w: int, h: int, frac: float) -> int:
    return round(min(w, h) * frac)


def _edge_pads(ctx: TemplateContext, frac: float) -> tuple[int, int, int, int]:
    """Per-edge padding: the %-of-min-side house pad, clamped UP to the format's safe-zone
    inset so important content never lands in a platform-obscured strip (ig_story's 250px
    top/bottom bars are the motivating case). Returns (top, right, bottom, left)."""
    fmt = get_format(ctx.format_key)
    base = _base_pad(fmt.width, fmt.height, frac)
    sz = fmt.safe_zone
    return max(base, sz.top), max(base, sz.right), max(base, sz.bottom), max(base, sz.left)


# Conservative width assumed for a horizontal logo lockup (height × this factor); the actual
# <img> is width:auto, so QA checks the worst plausible footprint.
_LOGO_WIDTH_FACTOR = 3


def _logo(ctx: TemplateContext, top: int, left: int, height: int) -> str:
    if not ctx.logo_ref:
        return ""
    return (
        f'<img src="{escape(ctx.logo_ref, quote=True)}" alt="" '
        f'style="position:absolute;top:{top}px;left:{left}px;height:{height}px;width:auto" />'
    )


def _logo_zone(ctx: TemplateContext, top: int, left: int, height: int) -> ZoneRect | None:
    if not ctx.logo_ref:
        return None
    return ZoneRect(x=left, y=top, w=height * _LOGO_WIDTH_FACTOR, h=height)


def _cta(label: str, bg: str, fg: str, font: str, size: int) -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'font-family:{font};font-weight:700;font-size:{size}px;'
        f'padding:{size * 0.6:.0f}px {size * 1.1:.0f}px;border-radius:{size}px;'
        f'letter-spacing:.01em">{escape(label)}</span>'
    )


class LayoutTemplate(abc.ABC):
    key: str
    name: str
    description: str

    @abc.abstractmethod
    def render(self, ctx: TemplateContext) -> str:
        """Return a self-contained HTML canvas at the format's exact pixel size."""
        raise NotImplementedError

    @abc.abstractmethod
    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        """Content placement for QA — must use the same pad math as render()."""
        raise NotImplementedError


class CenteredHero(LayoutTemplate):
    key = "centered_hero"
    name = "Centered Hero"
    description = "Full-bleed imagery with one bold headline + CTA anchored low. Scrim on demand."

    PAD_FRAC = 0.07

    def render(self, ctx: TemplateContext) -> str:
        w, h = ctx.size()
        pad_t, pad_r, pad_b, pad_l = _edge_pads(ctx, self.PAD_FRAC)
        h_size = round(w * 0.072)
        sub_size = round(w * 0.03)
        cta_size = round(w * 0.028)
        # With imagery, text is white over a scrim; without, use the brand primary as ground.
        ground = f"background:url('{escape(ctx.image_ref, quote=True)}') center/cover" if ctx.image_ref else f"background:{ctx.primary}"
        scrim = (
            '<div style="position:absolute;inset:0;'
            'background:linear-gradient(180deg,rgba(0,0,0,0) 35%,rgba(0,0,0,.62) 100%)"></div>'
            if ctx.scrim
            else ""
        )
        sub = (
            f'<p style="font-family:{ctx.body_font};color:#fff;font-size:{sub_size}px;'
            f'margin:{sub_size * 0.6:.0f}px 0 0;max-width:80%;line-height:1.35;opacity:.92">'
            f"{escape(ctx.subhead)}</p>"
            if ctx.subhead
            else ""
        )
        cta = (
            f'<div style="margin-top:{cta_size * 1.4:.0f}px">'
            f"{_cta(ctx.cta, ctx.accent, ctx.ink, ctx.body_font, cta_size)}</div>"
            if ctx.cta
            else ""
        )
        return (
            f'<div style="position:relative;width:{w}px;height:{h}px;overflow:hidden;{ground}">'
            f"{scrim}"
            f"{_logo(ctx, pad_t, pad_l, round(h * 0.06))}"
            f'<div style="position:absolute;left:{pad_l}px;right:{pad_r}px;bottom:{pad_b}px">'
            f'<h1 style="font-family:{ctx.heading_font};color:#fff;font-size:{h_size}px;'
            f'font-weight:800;line-height:1.03;letter-spacing:-.02em;margin:0;'
            f'text-wrap:balance">{escape(ctx.headline)}</h1>'
            f"{sub}{cta}"
            f"</div></div>"
        )

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        w, h = ctx.size()
        pad_t, pad_r, pad_b, pad_l = _edge_pads(ctx, self.PAD_FRAC)
        h_size = round(w * 0.072)
        sub_size = round(w * 0.03)
        cta_size = round(w * 0.028)
        avail = w - pad_l - pad_r
        # Copy-aware text-block height (margins/paddings mirror the render() math above).
        # Line counts come from a conservative ~0.6×font-size average glyph width for the
        # 800-weight headline (0.55 for the body face) — over-estimating keeps the QA zone
        # a superset of the real DOM block, which the browser containment test asserts.
        head_lines = max(1, math.ceil(len(ctx.headline) * h_size * 0.6 / avail))
        text_h = round(h_size * 1.1 * head_lines)
        if ctx.subhead:
            sub_lines = max(1, math.ceil(len(ctx.subhead) * sub_size * 0.55 / (avail * 0.8)))
            text_h += round(sub_size * 0.6 + sub_size * 1.35 * sub_lines)
        if ctx.cta:
            text_h += round(cta_size * 1.4 + cta_size * 2.2)  # margin-top + chip (font + 2×.6 pad)
        text_zone = ZoneRect(x=pad_l, y=h - pad_b - text_h, w=w - pad_l - pad_r, h=text_h)
        return TemplateGeometry(
            text_zones=[text_zone],
            logo_zone=_logo_zone(ctx, pad_t, pad_l, round(h * 0.06)),
            text_over_imagery=ctx.image_ref is not None,
        )


class LowerBand(LayoutTemplate):
    key = "lower_band"
    name = "Lower Band"
    description = "Imagery on top, text in a solid brand band below — text never overlaps imagery, so it is always legible."

    PAD_FRAC = 0.06

    def render(self, ctx: TemplateContext) -> str:
        w, h = ctx.size()
        band_h = round(h * 0.36)
        pad_t, pad_r, pad_b, pad_l = _edge_pads(ctx, self.PAD_FRAC)
        # The band's top edge is mid-canvas, so its internal top padding needs no safe-zone
        # clamp — only the three canvas-edge sides do.
        band_pad_top = _base_pad(w, h, self.PAD_FRAC)
        h_size = round(w * 0.055)
        cta_size = round(w * 0.026)
        top = (
            f"background:url('{escape(ctx.image_ref, quote=True)}') center/cover"
            if ctx.image_ref
            else f"background:{ctx.ink}"
        )
        cta = (
            f'<div style="margin-top:{cta_size:.0f}px">'
            f"{_cta(ctx.cta, ctx.accent, ctx.ink, ctx.body_font, cta_size)}</div>"
            if ctx.cta
            else ""
        )
        return (
            f'<div style="position:relative;width:{w}px;height:{h}px;overflow:hidden;background:{ctx.primary}">'
            f'<div style="position:absolute;top:0;left:0;right:0;height:{h - band_h}px;{top}"></div>'
            f'<div style="position:absolute;left:0;right:0;bottom:0;height:{band_h}px;'
            f'background:{ctx.primary};padding:{band_pad_top}px {pad_r}px {pad_b}px {pad_l}px;'
            f"box-sizing:border-box;"
            f'display:flex;flex-direction:column;justify-content:center">'
            f'<h1 style="font-family:{ctx.heading_font};color:{ctx.on_primary};font-size:{h_size}px;'
            f'font-weight:800;line-height:1.05;letter-spacing:-.02em;margin:0;text-wrap:balance">'
            f"{escape(ctx.headline)}</h1>{cta}"
            f"</div>"
            f"{_logo(ctx, pad_t, pad_l, round(h * 0.05))}"
            f"</div>"
        )

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        w, h = ctx.size()
        band_h = round(h * 0.36)
        pad_t, pad_r, pad_b, pad_l = _edge_pads(ctx, self.PAD_FRAC)
        band_pad_top = _base_pad(w, h, self.PAD_FRAC)
        # Text zone = the band's content box (band minus its padding) — text never overlaps
        # imagery in this template. The logo renders top-left of the CANVAS (over the image
        # region), per render() above.
        text_zone = ZoneRect(
            x=pad_l,
            y=(h - band_h) + band_pad_top,
            w=w - pad_l - pad_r,
            h=band_h - band_pad_top - pad_b,
        )
        return TemplateGeometry(
            text_zones=[text_zone],
            logo_zone=_logo_zone(ctx, pad_t, pad_l, round(h * 0.05)),
            text_over_imagery=False,
        )


TEMPLATES: dict[str, LayoutTemplate] = {t.key: t for t in (CenteredHero(), LowerBand())}


def get_template(key: str) -> LayoutTemplate:
    """Look up a layout template. Raises KeyError for unknown keys (fail loud)."""
    return TEMPLATES[key]


def available_templates() -> list[dict[str, str]]:
    """Selectable templates for the picker UI: key + name + description."""
    return [{"key": t.key, "name": t.name, "description": t.description} for t in TEMPLATES.values()]
