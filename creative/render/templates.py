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

from mimik_contracts import BrandLayout, LogoPlacement, get_format, validate_asset_ref

from creative.render.color import shade, tint


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
    # The brand's default layout (logo placement/size, safe-zone margins, ...). When present it
    # drives logo anchoring/size and raises the safe-zone floor; when None the templates keep
    # their built-in defaults, so pre-layout callers render exactly as before.
    layout: BrandLayout | None = None

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
    top, right, bottom, left = (
        max(base, sz.top),
        max(base, sz.right),
        max(base, sz.bottom),
        max(base, sz.left),
    )
    # A brand's safe-zone margins (% of the shortest edge) raise the floor — never below the
    # platform safe zone, but the brand can demand more breathing room.
    layout = ctx.layout
    if layout is not None:
        short = min(fmt.width, fmt.height)
        m = layout.margins
        top = max(top, round(m.top / 100 * short))
        right = max(right, round(m.right / 100 * short))
        bottom = max(bottom, round(m.bottom / 100 * short))
        left = max(left, round(m.left / 100 * short))
        # Header/footer brand bands reserve a strip at top/bottom — content must clear them.
        band = _band_height(fmt.width, fmt.height)
        if layout.header:
            top = max(top, band + _base_pad(fmt.width, fmt.height, frac))
        if layout.footer:
            bottom = max(bottom, band + _base_pad(fmt.width, fmt.height, frac))
    return top, right, bottom, left


# Header/footer band height as a fraction of the canvas height.
_BAND_FRAC = 0.07


def _band_height(width: int, height: int) -> int:
    return round(height * _BAND_FRAC)


def _bands_html(ctx: TemplateContext) -> str:
    """Solid brand-color strips at the very top/bottom when the brand's layout opts into a
    header/footer band. Absolutely positioned over the ground; content already clears them via
    the raised safe-zone floor (_edge_pads). Empty string when neither is enabled (no regression)."""
    layout = ctx.layout
    if layout is None or (not layout.header and not layout.footer):
        return ""
    w, h = ctx.size()
    band = _band_height(w, h)
    parts: list[str] = []
    if layout.header:
        parts.append(
            f'<div style="position:absolute;top:0;left:0;right:0;height:{band}px;'
            f'background:{ctx.primary}"></div>'
        )
    if layout.footer:
        parts.append(
            f'<div style="position:absolute;bottom:0;left:0;right:0;height:{band}px;'
            f'background:{ctx.primary}"></div>'
        )
    return "".join(parts)


# Conservative width assumed for a horizontal logo lockup (height × this factor); the actual
# <img> is width:auto, so QA checks the worst plausible footprint.
_LOGO_WIDTH_FACTOR = 3


def _resolve_logo(ctx: TemplateContext, top: int, left: int, height: int) -> tuple[int, int, int] | None:
    """Final (top, left, height) for the logo. With a BrandLayout, the logo is sized by
    `logo_scale` (fraction of the short edge) and anchored to `logo_placement` inside the brand's
    margins; without one it keeps the template's passed-in default (legacy behaviour)."""
    if not ctx.logo_ref:
        return None
    layout = ctx.layout
    if layout is None:
        return top, left, height

    w, h = ctx.size()
    short = min(w, h)
    lh = max(1, round(layout.logo_scale * short))
    lw = lh * _LOGO_WIDTH_FACTOR
    m = layout.margins
    m_top = round(m.top / 100 * short)
    m_right = round(m.right / 100 * short)
    m_bottom = round(m.bottom / 100 * short)
    m_left = round(m.left / 100 * short)
    place = layout.logo_placement

    if place in (LogoPlacement.TOP_LEFT, LogoPlacement.MIDDLE_LEFT, LogoPlacement.BOTTOM_LEFT):
        lx = m_left
    elif place in (LogoPlacement.TOP_RIGHT, LogoPlacement.MIDDLE_RIGHT, LogoPlacement.BOTTOM_RIGHT):
        lx = max(m_left, w - m_right - lw)
    else:
        lx = round((w - lw) / 2)

    if place in (LogoPlacement.TOP_LEFT, LogoPlacement.TOP_CENTER, LogoPlacement.TOP_RIGHT):
        ly = m_top
    elif place in (LogoPlacement.BOTTOM_LEFT, LogoPlacement.BOTTOM_CENTER, LogoPlacement.BOTTOM_RIGHT):
        ly = max(m_top, h - m_bottom - lh)
    else:
        ly = round((h - lh) / 2)

    return ly, lx, lh


def _logo(ctx: TemplateContext, top: int, left: int, height: int) -> str:
    resolved = _resolve_logo(ctx, top, left, height)
    if resolved is None:
        return ""
    ly, lx, lh = resolved
    return (
        f'<img src="{escape(ctx.logo_ref, quote=True)}" alt="" '
        f'style="position:absolute;top:{ly}px;left:{lx}px;height:{lh}px;width:auto" />'
    )


