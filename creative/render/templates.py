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
from html import escape

from pydantic import BaseModel, Field

from mimik_contracts import get_format


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

    def size(self) -> tuple[int, int]:
        fmt = get_format(self.format_key)
        return fmt.width, fmt.height


def _logo(ctx: TemplateContext, pad: int, height: int) -> str:
    if not ctx.logo_ref:
        return ""
    return (
        f'<img src="{escape(ctx.logo_ref, quote=True)}" alt="" '
        f'style="position:absolute;top:{pad}px;left:{pad}px;height:{height}px;width:auto" />'
    )


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


class CenteredHero(LayoutTemplate):
    key = "centered_hero"
    name = "Centered Hero"
    description = "Full-bleed imagery with one bold headline + CTA anchored low. Scrim on demand."

    def render(self, ctx: TemplateContext) -> str:
        w, h = ctx.size()
        pad = round(min(w, h) * 0.07)
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
            f"{_logo(ctx, pad, round(h * 0.06))}"
            f'<div style="position:absolute;left:{pad}px;right:{pad}px;bottom:{pad}px">'
            f'<h1 style="font-family:{ctx.heading_font};color:#fff;font-size:{h_size}px;'
            f'font-weight:800;line-height:1.03;letter-spacing:-.02em;margin:0;'
            f'text-wrap:balance">{escape(ctx.headline)}</h1>'
            f"{sub}{cta}"
            f"</div></div>"
        )


class LowerBand(LayoutTemplate):
    key = "lower_band"
    name = "Lower Band"
    description = "Imagery on top, text in a solid brand band below — text never overlaps imagery, so it is always legible."

    def render(self, ctx: TemplateContext) -> str:
        w, h = ctx.size()
        band_h = round(h * 0.36)
        pad = round(min(w, h) * 0.06)
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
            f'background:{ctx.primary};padding:{pad}px;box-sizing:border-box;'
            f'display:flex;flex-direction:column;justify-content:center">'
            f'<h1 style="font-family:{ctx.heading_font};color:{ctx.on_primary};font-size:{h_size}px;'
            f'font-weight:800;line-height:1.05;letter-spacing:-.02em;margin:0;text-wrap:balance">'
            f"{escape(ctx.headline)}</h1>{cta}"
            f"</div>"
            f"{_logo(ctx, pad, round(h * 0.05))}"
            f"</div>"
        )


TEMPLATES: dict[str, LayoutTemplate] = {t.key: t for t in (CenteredHero(), LowerBand())}


def get_template(key: str) -> LayoutTemplate:
    """Look up a layout template. Raises KeyError for unknown keys (fail loud)."""
    return TEMPLATES[key]


def available_templates() -> list[dict[str, str]]:
    """Selectable templates for the picker UI: key + name + description."""
    return [{"key": t.key, "name": t.name, "description": t.description} for t in TEMPLATES.values()]
