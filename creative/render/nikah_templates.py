"""Simply Nikah render family — faceless flat-vector heroes composed from engine primitives.

Mirrors ``glo2go_templates`` in shape (a ``NikahTemplateContext``, archetype classes, an HTML
builder for structural tests, an async ``render_nikah`` returning PNG bytes) but composes ONLY
engine SVG vectors — Simply Nikah never takes a photograph. The standalone SVG emitter matches
``creative/export/svg.py``'s named-layer contract so the canvas editor and PSD export consume SN
SVGs with zero changes.

Single geometry source: each archetype computes one frozen ``_NikahComposition``; the SVG emitter,
the HTML render, and ``geometry()`` all consume it, so exported-SVG / compositor-PNG parity is by
construction.

Design contract: docs/STYLE_PROFILES.md Profile 1. Build spec: docs/NIKAH_ENGINE_SPEC.md.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from pydantic import field_validator

from mimik_contracts import get_format

from creative.export.svg import rasterize_svg_to_png  # reuse the established rasterizer
from creative.knowledge.feedback import load_rules
from creative.render import nikah_primitives as prim
from creative.render.builtin_fonts import builtin_arabic_font_path, contains_arabic
from creative.render.fonts import embed_font_face, font_family_stack
from creative.render.nikah_vectors import get_vector
from creative.render.templates import (
    LayoutTemplate,
    TemplateContext,
    TemplateGeometry,
    ZoneRect,
)
from creative.style_profile import Effect, StyleProfile, get_style_profile

_NIKAH_PROFILE_ID = "simply-nikah"
_SYSTEM_FONT = prim._SYSTEM_FONT
# Internal @font-face family names for optional brand fonts — same tokens svg.py/glo2go use, so a
# brand font renders identically across every code-composited path (never client text; see fonts.py).
_HEADING_FONT_FAMILY = "MimikBrandHeading"
_BODY_FONT_FAMILY = "MimikBrandBody"
_SCRIPT_FONT_FAMILY = "MimikScriptArabic"

# Palette fallbacks (shared with the primitive module — all profile hexes are approx=True).
_PINK_FALLBACK = prim._PINK_FALLBACK
_BLUSH_FALLBACK = prim._BLUSH_FALLBACK
_PLUM_FALLBACK = prim._PLUM_FALLBACK
_LILAC_FALLBACK = prim._LILAC_FALLBACK
_CLOUD_FALLBACK = prim._CLOUD_FALLBACK

_SVG_NS = "http://www.w3.org/2000/svg"
_INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
ElementTree.register_namespace("", _SVG_NS)
ElementTree.register_namespace("inkscape", _INKSCAPE_NS)

_IMAGE_MIME_BY_SUFFIX = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}

HeroSymbol = Literal["hands_heart", "shield_crescent", "heart_shield", "heart", "crescent"]

# Layer ids in paint order (bottom→top) — the SN named-layer contract.
_LAYER_IDS: tuple[str, ...] = (
    "layer-background",
    "layer-motif",
    "layer-glow",
    "layer-hero",
    "layer-wordmark",
    "layer-headline",
    "layer-highlight-word",
    "layer-support",
    "layer-cta",
)
_EDITABLE_LAYER_IDS = frozenset(_LAYER_IDS)
_OVERRIDE_KEYS = frozenset({"dx", "dy", "scale", "rotation", "visible", "fill"})

# Copy keys that would smuggle a photo into a profile that must never take one.
_BANNED_PHOTO_KEYS = ("image_ref", "image", "photo", "photo_path", "image_path")


class NikahTemplateContext(TemplateContext):
    """Simply Nikah copy + composition controls shared by its launch archetypes.

    ``image_ref`` stays None — SN composes pure engine vectors (GENERATED_VECTOR). A non-None
    ``image_ref`` MUST raise, guarding the never-real-photos rule.
    """

    highlight_word: str | None = None
    hero_symbol: HeroSymbol = "hands_heart"
    lattice_backdrop: bool = True
    ground_gradient: bool = True  # archetype A default; B passes False
    secondary: str = _LILAC_FALLBACK  # muted-lilac role (TemplateContext lacks it)
    design_rule_ids: tuple[str, ...] = ()

    @field_validator("image_ref")
    @classmethod
    def _no_photographs(cls, value: str | None) -> None:
        if value is not None:
            raise ValueError(
                "Simply Nikah composes pure engine vectors; a photo/image_ref is never permitted."
            )
        return value


# =============================================================================================
# Palette + profile discipline (reuse of the glo2go patterns)
# =============================================================================================


def _palette_color(profile: StyleProfile, role: str, fallback: str) -> str:
    for color in profile.palette:
        if color.role == role:
            # TODO(M3): replace documented approximate fallbacks after brand hexes are confirmed.
            return fallback if color.hex is None or color.approx else color.hex
    return fallback


def _palette(profile: StyleProfile) -> dict[str, str]:
    return {
        "pink": _palette_color(profile, "primary", _PINK_FALLBACK),
        "blush": _palette_color(profile, "accent", _BLUSH_FALLBACK),
        "plum": _palette_color(profile, "ink", _PLUM_FALLBACK),
        "lilac": _palette_color(profile, "secondary", _LILAC_FALLBACK),
        "cloud": _palette_color(profile, "ground", _CLOUD_FALLBACK),
    }


def _require_nikah_profile(profile: StyleProfile) -> None:
    if profile.id != _NIKAH_PROFILE_ID:
        raise ValueError(f"Expected style profile {_NIKAH_PROFILE_ID!r}; got {profile.id!r}")
    required = {Effect.GRADIENT_FADE, Effect.BLUR, Effect.COLOR_BLOCK, Effect.BADGE_PILL}
    missing = required.difference(profile.effect_vocabulary)
    if missing:
        names = ", ".join(sorted(effect.value for effect in missing))
        raise ValueError(f"Simply Nikah profile is missing required effects: {names}")


def _copy_value(copy: dict[str, str], *keys: str, required: bool = False) -> str | None:
    for key in keys:
        value = copy.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise TypeError(f"Simply Nikah copy field {key!r} must be a string")
            cleaned = value.strip()
            if cleaned:
                return cleaned
    if required:
        raise ValueError(f"Simply Nikah copy requires {keys[0]!r}")
    return None


def _reject_photo_copy(copy: dict[str, str]) -> None:
    for key in _BANNED_PHOTO_KEYS:
        if copy.get(key):
            raise ValueError(
                f"Simply Nikah never takes a photo; copy key {key!r} is not permitted."
            )


def _embed_local_image(image_ref: str) -> str:
    """Return a compositor-safe data URI from a data URI or a local image path (offline)."""
    if image_ref.startswith("data:image/"):
        return image_ref
    path = Path(image_ref)
    if not path.is_file():
        raise FileNotFoundError(f"Simply Nikah logo path is not a local file: {image_ref}")
    mime = _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower())
    if mime is None:
        supported = ", ".join(sorted(_IMAGE_MIME_BY_SUFFIX))
        raise ValueError(f"Simply Nikah logo must use one of these extensions: {supported}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


# =============================================================================================
# Text wrapping (conservative, deterministic)
# =============================================================================================


def _wrap(text: str, max_chars: int, max_lines: int) -> tuple[str, ...]:
    if not text:
        return ()
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if len(trial) <= max_chars or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        head = lines[: max_lines - 1]
        tail = " ".join(lines[max_lines - 1 :])
        lines = head + [tail]
    return tuple(lines)


# =============================================================================================
# Composition — one frozen dataclass per render, shared by SVG / HTML / geometry
# =============================================================================================


@dataclass(frozen=True)
class _TextLine:
    text: str
    x: int
    baseline: int
    font: int
    weight: int
    fill: str
    opacity: float
    anchor: str


@dataclass(frozen=True)
class _NikahComposition:
    archetype: str
    w: int
    h: int
    grid_step: int
    rule_ids: str
    palette: dict[str, str]
    font_family: str
    ground_gradient: bool
    lattice_on: bool
    # wordmark
    wm_cx: int
    wm_baseline: int
    wm_h: int
    logo_ref: str | None
    wm_bbox: tuple[int, int, int, int]
    # headline text (non-highlighted words)
    headline_lines: tuple[_TextLine, ...]
    headline_bbox: tuple[int, int, int, int]
    # highlight word box (top-left + word + font), or None
    highlight_word: str | None
    highlight_x: int
    highlight_y: int
    highlight_font: int
    highlight_bbox: tuple[int, int, int, int]
    # support
    support_lines: tuple[_TextLine, ...]
    support_bbox: tuple[int, int, int, int]
    # hero
    hero_symbol: str
    hero_cx: int
    hero_cy: int
    hero_box: int
    glow_rx: int
    glow_ry: int
    glow_opacity: float
    hero_bbox: tuple[int, int, int, int]
    glow_bbox: tuple[int, int, int, int]
    # cta
    cta_label: str | None
    cta_cx: int
    cta_top: int
    cta_h: int
    cta_bbox: tuple[int, int, int, int]
    # backdrop bboxes
    bg_bbox: tuple[int, int, int, int]
    motif_bbox: tuple[int, int, int, int]


# Per-archetype composition parameters. Kept as data so both archetypes share one code path.
_ARCHETYPE_PARAMS = {
    "highlighted_word_hero": {
        "headline_font_frac": 0.085,
        "headline_weight": 760,
        "headline_max_lines": 3,
        "support_font_frac": 0.0315,
        "support_margin_frac": 0.0278,
        "support_opacity": 0.85,
        "hero_frac": 0.42,
        "hero_center_frac": 0.60,
        "glow_opacity": 0.5,
        "ground_gradient_default": True,
        "highlight_required": True,
    },
    "protection_symbol_hero": {
        "headline_font_frac": 0.070,
        "headline_weight": 720,
        "headline_max_lines": 2,
        "support_font_frac": 0.02963,
        "support_margin_frac": 0.0241,
        "support_opacity": 0.85,
        "hero_frac": 0.52,
        "hero_center_frac": 0.62,
        "glow_opacity": 0.45,
        "ground_gradient_default": False,
        "highlight_required": False,
    },
    "ayah_translation": {
        "headline_font_frac": 0.060,
        "headline_weight": 500,
        "headline_max_lines": 3,
        "support_font_frac": 0.02963,
        "support_margin_frac": 0.035,
        "support_opacity": 0.88,
        "hero_frac": 0.80,
        "hero_center_frac": 0.38,
        "glow_opacity": 0.38,
        "ground_gradient_default": True,
        "highlight_required": False,
    },
}


def _compose(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    hero_symbol: HeroSymbol,
    logo_ref: str | None,
    lattice_backdrop: bool,
    ground_gradient: bool | None = None,
) -> _NikahComposition:
    if archetype not in _ARCHETYPE_PARAMS:
        choices = ", ".join(sorted(_ARCHETYPE_PARAMS))
        raise ValueError(f"Unknown Simply Nikah archetype {archetype!r}; choose from: {choices}")
    _reject_photo_copy(copy)
    params = _ARCHETYPE_PARAMS[archetype]
    profile = get_style_profile(_NIKAH_PROFILE_ID)
    _require_nikah_profile(profile)
    palette = _palette(profile)
    fmt = get_format(format_key)  # fail loud through the established format registry
    w, h = fmt.width, fmt.height
    # Left/right insets are unused: SN centres its single content column (generous whitespace),
    # so only the top/bottom safe zone drives vertical placement.
    st, sb = fmt.safe_zone.top, fmt.safe_zone.bottom

    grid_step = max(8, round(min(w, h) / 24))
    rule_ids = " ".join(rule.id for rule in load_rules(_NIKAH_PROFILE_ID))
    if ground_gradient is None:
        ground_gradient = bool(params["ground_gradient_default"])
    is_ayah = archetype == "ayah_translation"

    # --- copy ---------------------------------------------------------------------------------
    headline = _copy_value(copy, "ayah", "headline", required=True) if is_ayah else _copy_value(
        copy,
        "headline",
        required=True,
    )
    assert headline is not None
    highlight = _copy_value(copy, "highlight", "highlight_word")
    if params["highlight_required"] and highlight is None:
        raise ValueError(f"{archetype!r} requires a 'highlight' copy key")
    support = (
        _copy_value(copy, "translation", "sub", "subhead", required=True)
        if is_ayah
        else _copy_value(copy, "sub", "subhead")
    )
    if is_ayah and not contains_arabic(headline):
        raise ValueError("'ayah_translation' requires Arabic-script 'ayah' copy")
    if is_ayah and not _contains_latin(support):
        raise ValueError("'ayah_translation' requires Latin-script 'translation' copy")
    cta_label = _copy_value(copy, "cta")

    # --- wordmark -----------------------------------------------------------------------------
    wm_cx = round(w / 2)
    wm_baseline = round(st + 0.040 * h)
    wm_h = max(40, round(0.033 * h))
    wm_w = round(w * 0.5)
    wm_bbox = (round(w / 2 - wm_w / 2), wm_baseline - wm_h, wm_w, round(wm_h * 1.4))

    # --- headline column ----------------------------------------------------------------------
    head_font = round(params["headline_font_frac"] * w)
    head_weight = int(params["headline_weight"])
    head_lh = round(head_font * 1.08)
    if is_ayah:
        panel_x = round(w * 0.10)
        panel_y = round(st + 0.14 * h)
        panel_w = round(w * 0.80)
        panel_h = round(min(0.30 * h, 0.52 * w))
        panel_padding = round(w * 0.065)
        head_width = panel_w - 2 * panel_padding
        head_x0 = panel_x + panel_padding
        head_cx = panel_x + panel_w - panel_padding
        head_top = panel_y + round(panel_h * 0.15)
    else:
        head_width = round(w * 0.778)
        head_x0 = round((w - head_width) / 2)
        head_cx = round(w / 2)
        head_top = round(st + 0.115 * h)
    max_chars = max(1, int(head_width / (head_font * prim._HEAVY_GLYPH_FACTOR)))

    # Split the headline around the (case-insensitive) highlight occurrence. v1 stacks the boxed
    # word on its own centred line (before-words above, after-words below) rather than true inline
    # flow — the box still owns layer-highlight-word; surrounding words own layer-headline.
    before_text = headline
    after_text = ""
    highlight_word: str | None = None
    if highlight is not None:
        idx = headline.lower().find(highlight.lower())
        if idx < 0:
            raise ValueError(
                f"'highlight' {highlight!r} must be a case-insensitive substring of the headline"
            )
        before_text = headline[:idx].strip()
        highlight_word = headline[idx : idx + len(highlight)].strip()
        after_text = headline[idx + len(highlight) :].strip()

    y = head_top
    headline_lines: list[_TextLine] = []

    def _emit_block(text: str) -> None:
        nonlocal y
        for line in _wrap(text, max_chars, params["headline_max_lines"]):
            baseline = y + head_font
            headline_lines.append(
                _TextLine(
                    line,
                    head_cx,
                    baseline,
                    head_font,
                    head_weight,
                    palette["plum"],
                    1.0,
                    "end" if is_ayah else "middle",
                )
            )
            y += head_lh

    _emit_block(before_text)

    highlight_x = head_x0
    highlight_y = y
    highlight_font = head_font
    highlight_bbox = (head_x0, y, head_width, 1)
    if highlight_word:
        box_w = len(highlight_word) * prim._HEAVY_GLYPH_FACTOR * head_font + 2 * 0.45 * head_font
        box_h = head_font + 2 * 0.22 * head_font
        highlight_x = round(head_cx - box_w / 2)
        highlight_y = round(y)
        highlight_bbox = (highlight_x, highlight_y, round(box_w), round(box_h))
        y += round(box_h) + round(head_font * 0.14)

    _emit_block(after_text)

    headline_block_bottom = y
    if headline_lines:
        top_of_block = headline_lines[0].baseline - head_font
    else:
        top_of_block = head_top
    headline_bbox = (head_x0, top_of_block, head_width, max(1, headline_block_bottom - top_of_block))

    # --- support ------------------------------------------------------------------------------
    support_font = round(params["support_font_frac"] * w)
    support_lh = round(support_font * 1.45)
    support_margin = round(params["support_margin_frac"] * w)
    support_top = (
        panel_y + panel_h + round(0.045 * h)
        if is_ayah
        else headline_block_bottom + support_margin
    )
    support_lines: list[_TextLine] = []
    if support:
        sup_chars = max(1, int(head_width / (support_font * 0.52)))
        sy = support_top
        support_x = round(w / 2) if is_ayah else head_cx
        for line in _wrap(support, sup_chars, 2):
            baseline = sy + support_font
            support_lines.append(
                _TextLine(
                    line,
                    support_x,
                    baseline,
                    support_font,
                    430,
                    palette["plum"],
                    float(params["support_opacity"]),
                    "middle",
                )
            )
            sy += support_lh
        support_block_bottom = sy
    else:
        support_block_bottom = support_top
    support_bbox = (head_x0, support_top, head_width, max(1, support_block_bottom - support_top))

    # --- cta ----------------------------------------------------------------------------------
    cta_h = round(0.062 * h)
    # Pill bottom flush against the bottom safe zone (the table's placement; see the build note in
    # the report — the spec's extra "-0.030·H" term contradicts its own coordinate table).
    cta_top = h - sb - cta_h
    if cta_label:
        cta_font = cta_h * 0.40
        pill_w = max(cta_h * 2.2, len(cta_label) * prim._HEAVY_GLYPH_FACTOR * cta_font + 2 * cta_h * 0.72)
        cta_bbox = (round(w / 2 - pill_w / 2), cta_top, round(pill_w), cta_h)
    else:
        cta_bbox = (round(w / 2), cta_top, 0, 0)

    # --- hero + glow --------------------------------------------------------------------------
    if is_ayah:
        hero_cx = round(w / 2)
        hero_cy = panel_y + round(panel_h / 2)
        hero_box = panel_w
        glow_rx = round(panel_w * 0.52)
        glow_ry = round(panel_h * 0.62)
        hero_bbox = (panel_x, panel_y, panel_w, panel_h)
        glow_bbox = (
            hero_cx - glow_rx,
            hero_cy - glow_ry,
            2 * glow_rx,
            2 * glow_ry,
        )
    else:
        hero_cx = round(w / 2)
        hero_cy = round(st + params["hero_center_frac"] * (h - st - sb))
        hero_frac_box = params["hero_frac"] * w
        free_gap = cta_top - support_block_bottom
        hero_box = (
            round(min(hero_frac_box, 0.85 * free_gap))
            if free_gap > 0
            else round(hero_frac_box)
        )
        hero_box = max(hero_box, round(hero_frac_box * 0.5))
        half = hero_box / 2
        glow_rx = round(1.35 * half)
        glow_ry = round(1.20 * half)
        hero_bbox = (
            round(hero_cx - half),
            round(hero_cy - half),
            hero_box,
            hero_box,
        )
        glow_bbox = (
            hero_cx - glow_rx,
            hero_cy - glow_ry,
            2 * glow_rx,
            2 * glow_ry,
        )

    return _NikahComposition(
        archetype=archetype,
        w=w,
        h=h,
        grid_step=grid_step,
        rule_ids=rule_ids,
        palette=palette,
        font_family=_SYSTEM_FONT,
        ground_gradient=ground_gradient,
        lattice_on=lattice_backdrop,
        wm_cx=wm_cx,
        wm_baseline=wm_baseline,
        wm_h=wm_h,
        logo_ref=_embed_local_image(logo_ref) if logo_ref else None,
        wm_bbox=wm_bbox,
        headline_lines=tuple(headline_lines),
        headline_bbox=headline_bbox,
        highlight_word=highlight_word,
        highlight_x=highlight_x,
        highlight_y=highlight_y,
        highlight_font=highlight_font,
        highlight_bbox=highlight_bbox,
        support_lines=tuple(support_lines),
        support_bbox=support_bbox,
        hero_symbol=hero_symbol,
        hero_cx=hero_cx,
        hero_cy=hero_cy,
        hero_box=hero_box,
        glow_rx=glow_rx,
        glow_ry=glow_ry,
        glow_opacity=float(params["glow_opacity"]),
        hero_bbox=hero_bbox,
        glow_bbox=glow_bbox,
        cta_label=cta_label,
        cta_cx=round(w / 2),
        cta_top=cta_top,
        cta_h=cta_h,
        cta_bbox=cta_bbox,
        bg_bbox=(0, 0, w, h),
        motif_bbox=(0, 0, w, h),
    )


# =============================================================================================
# SVG emission — matches svg.py::_layer attribute set exactly
# =============================================================================================


def _svg_tag(local_name: str) -> str:
    return f"{{{_SVG_NS}}}{local_name}"


def _layer(
    root: ElementTree.Element,
    layer_id: str,
    bbox: tuple[int, int, int, int],
) -> ElementTree.Element:
    """Named editable layer — identical attribute set to svg.py::_layer."""
    return ElementTree.SubElement(
        root,
        _svg_tag("g"),
        {
            "id": layer_id,
            "data-layer": layer_id,
            f"{{{_INKSCAPE_NS}}}label": layer_id,
            f"{{{_INKSCAPE_NS}}}groupmode": "layer",
            "data-editable": "true",
            "data-bbox": " ".join(str(value) for value in bbox),
        },
    )


def _embed_fragment(layer: ElementTree.Element, fragment: str) -> None:
    """Parse a primitive's SVG-fragment string (in the SVG namespace) and append its elements."""
    wrapper = ElementTree.fromstring(f'<svg xmlns="{_SVG_NS}">{fragment}</svg>')
    for child in list(wrapper):
        layer.append(child)