def _logo_zone(ctx: TemplateContext, top: int, left: int, height: int) -> ZoneRect | None:
    resolved = _resolve_logo(ctx, top, left, height)
    if resolved is None:
        return None
    ly, lx, lh = resolved
    return ZoneRect(x=lx, y=ly, w=lh * _LOGO_WIDTH_FACTOR, h=lh)


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
            f"{_bands_html(ctx)}"
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
            f"{_bands_html(ctx)}"
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


class SoftEditorial(LayoutTemplate):
    """Modeled on the client-approved base style of real published posts (the Glo2Go IG
    set): a soft brand-tint ground, layered bottom waves, a badge-pill logo top-right, a
    deep-brand headline over the light ground, a white-on-brand subhead pill, and a solid
    CTA pill — layer by layer, every color DERIVED from the brand primary (never a house
    default). Optional imagery sits in its own rounded window; text never overlaps it.
    """

    key = "soft_editorial"
    name = "Soft Editorial"
    description = (
        "Soft brand-tint ground with layered waves, badge logo, deep-brand headline, "
        "subhead pill and CTA — premium and human, not a flat color plate."
    )

    PAD_FRAC = 0.07

    # One palette derivation, used by render() AND the QA color semantics below —
    # what QA computes is exactly what renders.
    @staticmethod
    def palette(ctx: TemplateContext) -> dict[str, str]:
        return {
            "ground_top": tint(ctx.primary, 0.95),
            "ground_bottom": tint(ctx.primary, 0.86),
            "wave_back": tint(ctx.primary, 0.55),
            "wave_front": shade(ctx.primary, 0.12),
            "badge": shade(ctx.primary, 0.10),
            "headline": shade(ctx.primary, 0.28),
            "pill": shade(ctx.primary, 0.15),
        }

    def render(self, ctx: TemplateContext) -> str:
        w, h = ctx.size()
        pad_t, pad_r, pad_b, pad_l = _edge_pads(ctx, self.PAD_FRAC)
        pal = self.palette(ctx)
        h_size = round(w * 0.058)
        sub_size = round(w * 0.026)
        cta_size = round(w * 0.026)
        badge_h = round(h * 0.055)
        wave_h = round(h * 0.16)

        badge = ""
        if ctx.logo_ref:
            badge_pad = round(badge_h * 0.30)
            # The pill bleeds to the canvas edge (like the real posts' badge), but the
            # LOGO inside must clear the format's safe zone — so the pill's right padding
            # absorbs the inset.
            badge_pad_r = max(round(badge_pad * 1.6), get_format(ctx.format_key).safe_zone.right)
            badge = (
                f'<div style="position:absolute;top:{pad_t}px;right:0;'
                f"background:{pal['badge']};"
                f"padding:{badge_pad}px {badge_pad_r}px {badge_pad}px {round(badge_pad * 1.6)}px;"
                f'border-radius:{badge_h}px 0 0 {badge_h}px">'
                f'<img src="{escape(ctx.logo_ref, quote=True)}" alt="" '
                f'style="display:block;height:{badge_h}px;width:auto" /></div>'
            )

        image = ""
        if ctx.image_ref:
            img_h = round(h * 0.40)
            image = (
                f'<div style="margin:{round(h * 0.03)}px auto 0;width:76%;height:{img_h}px;'
                f"background:url('{escape(ctx.image_ref, quote=True)}') center/cover;"
                f'border-radius:{round(w * 0.03)}px"></div>'
            )

        sub = (
            f'<div style="margin:{round(sub_size * 1.2)}px auto 0;max-width:84%">'
            f'<span style="display:inline-block;background:{pal["pill"]};color:#FFFFFF;'
            f"font-family:{ctx.body_font};font-size:{sub_size}px;line-height:1.5;"
            f'padding:{round(sub_size * 0.7)}px {round(sub_size * 1.3)}px;'
            f'border-radius:{round(sub_size * 0.9)}px">{escape(ctx.subhead)}</span></div>'
            if ctx.subhead
            else ""
        )
        cta = (
            f'<div style="margin-top:{round(cta_size * 1.6)}px">'
            f"{_cta(ctx.cta, pal['pill'], '#FFFFFF', ctx.body_font, cta_size)}</div>"
            if ctx.cta
            else ""
        )

        # Two stacked waves along the bottom edge — the layered curve motif of the real posts.
        waves = (
            f'<svg style="position:absolute;left:0;right:0;bottom:0" width="{w}" '
            f'height="{wave_h}" viewBox="0 0 {w} {wave_h}" preserveAspectRatio="none">'
            f'<path d="M0 {round(wave_h * 0.45)} C {round(w * 0.3)} 0, {round(w * 0.6)} '
            f"{wave_h}, {w} {round(wave_h * 0.35)} L {w} {wave_h} L 0 {wave_h} Z\" "
            f'fill="{pal["wave_back"]}" opacity="0.55"/>'
            f'<path d="M0 {round(wave_h * 0.75)} C {round(w * 0.35)} {round(wave_h * 0.25)}, '
            f'{round(w * 0.7)} {wave_h}, {w} {round(wave_h * 0.6)} L {w} {wave_h} L 0 '
            f'{wave_h} Z" fill="{pal["wave_front"]}"/></svg>'
        )

        # With imagery the stack reads top-down like the real posts; without it, the column
        # centers in the space between badge and waves so the frame never feels top-loaded.
        content_top = round(pad_t + badge_h * 1.9)
        justify = "flex-start" if ctx.image_ref else "center"
        return (
            f'<div style="position:relative;width:{w}px;height:{h}px;overflow:hidden;'
            f"background:linear-gradient(170deg,{pal['ground_top']} 0%,"
            f"{pal['ground_bottom']} 100%)\">"
            f"{_bands_html(ctx)}"
            f"{badge}"
            f'<div style="position:absolute;left:{pad_l}px;right:{pad_r}px;'
            f"top:{content_top}px;bottom:{wave_h}px;text-align:center;"
            f'display:flex;flex-direction:column;justify-content:{justify}">'
            f"<div>"
            f'<h1 style="font-family:{ctx.heading_font};color:{pal["headline"]};'
            f"font-size:{h_size}px;font-weight:800;line-height:1.12;letter-spacing:-.015em;"
            f'margin:0;text-wrap:balance">{escape(ctx.headline)}</h1>'
            f"{sub}{image}{cta}"
            f"</div></div>"
            f"{waves}"
            f"</div>"
        )

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        w, h = ctx.size()
        pad_t, pad_r, pad_b, pad_l = _edge_pads(ctx, self.PAD_FRAC)
        h_size = round(w * 0.058)
        sub_size = round(w * 0.026)
        cta_size = round(w * 0.026)
        badge_h = round(h * 0.055)
        avail = w - pad_l - pad_r
        top = round(pad_t + badge_h * 1.9)

        head_lines = max(1, math.ceil(len(ctx.headline) * h_size * 0.6 / avail))
        text_h = round(h_size * 1.12 * head_lines)
        if ctx.subhead:
            sub_lines = max(1, math.ceil(len(ctx.subhead) * sub_size * 0.55 / (avail * 0.84)))
            text_h += round(sub_size * 1.2 + sub_size * 1.5 * sub_lines + sub_size * 1.4)
        if ctx.image_ref:
            text_h += round(h * 0.03 + h * 0.40)
        if ctx.cta:
            text_h += round(cta_size * 1.6 + cta_size * 2.2)
        # Mirror render(): the column spans badge→waves; without imagery it flex-centers in
        # that span, so the zone's y shifts down by half the slack. The estimate is NEVER
        # clamped to the span — over-estimating keeps the QA zone a superset of the real
        # DOM block, so copy that genuinely overflows the span breaches the bottom safe
        # zone and QA fails loud (routing to a human) instead of false-passing.
        wave_h = round(h * 0.16)
        span = h - wave_h - top
        y = top if ctx.image_ref else top + max(0, (span - text_h) // 2)
        text_zone = ZoneRect(x=pad_l, y=y, w=avail, h=text_h)

        logo_zone = None
        if ctx.logo_ref:
            badge_pad = round(badge_h * 0.30)
            # The decorative pill bleeds to the canvas edge by design; QA measures the
            # LOGO box, which the pill's right padding keeps inside the safe zone.
            badge_pad_r = max(round(badge_pad * 1.6), get_format(ctx.format_key).safe_zone.right)
            logo_zone = ZoneRect(
                x=w - badge_pad_r - badge_h * _LOGO_WIDTH_FACTOR,
                y=pad_t + badge_pad,
                w=badge_h * _LOGO_WIDTH_FACTOR,
                h=badge_h,
            )
        return TemplateGeometry(
            text_zones=[text_zone],
            logo_zone=logo_zone,
            text_over_imagery=False,  # imagery has its own window; text never overlaps it
        )


TEMPLATES: dict[str, LayoutTemplate] = {
    t.key: t for t in (CenteredHero(), LowerBand(), SoftEditorial())
}


def get_template(key: str) -> LayoutTemplate:
    """Look up a layout template. Raises KeyError for unknown keys (fail loud)."""
    return TEMPLATES[key]


def available_templates() -> list[dict[str, str]]:
    """Selectable templates for the picker UI: key + name + description."""
    return [{"key": t.key, "name": t.name, "description": t.description} for t in TEMPLATES.values()]
