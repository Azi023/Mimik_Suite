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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal, cast
from xml.etree import ElementTree

from pydantic import field_validator

from mimik_contracts import (
    CreativeRect,
    MessageGeometry,
    MessageLineGeometry,
    ScaffoldGeometry,
    ScaffoldRegion,
    get_format,
)

from creative.knowledge.feedback import load_rules
from creative.render import nikah_primitives as prim
from creative.render.builtin_fonts import builtin_arabic_font_path, contains_arabic
from creative.render.compositor import (
    TextMeasurement,
    TextMeasureRequest,
    chromium_page,
    measure_svg_text,
    render_svg_with_geometry_on_page,
)
from creative.render.fonts import EmbeddedFont, embed_font_face, font_family_stack
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


class NikahLayoutError(ValueError):
    """Copy cannot be laid out without violating the measured safe-area invariants."""

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
_OVERRIDE_KEYS = frozenset(
    {"dx", "dy", "scale", "scale_x", "scale_y", "rotation", "visible", "fill"}
)

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
# Text wrapping (measured, balanced, deterministic)
# =============================================================================================


MeasureText = Callable[[str, int, int, str, str], TextMeasurement]


def _fallback_measure(
    text: str,
    font_size: int,
    _font_weight: int,
    _font_family: str,
    _direction: str,
) -> TextMeasurement:
    """Deterministic structural fallback for synchronous SVG-only callers.

    Production rendering supplies Chromium measurements. This fallback deliberately models
    individual glyph classes instead of using a character-count/average-glyph threshold.
    """
    width_units = 0.0
    for character in text:
        if character.isspace():
            width_units += 0.28
        elif character in "ilI.,'!|":
            width_units += 0.30
        elif character in "MW@%&":
            width_units += 0.88
        elif contains_arabic(character):
            width_units += 0.62
        elif character.isupper():
            width_units += 0.64
        else:
            width_units += 0.54
    return TextMeasurement(
        x=0.0,
        y=-0.80 * font_size,
        width=width_units * font_size,
        height=float(font_size),
    )


def _wrap(
    text: str,
    max_width: float,
    max_lines: int,
    *,
    measure: MeasureText,
    font_size: int,
    font_weight: int,
    font_family: str,
    direction: str,
) -> tuple[str, ...] | None:
    """Return the best measured line breaks, or None when the text cannot fit."""
    if not text:
        return ()
    words = text.split()
    if not words:
        return ()

    widths: dict[tuple[int, int], float] = {}

    def _width(start: int, end: int) -> float:
        key = (start, end)
        if key not in widths:
            widths[key] = measure(
                " ".join(words[start:end]),
                font_size,
                font_weight,
                font_family,
                direction,
            ).width
        return widths[key]

    # Prefer the fewest lines that fit. Within that line count minimize ragging, with a strong
    # widow penalty when the final line is one short word and a balanced break exists.
    for line_count in range(1, max_lines + 1):
        best: tuple[float, tuple[str, ...]] | None = None

        def _search(start: int, remaining: int, lines: tuple[str, ...], score: float) -> None:
            nonlocal best
            if remaining == 1:
                if start >= len(words) or _width(start, len(words)) > max_width:
                    return
                final = " ".join(words[start:])
                final_score = score + (max_width - _width(start, len(words))) ** 2 * 0.15
                if len(words) - start == 1 and len(words[start]) <= 5 and lines:
                    final_score += max_width**2
                candidate = (*lines, final)
                if best is None or (final_score, candidate) < best:
                    best = (final_score, candidate)
                return

            last_end = len(words) - remaining + 1
            for end in range(start + 1, last_end + 1):
                width = _width(start, end)
                if width > max_width:
                    break
                line = " ".join(words[start:end])
                _search(
                    end,
                    remaining - 1,
                    (*lines, line),
                    score + (max_width - width) ** 2,
                )

        _search(0, line_count, (), 0.0)
        if best is not None:
            return best[1]
    return None


# =============================================================================================
# Composition — one frozen dataclass per render, shared by SVG / HTML / geometry
# =============================================================================================


@dataclass(frozen=True)
class _TextLine:
    role: Literal["headline", "highlight", "support", "cta"]
    text: str
    x: int
    baseline: int
    font: int
    weight: int
    font_family: str
    fill: str
    opacity: float
    anchor: str
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class _ResolvedFonts:
    heading: EmbeddedFont | None
    body: EmbeddedFont | None
    script: EmbeddedFont | None
    heading_family: str
    body_family: str
    script_family: str

    @property
    def face_css(self) -> str:
        return "".join(
            font.face_css
            for font in (self.heading, self.body, self.script)
            if font is not None
        )