def _render_hero_fragment(comp: _NikahComposition) -> str:
    """Dispatch the hero symbol to the primitive vocabulary; returns a single-rooted <g>."""
    p = comp.palette
    if comp.archetype == "ayah_translation":
        x, y, width, height = comp.hero_bbox
        inset = max(10, round(width * 0.018))
        return (
            '<g data-role="ayah-panel">'
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="34" '
            f'fill="{p["blush"]}" fill-opacity="0.56" stroke="{p["lilac"]}" '
            'stroke-width="3"/>'
            f'<rect x="{x + inset}" y="{y + inset}" '
            f'width="{width - 2 * inset}" height="{height - 2 * inset}" rx="26" '
            'fill="none" '
            f'stroke="{p["plum"]}" stroke-opacity="0.12" stroke-width="2"/>'
            "</g>"
        )
    cx, cy, box = comp.hero_cx, comp.hero_cy, comp.hero_box
    half = box / 2
    symbol = comp.hero_symbol
    inner: list[str] = []
    bundled_vector = {
        "hands_heart": "dua_hands",
        "crescent": "crescent",
    }.get(symbol)
    if bundled_vector is not None:
        inner.append(
            get_vector(
                bundled_vector,
                x=cx - half,
                y=cy - half,
                scale=box / 100,
                fill=p["pink"],
            )
        )
    elif symbol == "heart":
        inner.append(prim.heart(cx, cy, box, fill=p["pink"]))
    elif symbol == "shield_crescent":
        inner.append(
            prim.shield_crescent(
                cx,
                cy,
                box,
                fill=p["pink"],
                shield_fill=p["blush"],
                stroke=p["plum"],
            )
        )
    elif symbol == "heart_shield":
        inner.append(
            prim.shield(
                cx, cy, box * 0.72, box,
                fill=p["blush"], stroke=p["plum"], stroke_width=max(2.0, box * 0.012),
            )
        )
        inner.append(prim.heart(cx, cy - box * 0.04, box * 0.44, fill=p["pink"]))
    else:  # defensive — Literal keeps this unreachable in typed callers
        raise ValueError(f"Unknown hero_symbol {symbol!r}")
    return f'<g data-role="hero">{"".join(inner)}</g>'


