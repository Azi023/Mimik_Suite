"""Profile-driven Glo2Go layout archetypes for real-photo education creatives.

The owner-exclusion rule belongs to upstream image sourcing. This renderer's guardrails are
visual: real photography stays dominant, plum and white stay load-bearing, information panels
exist only behind copy that needs photographic separation, and effects remain restrained.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Literal

from pydantic import field_validator

from mimik_contracts import get_format, validate_asset_ref

from creative.render.compositor import render_context_to_png
from creative.render.templates import (
    TEMPLATES,
    LayoutTemplate,
    TemplateContext,
    TemplateGeometry,
    ZoneRect,
)
from creative.style_profile import Effect, StyleProfile, get_style_profile

_GLO2GO_PROFILE_ID = "glo2go-aesthetics"
_PLUM_FALLBACK = "#5A2A6B"
_WHITE_FALLBACK = "#FFFFFF"
_IMAGE_MIME_BY_SUFFIX = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

# TODO(M3): Load the approved Glo2Go heading/body font families after onboarding supplies them.
_SYSTEM_FONT = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"


class Glo2GoTemplateContext(TemplateContext):
    """Glo2Go copy, image, and composition controls shared by both archetypes."""

    density: Literal["compact", "dense"] = "compact"
    text_region: Literal[
        "top",
        "bottom",
        "left",
        "right",
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
        "center",
    ] | None = None
    image_ref_2: str | None = None
    myth_label: str | None = None
    myth_text: str | None = None
    fact_label: str | None = None
    fact_text: str | None = None

    _second_ref_is_safe = field_validator("image_ref_2")(
        staticmethod(validate_asset_ref)
    )


@dataclass(frozen=True)
class _Frame:
    top: int
    right: int
    bottom: int
    left: int
    badge_width: int
    badge_height: int


@dataclass(frozen=True)
class _HeroComposition:
    panel_x: int
    panel_y: int
    panel_width: int
    panel_height: int
    panel_padding: int
    headline_size: int
    body_size: int


@dataclass(frozen=True)
class _SplitComposition:
    gap: int
    top_photo_height: int
    bottom_photo_y: int
    bottom_photo_height: int
    panel_width: int
    panel_padding: int
    headline_size: int
    body_size: int
    label_size: int
    myth_panel: ZoneRect
    fact_panel: ZoneRect


def _palette_color(profile: StyleProfile, role: str, fallback: str) -> str:
    for color in profile.palette:
        if color.role == role:
            # TODO(M3): Replace documented approximate fallbacks after brand hexes are confirmed.
            return fallback if color.hex is None or color.approx else color.hex
    return fallback


def _require_glo2go_profile(profile: StyleProfile) -> None:
    if profile.id != _GLO2GO_PROFILE_ID:
        raise ValueError(f"Expected style profile {_GLO2GO_PROFILE_ID!r}; got {profile.id!r}")
    required = {Effect.TEXT_PANEL_OVER_PHOTO, Effect.BADGE_PILL, Effect.SOFT_SHADOW}
    missing = required.difference(profile.effect_vocabulary)
    if missing:
        names = ", ".join(sorted(effect.value for effect in missing))
        raise ValueError(f"Glo2Go profile is missing required effects: {names}")


def _copy_value(
    copy: dict[str, str],
    *keys: str,
    required: bool = False,
) -> str | None:
    for key in keys:
        value = copy.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"Glo2Go copy field {key!r} must be a string")
            cleaned = value.strip()
            if cleaned:
                return cleaned
    if required:
        raise ValueError(f"Glo2Go copy requires {keys[0]!r}")
    return None


def _embed_local_image(image_ref: str) -> str:
    """Return a compositor-safe data URI from a data URI or a local image path.

    Network URLs are intentionally not accepted: the operator supplies a downloaded Pexels
    photo, and embedding it keeps the render deterministic and offline.
    """
    if image_ref.startswith("data:image/"):
        return image_ref

    path = Path(image_ref)
    if not path.is_file():
        raise FileNotFoundError(f"Glo2Go image path is not a local file: {image_ref}")
    mime = _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower())
    if mime is None:
        supported = ", ".join(sorted(_IMAGE_MIME_BY_SUFFIX))
        raise ValueError(f"Glo2Go image must use one of these extensions: {supported}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _density(archetype: str, copy: dict[str, str]) -> Literal["compact", "dense"]:
    score = sum(len(value.strip()) for value in copy.values() if isinstance(value, str))
    threshold = 150 if archetype == "single_photo_education_hero" else 205
    return "dense" if score > threshold else "compact"


def _frame(ctx: TemplateContext) -> _Frame:
    fmt = get_format(ctx.format_key)
    short = min(fmt.width, fmt.height)
    house = round(short * 0.06)
    badge_height = round(short * 0.055)
    badge_width = round(short * 0.24)
    return _Frame(
        top=max(house, fmt.safe_zone.top),
        right=max(house, fmt.safe_zone.right),
        bottom=max(house, fmt.safe_zone.bottom),
        left=max(house, fmt.safe_zone.left),
        badge_width=badge_width,
        badge_height=badge_height,
    )


def _rgba(color: str, alpha: float) -> str:
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return f"rgba({red},{green},{blue},{alpha:.2f})"


def _line_count(text: str | None, font_size: int, available_width: int, glyph: float) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) * font_size * glyph / max(1, available_width)))


def _hero_composition(ctx: Glo2GoTemplateContext) -> _HeroComposition:
    width, height = ctx.size()
    frame = _frame(ctx)
    dense = ctx.density == "dense"
    panel_width = round(width * (0.66 if dense else 0.54))
    panel_padding = round(width * (0.034 if dense else 0.040))
    headline_size = round(width * (0.052 if dense else 0.064))
    body_size = round(width * (0.023 if dense else 0.026))
    content_width = panel_width - 2 * panel_padding
    headline_lines = _line_count(ctx.headline, headline_size, content_width, 0.56)
    body_lines = _line_count(ctx.subhead, body_size, content_width, 0.52)
    panel_height = 2 * panel_padding + round(headline_lines * headline_size * 1.08)
    if body_lines:
        panel_height += round(body_size * 0.75 + body_lines * body_size * 1.45)
    if ctx.cta:
        panel_height += round(body_size * 2.55)
    panel_x, panel_y = _hero_panel_anchor(
        ctx,
        panel_width=panel_width,
        panel_height=panel_height,
        frame=frame,
    )
    return _HeroComposition(
        panel_x=panel_x,
        panel_y=panel_y,
        panel_width=panel_width,
        panel_height=panel_height,
        panel_padding=panel_padding,
        headline_size=headline_size,
        body_size=body_size,
    )


def _hero_panel_anchor(
    ctx: Glo2GoTemplateContext,
    *,
    panel_width: int,
    panel_height: int,
    frame: _Frame,
) -> tuple[int, int]:
    """Map a vision region to a safe pixel anchor while preserving the legacy default."""
    width, height = ctx.size()
    if ctx.text_region is None:
        return (
            frame.left,
            max(frame.top + frame.badge_height, height - frame.bottom - panel_height),
        )

    horizontal = {
        "top": "center",
        "bottom": "center",
        "left": "left",
        "right": "right",
        "top_left": "left",
        "top_right": "right",
        "bottom_left": "left",
        "bottom_right": "right",
        "center": "center",
    }[ctx.text_region]
    vertical = {
        "top": "top",
        "bottom": "bottom",
        "left": "center",
        "right": "center",
        "top_left": "top",
        "top_right": "top",
        "bottom_left": "bottom",
        "bottom_right": "bottom",
        "center": "center",
    }[ctx.text_region]

    x = {
        "left": frame.left,
        "center": round((width - panel_width) / 2),
        "right": width - frame.right - panel_width,
    }[horizontal]
    y = {
        "top": frame.top,
        "center": round((height - panel_height) / 2),
        "bottom": height - frame.bottom - panel_height,
    }[vertical]

    # A top/right panel must clear the fixed top-right logo badge rather than trade one
    # collision for another. Other top anchors stay aligned to the safe-zone edge.
    badge_left = width - frame.right - frame.badge_width
    if vertical == "top" and x + panel_width > badge_left:
        y = frame.top + frame.badge_height + round(frame.badge_height * 0.35)
    return (
        max(frame.left, min(x, width - frame.right - panel_width)),
        max(frame.top, min(y, height - frame.bottom - panel_height)),
    )


def _split_composition(ctx: Glo2GoTemplateContext) -> _SplitComposition:
    width, height = ctx.size()
    frame = _frame(ctx)
    dense = ctx.density == "dense"
    gap = max(10, round(min(width, height) * 0.012))
    available_height = height - gap
    myth_length = len(ctx.myth_text or "")
    fact_length = len(ctx.fact_text or "")
    total_length = max(1, myth_length + fact_length)
    balance = (myth_length - fact_length) / total_length
    top_ratio = 0.5 + max(-0.06, min(0.06, balance * 0.10))
    top_photo_height = round(available_height * top_ratio)
    bottom_photo_y = top_photo_height + gap
    bottom_photo_height = height - bottom_photo_y

    panel_width = round(width * (0.64 if dense else 0.54))
    panel_padding = round(width * (0.028 if dense else 0.032))
    headline_size = round(width * (0.040 if dense else 0.046))
    body_size = round(width * (0.021 if dense else 0.023))
    label_size = round(width * 0.021)
    content_width = panel_width - 2 * panel_padding

    headline_lines = _line_count(ctx.headline, headline_size, content_width, 0.56)
    myth_lines = _line_count(ctx.myth_text, body_size, content_width, 0.52)
    fact_lines = _line_count(ctx.fact_text, body_size, content_width, 0.52)
    label_height = round(label_size * 1.25)
    myth_height = (
        2 * panel_padding
        + round(headline_lines * headline_size * 1.08)
        + round(label_size * 0.80)
        + label_height
        + round(body_size * 0.65)
        + round(myth_lines * body_size * 1.42)
    )
    fact_height = (
        2 * panel_padding
        + label_height
        + round(body_size * 0.65)
        + round(fact_lines * body_size * 1.42)
    )
    if ctx.cta:
        fact_height += round(body_size * 2.55)

    myth_x = frame.left
    myth_y = max(frame.top, top_photo_height - frame.left - myth_height)
    fact_x = width - frame.right - panel_width
    fact_y = min(
        bottom_photo_y + frame.left,
        height - frame.bottom - fact_height,
    )
    return _SplitComposition(
        gap=gap,
        top_photo_height=top_photo_height,
        bottom_photo_y=bottom_photo_y,
        bottom_photo_height=bottom_photo_height,
        panel_width=panel_width,
        panel_padding=panel_padding,
        headline_size=headline_size,
        body_size=body_size,
        label_size=label_size,
        myth_panel=ZoneRect(x=myth_x, y=myth_y, w=panel_width, h=myth_height),
        fact_panel=ZoneRect(x=fact_x, y=fact_y, w=panel_width, h=fact_height),
    )


def _as_glo2go_context(ctx: TemplateContext) -> Glo2GoTemplateContext:
    if not isinstance(ctx, Glo2GoTemplateContext):
        raise TypeError("Glo2Go templates require Glo2GoTemplateContext")
    if ctx.image_ref is None:
        raise ValueError("Glo2Go templates require a real photo")
    return ctx


def _canvas_open(ctx: Glo2GoTemplateContext, archetype: str) -> str:
    width, height = ctx.size()
    return (
        f'<div class="g2g-canvas" data-archetype="{archetype}" '
        f'data-density="{ctx.density}" '
        f'data-effects="{Effect.TEXT_PANEL_OVER_PHOTO.value} {Effect.BADGE_PILL.value} '
        f'{Effect.SOFT_SHADOW.value}" aria-label="{escape(ctx.headline, quote=True)}" '
        f'style="--g2g-plum:{ctx.primary};--g2g-ink:{ctx.ink};'
        f'--g2g-ground:{ctx.on_primary};width:{width}px;height:{height}px">'
    )


def _common_css(ctx: Glo2GoTemplateContext) -> str:
    ground_panel = _rgba(ctx.on_primary, 0.94 if ctx.density == "compact" else 0.96)
    plum_border = _rgba(ctx.ink, 0.10)
    plum_shadow = _rgba(ctx.ink, 0.18)
    feather_shadow = _rgba(ctx.ink, 0.10)
    return (
        "<style>"
        ".g2g-canvas,.g2g-canvas *{box-sizing:border-box}"
        ".g2g-canvas{position:relative;overflow:hidden;background:var(--g2g-ground);"
        f"font-family:{_SYSTEM_FONT};color:var(--g2g-ink)}}"
        ".g2g-photo{position:absolute;display:block;width:100%;height:100%;object-fit:cover}"
        f".g2g-panel{{position:absolute;background:{ground_panel};"
        f"border:1px solid {plum_border};box-shadow:0 18px 44px {plum_shadow},"
        f"0 4px 14px {feather_shadow},inset 0 1px 0 rgba(255,255,255,.62);"
        "border-radius:26px;color:var(--g2g-ink)}"
        ".g2g-badge{position:absolute;z-index:4;display:flex;align-items:center;"
        "justify-content:center;border-radius:999px;background:var(--g2g-plum);"
        "color:var(--g2g-ground);font-weight:700;letter-spacing:-.01em;"
        "box-shadow:0 8px 22px rgba(38,12,46,.16);white-space:nowrap}"
        ".g2g-logo-badge{padding:8px 18px}.g2g-logo{display:block;max-width:100%;"
        "max-height:100%;object-fit:contain}"
        ".g2g-panel h1{margin:0;font-weight:760;line-height:1.08;letter-spacing:-.025em;"
        "text-wrap:balance}"
        ".g2g-panel p{margin:0;font-weight:430;line-height:1.45;text-wrap:pretty}"
        ".g2g-label{display:inline-flex;align-items:center;border-radius:999px;"
        "background:var(--g2g-plum);color:var(--g2g-ground);font-weight:720;line-height:1;"
        "letter-spacing:-.01em}"
        ".g2g-cta{display:inline-flex;align-items:center;width:max-content;max-width:100%;"
        "border-radius:999px;background:var(--g2g-plum);color:var(--g2g-ground);"
        "font-weight:750;line-height:1.1;letter-spacing:-.01em}"
        "</style>"
    )


def _badge(ctx: Glo2GoTemplateContext) -> str:
    frame = _frame(ctx)
    font_size = round(frame.badge_height * 0.34)
    if ctx.logo_ref:
        return (
            f'<div class="g2g-badge g2g-logo-badge" '
            f'style="top:{frame.top}px;right:{frame.right}px;'
            f'width:{frame.badge_width}px;height:{frame.badge_height}px">'
            f'<img class="g2g-logo" src="{escape(ctx.logo_ref, quote=True)}" alt=""></div>'
        )
    return (
        f'<div class="g2g-badge" style="top:{frame.top}px;right:{frame.right}px;'
        f'width:{frame.badge_width}px;height:{frame.badge_height}px;font-size:{font_size}px">'
        "G2G Aesthetics</div>"
    )


def _cta_html(cta: str | None, body_size: int) -> str:
    if not cta:
        return ""
    padding_y = round(body_size * 0.55)
    padding_x = round(body_size * 0.92)
    return (
        f'<span class="g2g-cta" style="margin-top:{round(body_size * 0.82)}px;'
        f'padding:{padding_y}px {padding_x}px;font-size:{round(body_size * 0.9)}px">'
        f"{escape(cta)}</span>"
    )


class SinglePhotoEducationHero(LayoutTemplate):
    """Full-bleed photo with one copy-sized legibility panel, never a permanent band."""

    key = "single_photo_education_hero"
    name = "Single Photo Education Hero"
    description = "Full-bleed education photo with a restrained, copy-aware white panel."

    def render(self, ctx: TemplateContext) -> str:
        glo = _as_glo2go_context(ctx)
        comp = _hero_composition(glo)
        photo_position = "64% center" if glo.density == "dense" else "center center"
        subhead = (
            f'<p style="margin-top:{round(comp.body_size * 0.72)}px;'
            f'font-size:{comp.body_size}px">{escape(glo.subhead)}</p>'
            if glo.subhead
            else ""
        )
        cta = _cta_html(glo.cta, comp.body_size)
        region = glo.text_region or "default"
        return (
            f"{_canvas_open(glo, self.key)}{_common_css(glo)}"
            f'<img class="g2g-photo" src="{escape(glo.image_ref, quote=True)}" alt="" '
            f'style="object-position:{photo_position}">'
            f"{_badge(glo)}"
            f'<section class="g2g-panel g2g-hero-panel" data-text-region="{region}" '
            f'style="left:{comp.panel_x}px;top:{comp.panel_y}px;width:{comp.panel_width}px;'
            f'min-height:{comp.panel_height}px;padding:{comp.panel_padding}px">'
            f'<h1 style="font-size:{comp.headline_size}px">{escape(glo.headline)}</h1>'
            f"{subhead}{cta}</section></div>"
        )

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        glo = _as_glo2go_context(ctx)
        comp = _hero_composition(glo)
        frame = _frame(glo)
        width, _height = glo.size()
        return TemplateGeometry(
            text_zones=[
                ZoneRect(
                    x=comp.panel_x,
                    y=comp.panel_y,
                    w=comp.panel_width,
                    h=comp.panel_height,
                )
            ],
            logo_zone=ZoneRect(
                x=width - frame.right - frame.badge_width,
                y=frame.top,
                w=frame.badge_width,
                h=frame.badge_height,
            ),
            text_over_imagery=True,
        )


class MythVsFactSplit(LayoutTemplate):
    """Two stacked photo crops with deliberately offset Myth and Fact information panels."""

    key = "myth_vs_fact_split"
    name = "Myth vs Fact Split"
    description = "Two stacked photo crops with independently balanced Myth and Fact panels."

    def render(self, ctx: TemplateContext) -> str:
        glo = _as_glo2go_context(ctx)
        if not all((glo.myth_label, glo.myth_text, glo.fact_label, glo.fact_text)):
            raise ValueError("Myth vs Fact requires both labels and both explanations")
        comp = _split_composition(glo)
        label_padding_y = round(comp.label_size * 0.55)
        label_padding_x = round(comp.label_size * 0.92)
        return (
            f"{_canvas_open(glo, self.key)}{_common_css(glo)}"
            f'<div style="position:absolute;inset:0;background:var(--g2g-ground)">'
            f'<div style="position:absolute;left:0;top:0;width:100%;'
            f'height:{comp.top_photo_height}px;overflow:hidden">'
            f'<img class="g2g-photo" src="{escape(glo.image_ref, quote=True)}" alt="" '
            f'style="object-position:center 28%"></div>'
            f'<div style="position:absolute;left:0;top:{comp.bottom_photo_y}px;width:100%;'
            f'height:{comp.bottom_photo_height}px;overflow:hidden">'
            f'<img class="g2g-photo" src="{escape(glo.image_ref_2 or glo.image_ref, quote=True)}" alt="" '
            f'style="object-position:center 72%"></div></div>'
            f"{_badge(glo)}"
            f'<section class="g2g-panel g2g-split-panel g2g-myth-panel" '
            f'style="left:{comp.myth_panel.x}px;top:{comp.myth_panel.y}px;'
            f'width:{comp.myth_panel.w}px;min-height:{comp.myth_panel.h}px;'
            f'padding:{comp.panel_padding}px">'
            f'<h1 style="font-size:{comp.headline_size}px">{escape(glo.headline)}</h1>'
            f'<span class="g2g-label" style="margin-top:{round(comp.label_size * 0.8)}px;'
            f'padding:{label_padding_y}px {label_padding_x}px;font-size:{comp.label_size}px">'
            f"{escape(glo.myth_label)}</span>"
            f'<p style="margin-top:{round(comp.body_size * 0.65)}px;'
            f'font-size:{comp.body_size}px">{escape(glo.myth_text)}</p></section>'
            f'<section class="g2g-panel g2g-split-panel g2g-fact-panel" '
            f'style="left:{comp.fact_panel.x}px;top:{comp.fact_panel.y}px;'
            f'width:{comp.fact_panel.w}px;min-height:{comp.fact_panel.h}px;'
            f'padding:{comp.panel_padding}px">'
            f'<span class="g2g-label" style="padding:{label_padding_y}px {label_padding_x}px;'
            f'font-size:{comp.label_size}px">{escape(glo.fact_label)}</span>'
            f'<p style="margin-top:{round(comp.body_size * 0.65)}px;'
            f'font-size:{comp.body_size}px">{escape(glo.fact_text)}</p>'
            f'{_cta_html(glo.cta, comp.body_size)}</section></div>'
        )

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        glo = _as_glo2go_context(ctx)
        comp = _split_composition(glo)
        frame = _frame(glo)
        width, _height = glo.size()
        return TemplateGeometry(
            text_zones=[comp.myth_panel, comp.fact_panel],
            logo_zone=ZoneRect(
                x=width - frame.right - frame.badge_width,
                y=frame.top,
                w=frame.badge_width,
                h=frame.badge_height,
            ),
            text_over_imagery=True,
        )


GLO2GO_TEMPLATES: dict[str, LayoutTemplate] = {
    template.key: template for template in (SinglePhotoEducationHero(), MythVsFactSplit())
}

# Extend the established registry rather than creating a second compositor or lookup system.
TEMPLATES.update(GLO2GO_TEMPLATES)


def _build_context(
    archetype: str,
    *,
    image_ref: str,
    copy: dict[str, str],
    format_key: str,
    profile: StyleProfile,
    image_ref_2: str | None = None,
    logo_ref: str | None = None,
    text_region: str | None = None,
) -> Glo2GoTemplateContext:
    if archetype not in GLO2GO_TEMPLATES:
        choices = ", ".join(GLO2GO_TEMPLATES)
        raise ValueError(f"Unknown Glo2Go archetype {archetype!r}; choose from: {choices}")
    _require_glo2go_profile(profile)
    get_format(format_key)  # Fail loud through the established format registry.

    primary = _palette_color(profile, "primary", _PLUM_FALLBACK)
    ink = _palette_color(profile, "ink", _PLUM_FALLBACK)
    ground = _palette_color(profile, "ground", _WHITE_FALLBACK)
    embedded_image = _embed_local_image(image_ref)
    embedded_image_2 = _embed_local_image(image_ref_2) if image_ref_2 else None
    embedded_logo = _embed_local_image(logo_ref) if logo_ref else None

    if archetype == "single_photo_education_hero":
        headline = _copy_value(copy, "headline", required=True)
        assert headline is not None
        return Glo2GoTemplateContext(
            format_key=format_key,
            headline=headline,
            subhead=_copy_value(copy, "sub", "subhead"),
            cta=_copy_value(copy, "cta"),
            primary=primary,
            accent=primary,
            on_primary=ground,
            ink=ink,
            heading_font=_SYSTEM_FONT,
            body_font=_SYSTEM_FONT,
            logo_ref=embedded_logo,
            image_ref=embedded_image,
            density=_density(archetype, copy),
            text_region=text_region,
        )

    myth_label = _copy_value(copy, "myth_label", required=True)
    myth_text = _copy_value(copy, "myth", "myth_text", required=True)
    fact_label = _copy_value(copy, "fact_label", required=True)
    fact_text = _copy_value(copy, "fact", "fact_text", required=True)
    assert myth_label is not None
    assert fact_label is not None
    headline = _copy_value(copy, "headline") or f"{myth_label} vs {fact_label}"
    return Glo2GoTemplateContext(
        format_key=format_key,
        headline=headline,
        primary=primary,
        accent=primary,
        on_primary=ground,
        ink=ink,
        heading_font=_SYSTEM_FONT,
        body_font=_SYSTEM_FONT,
        logo_ref=embedded_logo,
        image_ref=embedded_image,
        image_ref_2=embedded_image_2,
        density=_density(archetype, copy),
        text_region=text_region,
        cta=_copy_value(copy, "cta"),
        myth_label=myth_label,
        myth_text=myth_text,
        fact_label=fact_label,
        fact_text=fact_text,
    )


def build_glo2go_html(
    archetype: str,
    *,
    image_ref: str,
    copy: dict[str, str],
    format_key: str,
    profile: StyleProfile,
    image_ref_2: str | None = None,
    logo_ref: str | None = None,
    text_region: str | None = None,
) -> str:
    """Build editable HTML for structural tests and future layer-level editing.

    Hero copy keys: ``headline``, optional ``sub``/``subhead``, optional ``cta``.
    Split required copy keys: ``myth_label``, ``myth``, ``fact_label``, ``fact``. Its optional
    ``headline`` defaults to "Myth vs Fact" from the supplied labels; ``cta`` is also optional.
    """
    ctx = _build_context(
        archetype,
        image_ref=image_ref,
        copy=copy,
        format_key=format_key,
        profile=profile,
        image_ref_2=image_ref_2,
        logo_ref=logo_ref,
        text_region=text_region,
    )
    return GLO2GO_TEMPLATES[archetype].render(ctx)


async def render_glo2go(
    archetype: str,
    *,
    image_ref: str,
    copy: dict[str, str],
    format_key: str,
    image_ref_2: str | None = None,
    logo_ref: str | None = None,
    text_region: str | None = None,
) -> bytes:
    """Render a Glo2Go archetype through the existing Playwright compositor."""
    profile = get_style_profile(_GLO2GO_PROFILE_ID)
    ctx = _build_context(
        archetype,
        image_ref=image_ref,
        copy=copy,
        format_key=format_key,
        profile=profile,
        image_ref_2=image_ref_2,
        logo_ref=logo_ref,
        text_region=text_region,
    )
    return await render_context_to_png(ctx, archetype)