@dataclass(frozen=True)
class _NikahComposition:
    archetype: str
    w: int
    h: int
    grid_step: int
    rule_ids: str
    palette: dict[str, str]
    font_family: str
    metrics_source: Literal["chromium", "fallback"]
    safe_bbox: tuple[int, int, int, int]
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
    highlight_family: str
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
    cta_family: str
    cta_bbox: tuple[int, int, int, int]
    cta_text_bbox: tuple[int, int, int, int]
    # backdrop bboxes
    bg_bbox: tuple[int, int, int, int]
    motif_bbox: tuple[int, int, int, int]

    @property
    def message(self) -> MessageGeometry:
        lines = (*self.headline_lines, *self.support_lines)
        if self.highlight_word:
            lines = (
                *lines,
                _TextLine(
                    role="highlight",
                    text=self.highlight_word,
                    x=self.highlight_x,
                    baseline=self.highlight_y + round(self.highlight_bbox[3] / 2),
                    font=self.highlight_font,
                    weight=760,
                    font_family=self.highlight_family,
                    fill=self.palette["cloud"],
                    opacity=1.0,
                    anchor="start",
                    bbox=_highlight_text_bbox(self),
                ),
            )
        if self.cta_label:
            lines = (
                *lines,
                _TextLine(
                    role="cta",
                    text=self.cta_label,
                    x=self.cta_cx,
                    baseline=self.cta_top + round(self.cta_h / 2),
                    font=round(self.cta_h * 0.40),
                    weight=700,
                    font_family=self.cta_family,
                    fill=self.palette["cloud"],
                    opacity=1.0,
                    anchor="middle",
                    bbox=self.cta_text_bbox,
                ),
            )
        return MessageGeometry(
            lines=[
                MessageLineGeometry(
                    role=line.role,
                    text=line.text,
                    bbox=_rect(line.bbox),
                    baseline=line.baseline,
                    font_family=line.font_family,
                    font_size=line.font,
                    font_weight=line.weight,
                    colour=line.fill,
                    opacity=line.opacity,
                )
                for line in lines
            ]
        )

    @property
    def scaffold(self) -> ScaffoldGeometry:
        regions = [
            ScaffoldRegion(name="logo", role="content", bbox=_rect(self.wm_bbox)),
            ScaffoldRegion(name="headline", role="content", bbox=_rect(self.headline_bbox)),
        ]
        if self.highlight_word:
            regions.append(
                ScaffoldRegion(
                    name="highlight",
                    role="content",
                    bbox=_rect(self.highlight_bbox),
                )
            )
        if self.support_lines:
            regions.append(
                ScaffoldRegion(name="support", role="content", bbox=_rect(self.support_bbox))
            )
        if self.cta_label:
            regions.append(
                ScaffoldRegion(name="cta", role="content", bbox=_rect(self.cta_bbox))
            )
        hero_role: Literal["decoration", "container"] = (
            "container" if self.archetype == "ayah_translation" else "decoration"
        )
        regions.extend(
            (
                ScaffoldRegion(name="hero", role=hero_role, bbox=_rect(self.hero_bbox)),
                ScaffoldRegion(name="glow", role=hero_role, bbox=_rect(self.glow_bbox)),
            )
        )
        return ScaffoldGeometry(
            archetype=self.archetype,
            measurement_engine=self.metrics_source,
            safe_area=_rect(self.safe_bbox),
            regions=regions,
        )


@dataclass(frozen=True)
class NikahRenderResult:
    svg: str
    png: bytes
    scaffold: ScaffoldGeometry
    message: MessageGeometry


def _rect(bbox: tuple[int, int, int, int]) -> CreativeRect:
    return CreativeRect(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])


def _highlight_text_bbox(comp: _NikahComposition) -> tuple[int, int, int, int]:
    return (
        comp.highlight_x + round(0.45 * comp.highlight_font),
        comp.highlight_y + round(0.22 * comp.highlight_font),
        max(1, comp.highlight_bbox[2] - round(0.90 * comp.highlight_font)),
        max(1, comp.highlight_bbox[3] - round(0.44 * comp.highlight_font)),
    )


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


def _resolve_fonts(
    *,
    heading_font_ref: str | None,
    body_font_ref: str | None,
    script_font_ref: str | None,
    needs_script: bool,
) -> _ResolvedFonts:
    heading = (
        embed_font_face(heading_font_ref, family=_HEADING_FONT_FAMILY)
        if heading_font_ref
        else None
    )
    body = (
        embed_font_face(body_font_ref, family=_BODY_FONT_FAMILY)
        if body_font_ref
        else None
    )
    script = (
        embed_font_face(
            script_font_ref or str(builtin_arabic_font_path()),
            family=_SCRIPT_FONT_FAMILY,
        )
        if needs_script
        else None
    )
    return _ResolvedFonts(
        heading=heading,
        body=body,
        script=script,
        heading_family=(
            font_family_stack(heading.family, _SYSTEM_FONT) if heading else _SYSTEM_FONT
        ),
        body_family=font_family_stack(body.family, _SYSTEM_FONT) if body else _SYSTEM_FONT,
        script_family=(
            font_family_stack(script.family, _SYSTEM_FONT) if script else _SYSTEM_FONT
        ),
    )


def _positioned_text_bbox(
    metric: TextMeasurement,
    *,
    x: float,
    baseline: float,
    anchor: str,
) -> tuple[int, int, int, int]:
    if anchor == "middle":
        left = x - metric.width / 2
    elif anchor == "end":
        left = x - metric.width
    else:
        left = x
    return (
        round(left),
        round(baseline + metric.y),
        max(1, round(metric.width)),
        max(1, round(metric.height)),
    )


def _union_bboxes(
    bboxes: list[tuple[int, int, int, int]],
) -> tuple[int, int, int, int] | None:
    if not bboxes:
        return None
    left = min(bbox[0] for bbox in bboxes)
    top = min(bbox[1] for bbox in bboxes)
    right = max(bbox[0] + bbox[2] for bbox in bboxes)
    bottom = max(bbox[1] + bbox[3] for bbox in bboxes)
    return left, top, max(1, right - left), max(1, bottom - top)