def _ground_gradient_fragment(comp: _NikahComposition) -> str:
    p = comp.palette
    return (
        "<defs>"
        '<linearGradient id="nk-ground" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="55%" stop-color="{p["cloud"]}" stop-opacity="0"/>'
        f'<stop offset="100%" stop-color="{p["blush"]}" stop-opacity="0.12"/>'
        "</linearGradient>"
        "</defs>"
        f'<rect x="0" y="0" width="{comp.w}" height="{comp.h}" fill="url(#nk-ground)"/>'
    )


def _contains_latin(text: str | None) -> bool:
    return bool(text) and any(
        "\u0041" <= character <= "\u024f" for character in text
    )


def build_nikah_svg(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    hero_symbol: HeroSymbol = "hands_heart",
    logo_ref: str | None = None,
    lattice_backdrop: bool = True,
    layer_overrides: Mapping[str, object] | None = None,
    heading_font_ref: str | None = None,
    body_font_ref: str | None = None,
    direction: str = "ltr",
    script_font_ref: str | None = None,
) -> str:
    """Standalone layered SVG matching svg.py's named-layer contract.

    ``layer_overrides`` accepts the same dx/dy/scale/rotation/visible/fill mapping svg.py honors,
    keyed by SN layer ids, so the canvas editor round-trips without a second code path.

    ``heading_font_ref`` / ``body_font_ref`` are OPTIONAL brand-font files (a stored
    ``AssetKind.FONT`` ``local_path`` or a ``data:font/...`` URI). SN renders through the same
    Playwright compositor as svg.py/glo2go, so it adopts fonts identically (fonts.py ADOPTERS
    note): each font is embedded as an ``@font-face`` in the SVG ``<style>`` and applied to the
    headline + highlight word (heading font) and the support line + CTA (body font). When None,
    the render is unchanged — system font, byte-identical to before.

    ``direction="rtl"`` right-aligns Arabic-bearing text and embeds ``script_font_ref``. The
    Ayah + Translation archetype always renders its ayah RTL with bundled Amiri by default while
    keeping the translation and CTA LTR.
    """
    if direction not in {"ltr", "rtl"}:
        raise ValueError("Simply Nikah text direction must be 'ltr' or 'rtl'")

    comp = _compose(
        archetype,
        copy=copy,
        format_key=format_key,
        hero_symbol=hero_symbol,
        logo_ref=logo_ref,
        lattice_backdrop=lattice_backdrop,
    )

    # Resolve optional brand fonts up front (fail loud before building the tree). Distinct
    # @font-face families let heading and body use different files simultaneously; None => the
    # system font stack, so the un-branded render is byte-identical to today.
    heading_font = embed_font_face(heading_font_ref, family=_HEADING_FONT_FAMILY) if heading_font_ref else None
    body_font = embed_font_face(body_font_ref, family=_BODY_FONT_FAMILY) if body_font_ref else None
    needs_script_font = direction == "rtl" or archetype == "ayah_translation"
    script_font = (
        embed_font_face(
            script_font_ref or str(builtin_arabic_font_path()),
            family=_SCRIPT_FONT_FAMILY,
        )
        if needs_script_font
        else None
    )
    heading_family = (
        font_family_stack(heading_font.family, _SYSTEM_FONT) if heading_font else _SYSTEM_FONT
    )
    body_family = font_family_stack(body_font.family, _SYSTEM_FONT) if body_font else _SYSTEM_FONT
    script_family = (
        font_family_stack(script_font.family, _SYSTEM_FONT) if script_font else _SYSTEM_FONT
    )

    p = comp.palette
    root = ElementTree.Element(
        _svg_tag("svg"),
        {
            "version": "1.1",
            "width": str(comp.w),
            "height": str(comp.h),
            "viewBox": f"0 0 {comp.w} {comp.h}",
            "data-grid-step": str(comp.grid_step),
            "data-design-rule-ids": comp.rule_ids,
        },
    )

    # Optional brand-font faces go in a document <style> so Playwright loads them before paint.
    # Only emitted when a font is supplied — the no-font path adds nothing (byte-identical).
    face_blocks = [
        font.face_css
        for font in (heading_font, body_font, script_font)
        if font is not None
    ]
    if face_blocks:
        style = ElementTree.SubElement(root, _svg_tag("style"), {"type": "text/css"})
        style.text = "".join(face_blocks)

    layers: dict[str, ElementTree.Element] = {}
    bboxes: dict[str, tuple[int, int, int, int]] = {}

    # layer-background: cloud ground + optional gradient fade toward the bottom
    bg = _layer(root, "layer-background", comp.bg_bbox)
    ElementTree.SubElement(
        bg, _svg_tag("rect"),
        {"x": "0", "y": "0", "width": str(comp.w), "height": str(comp.h), "fill": p["cloud"]},
    )
    if comp.ground_gradient:
        _embed_fragment(bg, _ground_gradient_fragment(comp))
    layers["layer-background"], bboxes["layer-background"] = bg, comp.bg_bbox

    # layer-motif: whisper lattice backdrop (emitted even when off, like glo2go's empty subhead)
    motif = _layer(root, "layer-motif", comp.motif_bbox)
    if comp.lattice_on:
        _embed_fragment(
            motif,
            f"<defs>{prim.lattice_pattern('nk-lattice', tile=120, stroke=p['lilac'], stroke_width=3.0, opacity=0.08)}</defs>"
            f'<rect x="0" y="0" width="{comp.w}" height="{comp.h}" fill="url(#nk-lattice)"/>',
        )
    layers["layer-motif"], bboxes["layer-motif"] = motif, comp.motif_bbox

    # layer-glow: blush radial glow behind the hero
    glow = _layer(root, "layer-glow", comp.glow_bbox)
    _embed_fragment(
        glow,
        prim.glow_ellipse(
            comp.hero_cx, comp.hero_cy, comp.glow_rx, comp.glow_ry,
            fill=p["blush"], opacity=comp.glow_opacity,
        ),
    )
    layers["layer-glow"], bboxes["layer-glow"] = glow, comp.glow_bbox

    # layer-hero: the vector hero symbol (figure groups inside carry data-figure/data-faceless)
    hero = _layer(root, "layer-hero", comp.hero_bbox)
    _embed_fragment(hero, _render_hero_fragment(comp))
    layers["layer-hero"], bboxes["layer-hero"] = hero, comp.hero_bbox

    # layer-wordmark: top-center wordmark (the ONLY modesty-approved raster slot)
    wordmark = _layer(root, "layer-wordmark", comp.wm_bbox)
    _embed_fragment(
        wordmark,
        prim.wordmark(
            comp.wm_cx, comp.wm_baseline, height=comp.wm_h,
            fill=p["plum"], font_family=comp.font_family, logo_ref=comp.logo_ref,
        ),
    )
    layers["layer-wordmark"], bboxes["layer-wordmark"] = wordmark, comp.wm_bbox

    # layer-headline: the non-highlighted headline words (heading font)
    headline = _layer(root, "layer-headline", comp.headline_bbox)
    if archetype == "ayah_translation":
        headline.set("data-role", "ayah-text")
        headline.set("data-text", " ".join(line.text for line in comp.headline_lines))
    for line in comp.headline_lines:
        headline_direction = (
            "rtl" if archetype == "ayah_translation" else direction
        )
        headline_family = (
            script_family if contains_arabic(line.text) else heading_family
        )
        _add_text_line_with_font(
            headline,
            line,
            headline_family,
            direction=headline_direction,
            right_edge=comp.headline_bbox[0] + comp.headline_bbox[2],
        )
    layers["layer-headline"], bboxes["layer-headline"] = headline, comp.headline_bbox

    # layer-highlight-word: the plum box + reversed text (heading font; empty for a plain headline)
    highlight = _layer(root, "layer-highlight-word", comp.highlight_bbox)
    if comp.highlight_word:
        highlight_family = (
            script_family if contains_arabic(comp.highlight_word) else heading_family
        )
        box_svg, _bw, _bh = prim.highlighted_word_box(
            comp.highlight_word,
            x=comp.highlight_x, y=comp.highlight_y, font_size=comp.highlight_font,
            box_fill=p["plum"], text_fill=p["cloud"], font_family=highlight_family,
        )
        _embed_fragment(highlight, box_svg)
        if direction == "rtl" and archetype != "ayah_translation":
            for text in highlight.iter(_svg_tag("text")):
                text.set("direction", "rtl")
                text.set("text-anchor", "end")
                text.set(
                    "x",
                    f"{comp.highlight_x + _bw - 0.45 * comp.highlight_font:g}",
                )
    layers["layer-highlight-word"], bboxes["layer-highlight-word"] = highlight, comp.highlight_bbox

    # layer-support: the support line (body font)
    support = _layer(root, "layer-support", comp.support_bbox)
    if archetype == "ayah_translation":
        support.set("data-role", "translation")
        support.set("data-text", " ".join(line.text for line in comp.support_lines))
    for line in comp.support_lines:
        support_direction = "ltr" if archetype == "ayah_translation" else direction
        support_family = script_family if contains_arabic(line.text) else body_family
        _add_text_line_with_font(
            support,
            line,
            support_family,
            direction=support_direction,
            right_edge=comp.support_bbox[0] + comp.support_bbox[2],
            emit_ltr=archetype == "ayah_translation",
        )
    layers["layer-support"], bboxes["layer-support"] = support, comp.support_bbox

    # layer-cta: rounded pill CTA (Deep Plum fill, Cloud White text — body font)
    cta = _layer(root, "layer-cta", comp.cta_bbox)
    if comp.cta_label:
        cta_family = (
            script_family if contains_arabic(comp.cta_label) else body_family
        )
        pill_svg, _pw = prim.cta_pill(
            comp.cta_cx, comp.cta_top, height=comp.cta_h, label=comp.cta_label,
            fill=p["plum"], text_fill=p["cloud"], font_family=cta_family,
        )
        _embed_fragment(cta, pill_svg)
        if direction == "rtl" and archetype != "ayah_translation":
            cta_right = comp.cta_cx + _pw / 2 - comp.cta_h * 0.72
            for text in cta.iter(_svg_tag("text")):
                text.set("direction", "rtl")
                text.set("text-anchor", "end")
                text.set("x", f"{cta_right:g}")
    layers["layer-cta"], bboxes["layer-cta"] = cta, comp.cta_bbox

    _apply_layer_overrides(layers, bboxes, layer_overrides)

    return ElementTree.tostring(root, encoding="unicode", xml_declaration=True)


def _add_text_line_with_font(
    layer: ElementTree.Element,
    line: _TextLine,
    font_family: str,
    *,
    direction: str = "ltr",
    right_edge: int | None = None,
    emit_ltr: bool = False,
) -> None:
    anchor = "end" if direction == "rtl" else line.anchor
    x = right_edge if direction == "rtl" and right_edge is not None else line.x
    attrs = {
        "x": str(x),
        "y": str(line.baseline),
        "fill": line.fill,
        "font-family": font_family,
        "font-size": str(line.font),
        "font-weight": str(line.weight),
        "text-anchor": anchor,
        f"{{{_XML_NS}}}space": "preserve",
    }
    if direction == "rtl" or emit_ltr:
        attrs["direction"] = direction
    if line.opacity < 1.0:
        attrs["fill-opacity"] = f"{line.opacity:.2f}"
    text = ElementTree.SubElement(layer, _svg_tag("text"), attrs)
    text.text = line.text


# =============================================================================================
# Layer overrides (canvas-editor round-trip) — SN layer-id set, svg.py semantics
# =============================================================================================


def _apply_layer_overrides(
    layers: Mapping[str, ElementTree.Element],
    bboxes: Mapping[str, tuple[int, int, int, int]],
    layer_overrides: Mapping[str, object] | None,
) -> None:
    if layer_overrides is None:
        return
    unknown_layers = set(layer_overrides) - _EDITABLE_LAYER_IDS
    if unknown_layers:
        raise ValueError(f"Unknown editable layer override: {', '.join(sorted(unknown_layers))}")

    for layer_id, override_value in layer_overrides.items():
        if not isinstance(override_value, Mapping):
            raise TypeError(f"Override for {layer_id!r} must be a mapping")
        unknown_keys = set(override_value) - _OVERRIDE_KEYS
        if unknown_keys:
            unknown = ", ".join(sorted(str(key) for key in unknown_keys))
            raise ValueError(f"Unknown override field for {layer_id!r}: {unknown}")

        layer = layers[layer_id]
        x, y, width, height = bboxes[layer_id]
        cx, cy = x + width / 2, y + height / 2

        dx = _int_override(override_value, "dx")
        dy = _int_override(override_value, "dy")
        scale = _scale_override(override_value)
        rotation = _rotation_override(override_value)

        parts: list[str] = []
        if dx or dy:
            parts.append(f"translate({dx},{dy})")
        if rotation != 0.0:
            parts.append(f"rotate({rotation:g},{cx:g},{cy:g})")
        if scale != 1.0:
            parts.extend(
                (f"translate({cx:g},{cy:g})", f"scale({scale:g})", f"translate({-cx:g},{-cy:g})")
            )
        if parts:
            existing = layer.attrib.get("transform")
            if existing:
                parts.append(existing)
            layer.set("transform", " ".join(parts))

        if not _visible_override(override_value):
            layer.set("display", "none")
            layer.set("data-hidden", "true")

        fill = _fill_override(override_value)
        if fill is not None:
            for element in layer.iter():
                if "fill" in element.attrib and element.attrib["fill"] != "none":
                    element.set("fill", fill)