def _compose(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    hero_symbol: HeroSymbol,
    logo_ref: str | None,
    lattice_backdrop: bool,
    ground_gradient: bool | None = None,
    measure: MeasureText = _fallback_measure,
    fonts: _ResolvedFonts | None = None,
    direction: str = "ltr",
    metrics_source: Literal["chromium", "fallback"] = "fallback",
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
    safe_left = fmt.safe_zone.left
    safe_top = fmt.safe_zone.top
    safe_right = w - fmt.safe_zone.right
    safe_bottom = h - fmt.safe_zone.bottom
    safe_width = safe_right - safe_left
    safe_height = safe_bottom - safe_top
    safe_bbox = (safe_left, safe_top, safe_width, safe_height)
    if fonts is None:
        fonts = _resolve_fonts(
            heading_font_ref=None,
            body_font_ref=None,
            script_font_ref=None,
            needs_script=direction == "rtl" or archetype == "ayah_translation",
        )

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
    if len(headline.split()) > 60 or (support is not None and len(support.split()) > 80):
        raise NikahLayoutError(
            f"Simply Nikah {archetype} content does not fit {format_key} "
            "within the permitted copy capacity"
        )

    # --- wordmark -----------------------------------------------------------------------------
    wm_cx = round(w / 2)
    wm_h = max(40, round(0.033 * h))
    wm_baseline = safe_top + wm_h
    wm_w = min(round(w * 0.5), safe_width)
    wm_bbox = (round(w / 2 - wm_w / 2), safe_top, wm_w, round(wm_h * 1.15))

    # --- headline column ----------------------------------------------------------------------
    base_head_font = round(params["headline_font_frac"] * w)
    head_weight = int(params["headline_weight"])
    head_width = min(round(w * 0.778), safe_width)
    head_x0 = round((w - head_width) / 2)
    head_cx = round(w / 2)
    head_top = wm_bbox[1] + wm_bbox[3] + round(0.035 * h)
    heading_direction = "rtl" if is_ayah else direction
    heading_family = (
        fonts.script_family if is_ayah or contains_arabic(headline) else fonts.heading_family
    )

    # Split the headline around the (case-insensitive) highlight occurrence. v1 stacks the boxed
    # word on its own centred line (before-words above, after-words below) rather than true inline
    # flow — the box still owns layer-highlight-word; surrounding words own layer-headline.
    before_text = headline
    after_text = ""
    highlight_word: str | None = None
    if highlight is not None:
        idx = headline.lower().find(highlight.lower())
        if idx < 0:
            raise NikahLayoutError(
                f"'highlight' {highlight!r} must be a case-insensitive substring of the headline"
            )
        before_text = headline[:idx].strip()
        highlight_word = headline[idx : idx + len(highlight)].strip()
        after_text = headline[idx + len(highlight) :].strip()

    # --- cta ----------------------------------------------------------------------------------
    cta_h = round(0.062 * h)
    cta_top = safe_bottom - cta_h
    cta_font = round(cta_h * 0.40)
    cta_family = (
        fonts.script_family
        if cta_label and contains_arabic(cta_label)
        else fonts.body_family
    )
    if cta_label:
        cta_metric = measure(cta_label, cta_font, 700, cta_family, direction)
        pill_w = max(cta_h * 2.2, cta_metric.width + 2 * cta_h * 0.72)
        if pill_w > safe_width:
            raise NikahLayoutError(
                f"Simply Nikah {archetype} content does not fit {format_key}: CTA exceeds safe width"
            )
        cta_bbox = (round(w / 2 - pill_w / 2), cta_top, round(pill_w), cta_h)
        cta_text_bbox = (
            round(w / 2 - cta_metric.width / 2),
            round(cta_top + cta_h / 2 - cta_metric.height / 2),
            max(1, round(cta_metric.width)),
            max(1, round(cta_metric.height)),
        )
    else:
        cta_bbox = (round(w / 2), cta_top, 0, 0)
        cta_text_bbox = (round(w / 2), cta_top, 1, 1)

    # --- measured text stack + largest remaining hero rectangle -------------------------------
    base_support_font = round(params["support_font_frac"] * w)
    min_scale = 0.78
    selected: tuple[
        int,
        int,
        list[_TextLine],
        tuple[int, int, int, int],
        str | None,
        int,
        int,
        tuple[int, int, int, int],
        list[_TextLine],
        tuple[int, int, int, int],
        tuple[int, int, int, int],
        tuple[int, int, int, int],
        int,
        int,
        int,
        int,
        int,
    ] | None = None

    min_head_font = max(1, round(base_head_font * min_scale))
    min_support_font = max(1, round(base_support_font * min_scale))
    for head_font in range(base_head_font, min_head_font - 1, -2):
        head_lh = round(head_font * 1.08)
        before_lines = _wrap(
            before_text,
            head_width,
            int(params["headline_max_lines"]),
            measure=measure,
            font_size=head_font,
            font_weight=head_weight,
            font_family=heading_family,
            direction=heading_direction,
        )
        after_lines = _wrap(
            after_text,
            head_width,
            int(params["headline_max_lines"]),
            measure=measure,
            font_size=head_font,
            font_weight=head_weight,
            font_family=heading_family,
            direction=heading_direction,
        )
        if before_lines is None or after_lines is None:
            continue
        if len(before_lines) + len(after_lines) > int(params["headline_max_lines"]):
            continue

        for support_font in range(base_support_font, min_support_font - 1, -1):
            support_family = (
                fonts.script_family
                if support and contains_arabic(support)
                else fonts.body_family
            )
            support_direction = "ltr" if is_ayah else direction
            wrapped_support = (
                _wrap(
                    support,
                    head_width,
                    2,
                    measure=measure,
                    font_size=support_font,
                    font_weight=430,
                    font_family=support_family,
                    direction=support_direction,
                )
                if support
                else ()
            )
            if wrapped_support is None:
                continue

            y = head_top
            built_headline: list[_TextLine] = []

            def _append_headline(line_text: str) -> None:
                nonlocal y
                metric = measure(
                    line_text,
                    head_font,
                    head_weight,
                    heading_family,
                    heading_direction,
                )
                baseline = y - metric.y
                anchor = "end" if is_ayah else "middle"
                x = head_x0 + head_width if is_ayah else head_cx
                built_headline.append(
                    _TextLine(
                        role="headline",
                        text=line_text,
                        x=x,
                        baseline=round(baseline),
                        font=head_font,
                        weight=head_weight,
                        font_family=heading_family,
                        fill=palette["plum"],
                        opacity=1.0,
                        anchor=anchor,
                        bbox=_positioned_text_bbox(metric, x=x, baseline=baseline, anchor=anchor),
                    )
                )
                y += head_lh

            for line_text in before_lines:
                _append_headline(line_text)

            highlight_x = head_x0
            highlight_y = round(y)
            highlight_bbox = (head_x0, round(y), 1, 1)
            if highlight_word:
                highlight_metric = measure(
                    highlight_word.upper(),
                    head_font,
                    760,
                    heading_family,
                    direction,
                )
                box_w = round(highlight_metric.width + 2 * 0.45 * head_font)
                box_h = round(highlight_metric.height + 2 * 0.22 * head_font)
                if box_w > head_width:
                    continue
                highlight_x = round(head_cx - box_w / 2)
                highlight_bbox = (highlight_x, highlight_y, box_w, box_h)
                y += box_h + round(head_font * 0.14)

            for line_text in after_lines:
                _append_headline(line_text)

            headline_bbox = _union_bboxes(
                [line.bbox for line in built_headline]
                + ([highlight_bbox] if highlight_word else [])
            )
            if headline_bbox is None:
                headline_bbox = (head_x0, head_top, 1, 1)

            if is_ayah:
                panel_padding = round(w * 0.045)
                panel_x = max(safe_left, round(w * 0.10))
                panel_w = min(round(w * 0.80), safe_width)
                panel_y = max(safe_top, headline_bbox[1] - panel_padding)
                panel_bottom = headline_bbox[1] + headline_bbox[3] + panel_padding
                panel_h = panel_bottom - panel_y
                hero_bbox = (panel_x, panel_y, panel_w, panel_h)
                support_top = panel_bottom + round(0.035 * h)
            else:
                hero_bbox = (0, 0, 1, 1)
                support_top = headline_bbox[1] + headline_bbox[3] + round(
                    params["support_margin_frac"] * w
                )

            support_lh = round(support_font * 1.45)
            sy = support_top
            built_support: list[_TextLine] = []
            for line_text in wrapped_support:
                metric = measure(
                    line_text,
                    support_font,
                    430,
                    support_family,
                    support_direction,
                )
                baseline = sy - metric.y
                built_support.append(
                    _TextLine(
                        role="support",
                        text=line_text,
                        x=head_cx,
                        baseline=round(baseline),
                        font=support_font,
                        weight=430,
                        font_family=support_family,
                        fill=palette["plum"],
                        opacity=float(params["support_opacity"]),
                        anchor="middle",
                        bbox=_positioned_text_bbox(
                            metric,
                            x=head_cx,
                            baseline=baseline,
                            anchor="middle",
                        ),
                    )
                )
                sy += support_lh
            support_bbox = _union_bboxes([line.bbox for line in built_support])
            if support_bbox is None:
                support_bbox = (head_cx, round(support_top), 1, 1)
            support_bottom = support_bbox[1] + support_bbox[3]

            if is_ayah:
                glow_pad_x = round(hero_bbox[2] * 0.04)
                glow_pad_y = round(hero_bbox[3] * 0.08)
                glow_bbox = (
                    max(safe_left, hero_bbox[0] - glow_pad_x),
                    max(safe_top, hero_bbox[1] - glow_pad_y),
                    min(safe_right, hero_bbox[0] + hero_bbox[2] + glow_pad_x)
                    - max(safe_left, hero_bbox[0] - glow_pad_x),
                    min(safe_bottom, hero_bbox[1] + hero_bbox[3] + glow_pad_y)
                    - max(safe_top, hero_bbox[1] - glow_pad_y),
                )
                if support_bottom + round(0.025 * h) > cta_top:
                    continue
                hero_cx = hero_bbox[0] + round(hero_bbox[2] / 2)
                hero_cy = hero_bbox[1] + round(hero_bbox[3] / 2)
                hero_box = hero_bbox[2]
                glow_rx = round(glow_bbox[2] / 2)
                glow_ry = round(glow_bbox[3] / 2)
            else:
                free_top = support_bottom + round(0.025 * h)
                free_bottom = cta_top - round(0.025 * h)
                free_height = free_bottom - free_top
                max_hero = round(float(params["hero_frac"]) * w)
                hero_box = round(
                    min(max_hero, safe_width / 1.35, free_height / 1.20)
                )
                min_hero = round(w * 0.10)
                if hero_box < min_hero:
                    continue
                hero_cx = round((safe_left + safe_right) / 2)
                hero_cy = round((free_top + free_bottom) / 2)
                half = hero_box / 2
                hero_bbox = (
                    round(hero_cx - half),
                    round(hero_cy - half),
                    hero_box,
                    hero_box,
                )
                glow_rx = round(1.35 * half)
                glow_ry = round(1.20 * half)
                glow_bbox = (
                    hero_cx - glow_rx,
                    hero_cy - glow_ry,
                    2 * glow_rx,
                    2 * glow_ry,
                )

            selected = (
                head_font,
                support_font,
                built_headline,
                headline_bbox,
                highlight_word,
                highlight_x,
                highlight_y,
                highlight_bbox,
                built_support,
                support_bbox,
                hero_bbox,
                glow_bbox,
                hero_cx,
                hero_cy,
                hero_box,
                glow_rx,
                glow_ry,
            )
            break
        if selected is not None:
            break

    if selected is None:
        raise NikahLayoutError(
            f"Simply Nikah {archetype} content does not fit {format_key} "
            "within safe margins and permitted font shrink range"
        )

    (
        head_font,
        _support_font,
        headline_lines,
        headline_bbox,
        highlight_word,
        highlight_x,
        highlight_y,
        highlight_bbox,
        support_lines,
        support_bbox,
        hero_bbox,
        glow_bbox,
        hero_cx,
        hero_cy,
        hero_box,
        glow_rx,
        glow_ry,
    ) = selected

    composition = _NikahComposition(
        archetype=archetype,
        w=w,
        h=h,
        grid_step=grid_step,
        rule_ids=rule_ids,
        palette=palette,
        font_family=_SYSTEM_FONT,
        metrics_source=metrics_source,
        safe_bbox=safe_bbox,
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
        highlight_font=head_font,
        highlight_family=heading_family,
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
        cta_family=cta_family,
        cta_bbox=cta_bbox,
        cta_text_bbox=cta_text_bbox,
        bg_bbox=(0, 0, w, h),
        motif_bbox=(0, 0, w, h),
    )
    _validate_composition(composition)
    return composition


def _validate_composition(comp: _NikahComposition) -> None:
    safe_x, safe_y, safe_width, safe_height = comp.safe_bbox
    safe_right = safe_x + safe_width
    safe_bottom = safe_y + safe_height

    def _inside(bbox: tuple[int, int, int, int]) -> bool:
        x, y, width, height = bbox
        return (
            x >= safe_x
            and y >= safe_y
            and x + width <= safe_right
            and y + height <= safe_bottom
        )

    checked = [comp.wm_bbox, comp.headline_bbox, comp.hero_bbox, comp.glow_bbox]
    if comp.highlight_word:
        checked.append(comp.highlight_bbox)
    if comp.support_lines:
        checked.append(comp.support_bbox)
    if comp.cta_label:
        checked.append(comp.cta_bbox)
    if not all(_inside(bbox) for bbox in checked):
        raise NikahLayoutError(
            f"Simply Nikah {comp.archetype} layout violates the safe margins"
        )

    if comp.archetype == "ayah_translation":
        return
    decorations = (comp.hero_bbox, comp.glow_bbox)
    for line in comp.message.lines:
        text_bbox = (
            line.bbox.x,
            line.bbox.y,
            line.bbox.width,
            line.bbox.height,
        )
        if any(_bbox_intersects(text_bbox, decoration) for decoration in decorations):
            raise NikahLayoutError(
                f"Simply Nikah {comp.archetype} layout has text/decoration overlap"
            )


def _bbox_intersects(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


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
    _measure: MeasureText | None = None,
    _composition: _NikahComposition | None = None,
    _fonts: _ResolvedFonts | None = None,
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

    needs_script_font = direction == "rtl" or archetype == "ayah_translation"
    fonts = _fonts or _resolve_fonts(
        heading_font_ref=heading_font_ref,
        body_font_ref=body_font_ref,
        script_font_ref=script_font_ref,
        needs_script=needs_script_font,
    )
    comp = _composition or _compose(
        archetype,
        copy=copy,
        format_key=format_key,
        hero_symbol=hero_symbol,
        logo_ref=logo_ref,
        lattice_backdrop=lattice_backdrop,
        measure=_measure or _fallback_measure,
        fonts=fonts,
        direction=direction,
    )
    heading_family = fonts.heading_family
    body_family = fonts.body_family
    script_family = fonts.script_family

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
            "data-layout-engine": "nikah-layout-v1",
            "data-text-metrics": comp.metrics_source,
            "data-archetype": comp.archetype,
            "data-safe-area": " ".join(str(value) for value in comp.safe_bbox),
        },
    )

    # Optional brand-font faces go in a document <style> so Playwright loads them before paint.
    # Only emitted when a font is supplied — the no-font path adds nothing (byte-identical).
    if fonts.face_css:
        style = ElementTree.SubElement(root, _svg_tag("style"), {"type": "text/css"})
        style.text = fonts.face_css

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
    glow.set(
        "data-occluding",
        "false" if comp.archetype == "ayah_translation" else "true",
    )
    if comp.archetype == "ayah_translation":
        glow.set("data-container", "true")
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
    hero.set(
        "data-occluding",
        "false" if comp.archetype == "ayah_translation" else "true",
    )
    if comp.archetype == "ayah_translation":
        hero.set("data-container", "true")
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
            text_width=_highlight_text_bbox(comp)[2],
        )
        _embed_fragment(highlight, box_svg)
        for text in highlight.iter(_svg_tag("text")):
            text.set("data-role", "highlight")
            text.set(
                "data-bbox",
                " ".join(str(value) for value in _highlight_text_bbox(comp)),
            )
        if direction == "rtl" and archetype != "ayah_translation":
            for text in highlight.iter(_svg_tag("text")):
                text.set("direction", "rtl")
                text.set("text-anchor", "start")
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
            text_width=comp.cta_text_bbox[2],
        )
        _embed_fragment(cta, pill_svg)
        for text in cta.iter(_svg_tag("text")):
            text.set("data-role", "cta")
            text.set(
                "data-bbox",
                " ".join(str(value) for value in comp.cta_text_bbox),
            )
        if direction == "rtl" and archetype != "ayah_translation":
            cta_right = comp.cta_cx + _pw / 2 - comp.cta_h * 0.72
            for text in cta.iter(_svg_tag("text")):
                text.set("direction", "rtl")
                text.set("text-anchor", "start")
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
    # In SVG, ``start`` is the visual right edge when direction=rtl. Using ``end`` places the
    # glyph run to the right of x and makes metadata claim a box different from Chromium ink.
    anchor = "start" if direction == "rtl" else line.anchor
    x = right_edge if direction == "rtl" and right_edge is not None else line.x
    attrs = {
        "x": str(x),
        "y": str(line.baseline),
        "data-role": line.role,
        "data-bbox": " ".join(str(value) for value in line.bbox),
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


def layout_layers_from_svg(
    svg: str,
) -> tuple[ScaffoldGeometry, MessageGeometry] | None:
    """Recover typed L3/L4 geometry from a measured Simply Nikah SVG."""
    root = ElementTree.fromstring(svg)
    if root.get("data-layout-engine") != "nikah-layout-v1":
        return None
    raw_safe = root.get("data-safe-area", "").split()
    if len(raw_safe) != 4:
        raise ValueError("Measured Nikah SVG is missing a valid data-safe-area")
    safe_bbox = tuple(int(round(float(value))) for value in raw_safe)
    archetype = root.get("data-archetype")
    if not archetype:
        raise ValueError("Measured Nikah SVG is missing data-archetype")

    regions: list[ScaffoldRegion] = []
    region_map = {
        "layer-wordmark": ("logo", "content"),
        "layer-headline": ("headline", "content"),
        "layer-highlight-word": ("highlight", "content"),
        "layer-support": ("support", "content"),
        "layer-cta": ("cta", "content"),
        "layer-hero": ("hero", "decoration"),
        "layer-glow": ("glow", "decoration"),
    }
    for group in root.iter(_svg_tag("g")):
        layer_id = group.get("id")
        if layer_id not in region_map:
            continue
        if layer_id in {"layer-highlight-word", "layer-support", "layer-cta"}:
            if not any(True for _ in group.iter(_svg_tag("text"))):
                continue
        raw_bbox = group.get("data-bbox", "").split()
        if len(raw_bbox) != 4:
            continue
        bbox = tuple(int(round(float(value))) for value in raw_bbox)
        name, default_role = region_map[layer_id]
        role = "container" if group.get("data-container") == "true" else default_role
        regions.append(
            ScaffoldRegion(
                name=name,
                role=cast(Literal["content", "decoration", "container"], role),
                bbox=_rect(cast(tuple[int, int, int, int], bbox)),
            )
        )

    lines: list[MessageLineGeometry] = []
    for text in root.iter(_svg_tag("text")):
        role = text.get("data-role")
        raw_bbox = text.get("data-bbox", "").split()
        if role not in {"headline", "highlight", "support", "cta"} or len(raw_bbox) != 4:
            continue
        bbox = tuple(int(round(float(value))) for value in raw_bbox)
        lines.append(
            MessageLineGeometry(
                role=cast(Literal["headline", "highlight", "support", "cta"], role),
                text=text.text or "",
                bbox=_rect(cast(tuple[int, int, int, int], bbox)),
                baseline=round(float(text.get("y", "0"))),
                font_family=text.get("font-family", _SYSTEM_FONT),
                font_size=max(1, round(float(text.get("font-size", "1")))),
                font_weight=max(1, round(float(text.get("font-weight", "400")))),
                colour=text.get("fill", _PLUM_FALLBACK),
                opacity=float(text.get("fill-opacity", "1")),
            )
        )

    return (
        ScaffoldGeometry(
            archetype=archetype,
            measurement_engine=cast(
                Literal["chromium", "fallback"],
                root.get("data-text-metrics", "fallback"),
            ),
            safe_area=_rect(cast(tuple[int, int, int, int], safe_bbox)),
            regions=regions,
        ),
        MessageGeometry(lines=lines),
    )


def _validate_rendered_geometry(svg: str, *, format_key: str) -> None:
    """Validate Chromium-normalized boxes after editor transforms are applied."""
    root = ElementTree.fromstring(svg)
    raw_safe = root.get("data-safe-area", "").split()
    if len(raw_safe) != 4:
        raise NikahLayoutError("Measured Simply Nikah SVG has no valid safe area")
    safe = tuple(int(round(float(value))) for value in raw_safe)
    safe_x, safe_y, safe_width, safe_height = safe
    safe_right = safe_x + safe_width
    safe_bottom = safe_y + safe_height

    def _bbox(element: ElementTree.Element) -> tuple[int, int, int, int]:
        raw = element.get("data-bbox", "").split()
        if len(raw) != 4:
            label = element.get("id") or element.get("data-role") or element.tag
            raise NikahLayoutError(f"Measured Simply Nikah element {label!r} has no valid bbox")
        values = tuple(int(round(float(value))) for value in raw)
        x, y, width, height = values
        if width <= 0 or height <= 0:
            raise NikahLayoutError("Measured Simply Nikah element has an empty bbox")
        return cast(tuple[int, int, int, int], values)

    def _inside(bbox: tuple[int, int, int, int]) -> bool:
        x, y, width, height = bbox
        return (
            x >= safe_x
            and y >= safe_y
            and x + width <= safe_right
            and y + height <= safe_bottom
        )

    layers = {
        group.get("id"): group
        for group in root.iter(_svg_tag("g"))
        if group.get("id", "").startswith("layer-")
    }
    safe_layer_ids = {
        "layer-wordmark",
        "layer-headline",
        "layer-highlight-word",
        "layer-support",
        "layer-cta",
        "layer-hero",
        "layer-glow",
    }
    for layer_id in safe_layer_ids:
        layer = layers.get(layer_id)
        if layer is None or layer.get("data-hidden") == "true":
            continue
        if layer_id in {"layer-highlight-word", "layer-support", "layer-cta"} and not any(
            True for _ in layer.iter(_svg_tag("text"))
        ):
            continue
        if not _inside(_bbox(layer)):
            raise NikahLayoutError(
                f"Simply Nikah {format_key} layer {layer_id} violates the safe margins"
            )

    text_boxes: list[tuple[str, tuple[int, int, int, int]]] = []
    for text in root.iter(_svg_tag("text")):
        if text.get("data-role") not in {"headline", "highlight", "support", "cta"}:
            continue
        bbox = _bbox(text)
        if not _inside(bbox):
            raise NikahLayoutError(
                f"Simply Nikah {format_key} text {text.get('data-role')} violates the safe margins"
            )
        text_boxes.append((text.get("data-role", "text"), bbox))

    wordmark = layers.get("layer-wordmark")
    if wordmark is not None and wordmark.get("data-hidden") != "true":
        for text in wordmark.iter(_svg_tag("text")):
            bbox = _bbox(text)
            if not _inside(bbox):
                raise NikahLayoutError(
                    f"Simply Nikah {format_key} wordmark text violates the safe margins"
                )
            text_boxes.append(("wordmark", bbox))

    decoration_boxes = [
        (layer_id, _bbox(layer))
        for layer_id, layer in layers.items()
        if layer.get("data-occluding") == "true" and layer.get("data-hidden") != "true"
    ]
    for text_role, text_bbox in text_boxes:
        for layer_id, decoration_bbox in decoration_boxes:
            if _bbox_intersects(text_bbox, decoration_bbox):
                raise NikahLayoutError(
                    f"Simply Nikah {format_key} text {text_role} intersects {layer_id}"
                )


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
        scale_x, scale_y = _axis_scale_overrides(override_value)
        rotation = _rotation_override(override_value)

        parts: list[str] = []
        if dx or dy:
            parts.append(f"translate({dx},{dy})")
        if rotation != 0.0:
            parts.append(f"rotate({rotation:g},{cx:g},{cy:g})")
        if scale_x != 1.0 or scale_y != 1.0:
            parts.extend(
                (
                    f"translate({cx:g},{cy:g})",
                    f"scale({scale_x:g},{scale_y:g})",
                    f"translate({-cx:g},{-cy:g})",
                )
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


def _axis_scale_overrides(override: Mapping[object, object]) -> tuple[float, float]:
    """Apply legacy uniform scale unless either explicit axis scale is present."""
    if "scale_x" not in override and "scale_y" not in override:
        uniform = _scale_override(override)
        return uniform, uniform
    return (
        _bounded_axis_scale(override, "scale_x"),
        _bounded_axis_scale(override, "scale_y"),
    )


def _bounded_axis_scale(override: Mapping[object, object], key: str) -> float:
    value = override[key] if key in override else 1.0
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Layer override {key!r} must be a float")
    scale = float(value)
    if not isfinite(scale) or scale <= 0:
        raise ValueError(f"Layer override {key!r} must be a positive finite number")
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


def _all_phrases(text: str) -> tuple[str, ...]:
    words = text.split()
    return tuple(
        " ".join(words[start:end])
        for start in range(len(words))
        for end in range(start + 1, len(words) + 1)
    )


def _measurement_plan(
    archetype: str,
    *,
    copy: dict[str, str],
    format_key: str,
    fonts: _ResolvedFonts,
    direction: str,
) -> tuple[
    list[TextMeasureRequest],
    dict[tuple[str, int, int, str, str], str],
]:
    params = _ARCHETYPE_PARAMS[archetype]
    fmt = get_format(format_key)
    is_ayah = archetype == "ayah_translation"
    headline = _copy_value(
        copy,
        "ayah" if is_ayah else "headline",
        required=True,
    )
    assert headline is not None
    support = (
        _copy_value(copy, "translation", "sub", "subhead", required=True)
        if is_ayah
        else _copy_value(copy, "sub", "subhead")
    )
    if len(headline.split()) > 60 or (support is not None and len(support.split()) > 80):
        raise NikahLayoutError(
            f"Simply Nikah {archetype} content does not fit {format_key} "
            "within the permitted copy capacity"
        )
    highlight = _copy_value(copy, "highlight", "highlight_word")
    before = headline
    after = ""
    if highlight:
        index = headline.lower().find(highlight.lower())
        if index < 0:
            raise ValueError(
                f"'highlight' {highlight!r} must be a case-insensitive substring of the headline"
            )
        before = headline[:index].strip()
        after = headline[index + len(highlight) :].strip()

    heading_direction = "rtl" if is_ayah else direction
    heading_family = (
        fonts.script_family if is_ayah or contains_arabic(headline) else fonts.heading_family
    )
    support_direction = "ltr" if is_ayah else direction
    support_family = (
        fonts.script_family if support and contains_arabic(support) else fonts.body_family
    )
    base_head = round(float(params["headline_font_frac"]) * fmt.width)
    min_head = max(1, round(base_head * 0.78))
    base_support = round(float(params["support_font_frac"]) * fmt.width)
    min_support = max(1, round(base_support * 0.78))

    specs: set[tuple[str, int, int, str, str]] = set()
    for size in range(base_head, min_head - 1, -2):
        for phrase in (*_all_phrases(before), *_all_phrases(after)):
            specs.add((phrase, size, int(params["headline_weight"]), heading_family, heading_direction))
        if highlight:
            specs.add((highlight.upper(), size, 760, heading_family, direction))
    if support:
        for size in range(base_support, min_support - 1, -1):
            for phrase in _all_phrases(support):
                specs.add((phrase, size, 430, support_family, support_direction))
    cta = _copy_value(copy, "cta")
    if cta:
        cta_size = round(round(0.062 * fmt.height) * 0.40)
        cta_family = fonts.script_family if contains_arabic(cta) else fonts.body_family
        specs.add((cta, cta_size, 700, cta_family, direction))

    ordered = sorted(specs)
    keys = {spec: f"text-{index}" for index, spec in enumerate(ordered)}
    requests = [
        TextMeasureRequest(
            key=keys[spec],
            text=spec[0],
            font_size=spec[1],
            font_weight=spec[2],
            font_family=spec[3],
            direction=spec[4],
        )
        for spec in ordered
    ]
    return requests, keys


async def render_nikah_with_layout(
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
    layer_overrides: Mapping[str, object] | None = None,
) -> NikahRenderResult:
    """Measure and render on one Chromium page, returning typed L3/L4 geometry."""
    if direction not in {"ltr", "rtl"}:
        raise ValueError("Simply Nikah text direction must be 'ltr' or 'rtl'")
    if archetype not in _ARCHETYPE_PARAMS:
        choices = ", ".join(sorted(_ARCHETYPE_PARAMS))
        raise ValueError(f"Unknown Simply Nikah archetype {archetype!r}; choose from: {choices}")

    fmt = get_format(format_key)
    fonts = _resolve_fonts(
        heading_font_ref=heading_font_ref,
        body_font_ref=body_font_ref,
        script_font_ref=script_font_ref,
        needs_script=direction == "rtl" or archetype == "ayah_translation",
    )
    requests, keys = _measurement_plan(
        archetype,
        copy=copy,
        format_key=format_key,
        fonts=fonts,
        direction=direction,
    )

    async with chromium_page(fmt.width, fmt.height) as page:
        measurements = await measure_svg_text(page, requests, font_css=fonts.face_css)

        def _measured(
            text: str,
            font_size: int,
            font_weight: int,
            font_family: str,
            text_direction: str,
        ) -> TextMeasurement:
            spec = (text, font_size, font_weight, font_family, text_direction)
            try:
                return measurements[keys[spec]]
            except KeyError as exc:
                raise ValueError(f"Missing Chromium text measurement for {spec!r}") from exc

        composition = _compose(
            archetype,
            copy=copy,
            format_key=format_key,
            hero_symbol=hero_symbol,
            logo_ref=logo_ref,
            lattice_backdrop=lattice_backdrop,
            measure=_measured,
            fonts=fonts,
            direction=direction,
            metrics_source="chromium",
        )
        svg = build_nikah_svg(
            archetype,
            copy=copy,
            format_key=format_key,
            hero_symbol=hero_symbol,
            logo_ref=logo_ref,
            lattice_backdrop=lattice_backdrop,
            heading_font_ref=heading_font_ref,
            body_font_ref=body_font_ref,
            direction=direction,
            script_font_ref=script_font_ref,
            layer_overrides=layer_overrides,
            _composition=composition,
            _fonts=fonts,
        )
        svg, png = await render_svg_with_geometry_on_page(
            page,
            svg,
            fmt.width,
            fmt.height,
        )
        geometry = layout_layers_from_svg(svg)
        if geometry is None:
            raise NikahLayoutError("Measured Simply Nikah SVG is missing L3/L4 geometry")
        scaffold, message = geometry
        _validate_rendered_geometry(svg, format_key=format_key)
    return NikahRenderResult(
        svg=svg,
        png=png,
        scaffold=scaffold,
        message=message,
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
    layer_overrides: Mapping[str, object] | None = None,
) -> bytes:
    """Render a Simply Nikah archetype to PNG through the established Playwright rasterizer.

    Mirrors render_glo2go's call shape (minus image_ref — SN never takes a photo): loads
    get_style_profile("simply-nikah") internally (via _compose), builds the layered SVG, fails loud
    on unknown archetype/format/copy, and returns PNG bytes at exact format dimensions.

    ``heading_font_ref`` / ``body_font_ref`` are OPTIONAL brand-font files threaded into
    build_nikah_svg (see there); None keeps the system-font render (byte-identical).
    ``direction`` and ``script_font_ref`` use the same RTL/Arabic behavior as build_nikah_svg.
    """
    result = await render_nikah_with_layout(
        archetype,
        copy=copy,
        format_key=format_key,
        hero_symbol=hero_symbol,
        logo_ref=logo_ref,
        lattice_backdrop=lattice_backdrop,
        heading_font_ref=heading_font_ref,
        body_font_ref=body_font_ref,
        direction=direction,
        script_font_ref=script_font_ref,
        layer_overrides=layer_overrides,
    )
    return result.png


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