def _int_override(override: Mapping[object, object], key: str) -> int:
    value = override[key] if key in override else 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Layer override {key!r} must be an int")
    return value


def _scale_override(override: Mapping[object, object]) -> float:
    value = override["scale"] if "scale" in override else 1.0
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("Layer override 'scale' must be a float")
    scale = float(value)
    if not isfinite(scale) or scale <= 0:
        raise ValueError("Layer override 'scale' must be a positive finite number")
    return min(scale, 3.0)


def _rotation_override(override: Mapping[object, object]) -> float:
    value = override["rotation"] if "rotation" in override else 0.0
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("Layer override 'rotation' must be a float")
    rotation = float(value)
    if not isfinite(rotation):
        raise ValueError("Layer override 'rotation' must be finite")
    return min(max(rotation, -180.0), 180.0)


def _visible_override(override: Mapping[object, object]) -> bool:
    value = override["visible"] if "visible" in override else True
    if not isinstance(value, bool):
        raise TypeError("Layer override 'visible' must be a bool")
    return value


def _fill_override(override: Mapping[object, object]) -> str | None:
    value = override["fill"] if "fill" in override else None
    if value is not None and not isinstance(value, str):
        raise TypeError("Layer override 'fill' must be a string or None")
    return value


# =============================================================================================
# Archetype classes (LayoutTemplate shape) — NOT registered into TEMPLATES in this build.
# =============================================================================================


def _ctx_copy(ctx: NikahTemplateContext) -> dict[str, str]:
    copy: dict[str, str] = {"headline": ctx.headline}
    if ctx.highlight_word:
        copy["highlight"] = ctx.highlight_word
    if ctx.subhead:
        copy["subhead"] = ctx.subhead
    if ctx.cta:
        copy["cta"] = ctx.cta
    return copy


def _as_nikah_context(ctx: TemplateContext) -> NikahTemplateContext:
    if not isinstance(ctx, NikahTemplateContext):
        raise TypeError("Simply Nikah templates require NikahTemplateContext")
    return ctx


class HighlightedWordHero(LayoutTemplate):
    """Headline with one plum-boxed key word above a central vector hero."""

    key = "highlighted_word_hero"
    name = "Highlighted-Word Hero"
    description = "Trust/intention message with one decisive plum-boxed word over a vector hero."

    def render(self, ctx: TemplateContext) -> str:
        nk = _as_nikah_context(ctx)
        svg = build_nikah_svg(
            self.key, copy=_ctx_copy(nk), format_key=nk.format_key,
            hero_symbol=nk.hero_symbol, logo_ref=nk.logo_ref, lattice_backdrop=nk.lattice_backdrop,
        )
        w, h = nk.size()
        return f'<div style="position:relative;width:{w}px;height:{h}px;overflow:hidden">{svg}</div>'

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        return _geometry(self.key, _as_nikah_context(ctx))


class ProtectionSymbolHero(LayoutTemplate):
    """Dominant shield/crescent/hands symbol beneath a concise headline."""

    key = "protection_symbol_hero"
    name = "Protection or Intention Symbol Hero"
    description = "Central protective symbol as the first read, restrained headline above."

    def render(self, ctx: TemplateContext) -> str:
        nk = _as_nikah_context(ctx)
        svg = build_nikah_svg(
            self.key, copy=_ctx_copy(nk), format_key=nk.format_key,
            hero_symbol=nk.hero_symbol, logo_ref=nk.logo_ref, lattice_backdrop=nk.lattice_backdrop,
        )
        w, h = nk.size()
        return f'<div style="position:relative;width:{w}px;height:{h}px;overflow:hidden">{svg}</div>'

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        return _geometry(self.key, _as_nikah_context(ctx))


class AyahTranslation(LayoutTemplate):
    """Arabic ayah panel with an LTR translation and restrained invitation."""

    key = "ayah_translation"
    name = "Ayah + Translation"
    description = "Amiri-set Arabic ayah panel, plain-English translation, and gentle CTA."

    def render(self, ctx: TemplateContext) -> str:
        nk = _as_nikah_context(ctx)
        svg = build_nikah_svg(
            self.key,
            copy=_ctx_copy(nk),
            format_key=nk.format_key,
            hero_symbol=nk.hero_symbol,
            logo_ref=nk.logo_ref,
            lattice_backdrop=nk.lattice_backdrop,
            direction="rtl",
        )
        w, h = nk.size()
        return (
            f'<div style="position:relative;width:{w}px;height:{h}px;'
            f'overflow:hidden">{svg}</div>'
        )

    def geometry(self, ctx: TemplateContext) -> TemplateGeometry:
        return _geometry(self.key, _as_nikah_context(ctx))


def _geometry(archetype: str, nk: NikahTemplateContext) -> TemplateGeometry:
    comp = _compose(
        archetype, copy=_ctx_copy(nk), format_key=nk.format_key,
        hero_symbol=nk.hero_symbol, logo_ref=nk.logo_ref, lattice_backdrop=nk.lattice_backdrop,
        ground_gradient=nk.ground_gradient,
    )
    text_zones = [
        ZoneRect(x=comp.headline_bbox[0], y=comp.headline_bbox[1], w=comp.headline_bbox[2], h=comp.headline_bbox[3]),
    ]
    if comp.highlight_word:
        text_zones.append(
            ZoneRect(x=comp.highlight_bbox[0], y=comp.highlight_bbox[1], w=comp.highlight_bbox[2], h=comp.highlight_bbox[3])
        )
    if comp.support_lines:
        text_zones.append(
            ZoneRect(x=comp.support_bbox[0], y=comp.support_bbox[1], w=comp.support_bbox[2], h=comp.support_bbox[3])
        )
    if comp.cta_label:
        text_zones.append(
            ZoneRect(x=comp.cta_bbox[0], y=comp.cta_bbox[1], w=comp.cta_bbox[2], h=comp.cta_bbox[3])
        )
    logo_zone = ZoneRect(x=comp.wm_bbox[0], y=comp.wm_bbox[1], w=comp.wm_bbox[2], h=comp.wm_bbox[3])
    # text sits on the ground, never on the hero symbol.
    return TemplateGeometry(text_zones=text_zones, logo_zone=logo_zone, text_over_imagery=False)


NIKAH_TEMPLATES: dict[str, LayoutTemplate] = {
    t.key: t
    for t in (
        HighlightedWordHero(),
        ProtectionSymbolHero(),
        AyahTranslation(),
    )
}
# ORCHESTRATOR: register into TEMPLATES / wire QA seam here.
# Intentionally NOT calling `TEMPLATES.update(NIKAH_TEMPLATES)` in this build — the QA-registry
# glue (so run_brand_qa's get_template()/geometry() resolve SN archetypes) is a separate,
# serialized wire-in step owned by the orchestrator (see docs/NIKAH_ENGINE_SPEC.md §3).


def build_nikah_html(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    profile: StyleProfile,
    hero_symbol: HeroSymbol = "hands_heart",
    logo_ref: str | None = None,
    lattice_backdrop: bool = True,
) -> str:
    """Editable HTML for structural tests (mirror of build_glo2go_html).

    Copy keys — highlighted_word_hero: ``headline`` + ``highlight`` (required; highlight must be a
    case-insensitive substring of headline), optional ``sub``/``subhead``, ``cta``.
    protection_symbol_hero: ``headline`` required; ``highlight``/``sub``/``cta`` optional.
    ayah_translation: Arabic ``ayah`` + Latin-script ``translation`` required; ``cta`` optional.
    """
    _require_nikah_profile(profile)
    svg = build_nikah_svg(
        archetype, copy=copy, format_key=format_key,
        hero_symbol=hero_symbol, logo_ref=logo_ref, lattice_backdrop=lattice_backdrop,
    )
    fmt = get_format(format_key)
    return (
        f'<div style="position:relative;width:{fmt.width}px;height:{fmt.height}px;'
        f'overflow:hidden">{svg}</div>'
    )


async def render_nikah(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    hero_symbol: HeroSymbol = "hands_heart",
    logo_ref: str | None = None,
    lattice_backdrop: bool = True,
    heading_font_ref: str | None = None,
    body_font_ref: str | None = None,
    direction: str = "ltr",
    script_font_ref: str | None = None,
) -> bytes:
    """Render a Simply Nikah archetype to PNG through the established Playwright rasterizer.

    Mirrors render_glo2go's call shape (minus image_ref — SN never takes a photo): loads
    get_style_profile("simply-nikah") internally (via _compose), builds the layered SVG, fails loud
    on unknown archetype/format/copy, and returns PNG bytes at exact format dimensions.

    ``heading_font_ref`` / ``body_font_ref`` are OPTIONAL brand-font files threaded into
    build_nikah_svg (see there); None keeps the system-font render (byte-identical).
    ``direction`` and ``script_font_ref`` use the same RTL/Arabic behavior as build_nikah_svg.
    """
    svg = build_nikah_svg(
        archetype, copy=copy, format_key=format_key,
        hero_symbol=hero_symbol, logo_ref=logo_ref, lattice_backdrop=lattice_backdrop,
        heading_font_ref=heading_font_ref, body_font_ref=body_font_ref,
        direction=direction, script_font_ref=script_font_ref,
    )
    return await rasterize_svg_to_png(svg, format_key)


# =============================================================================================
# Modesty QA (§4) — pure, structural, no network, no vision
# =============================================================================================

_APPROVED_SOURCE = "generated_vector"
_STRUCTURALLY_UNVERIFIABLE = "ai_illustration"


def modesty_report(svg_text: str, *, source_kind: str) -> list[str]:
    """Structural modesty / haya QA. Returns failure strings ("modesty: ..."); [] = pass.

    1. Source discipline: only ``generated_vector`` is approved. ``ai_illustration`` fails CLOSED
       (v1 has no vision-based face/modesty detector for the generated-pixel path); every other
       source (licensed_stock / ai_realistic / product_cutout / brand_placeholder / anything) fails.
    2. No unapproved raster: every ``<image>`` must sit inside a group with ``data-role="wordmark"``
       (the only approved raster — the supplied logo). Any other raster structurally implies a real
       photo / face pixels and fails.
    3. Faceless-by-construction: every ``<g data-figure="true">`` must also carry
       ``data-faceless="true"`` (catches a future primitive or a hand-edited SVG that adds a figure
       outside the approved vocabulary).
    """
    failures: list[str] = []

    if source_kind == _STRUCTURALLY_UNVERIFIABLE:
        failures.append(
            "modesty: source 'ai_illustration' fails closed in v1 — it can produce faces/immodest "
            "content and cannot be verified structurally (needs a vision detector)."
        )
        return failures
    if source_kind != _APPROVED_SOURCE:
        failures.append(f"modesty: source {source_kind!r} is not approved for simply-nikah")
        return failures

    try:
        root = ElementTree.fromstring(svg_text)
    except ElementTree.ParseError as exc:
        return [f"modesty: SVG did not parse for structural audit ({exc})"]

    image_tag = _svg_tag("image")
    group_tag = _svg_tag("g")

    # Build a child→parent map so we can check each <image>'s ancestor chain for the wordmark group.
    parents: dict[ElementTree.Element, ElementTree.Element] = {}
    for parent in root.iter():
        for child in parent:
            parents[child] = parent

    def _within_wordmark(element: ElementTree.Element) -> bool:
        node: ElementTree.Element | None = element
        while node is not None:
            if node.tag == group_tag and node.attrib.get("data-role") == "wordmark":
                return True
            node = parents.get(node)
        return False

    for element in root.iter(image_tag):
        if not _within_wordmark(element):
            failures.append(
                "modesty: raster <image> found outside the approved data-role='wordmark' group "
                "(real photos can only enter as raster, so unapproved raster is rejected)."
            )

    for group in root.iter(group_tag):
        if group.attrib.get("data-figure") == "true" and group.attrib.get("data-faceless") != "true":
            failures.append(
                "modesty: a <g data-figure='true'> is missing the required data-faceless='true' pair "
                "(figure was not built through the approved faceless vocabulary)."
            )

    return failures
