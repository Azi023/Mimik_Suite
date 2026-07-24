"""Simply Nikah vector primitive vocabulary — the reusable, faceless flat-vector set.

Every primitive is a **pure, deterministic function** returning an SVG *fragment* string (a
single-rooted `<g>`/`<path>`/`<pattern>`). No I/O, no randomness. Coordinates are canvas px,
top-left origin. Colors are supplied by the caller (the template resolves palette roles); the
palette-fallback constants below exist so callers share one source of truth.

Modesty is enforced BY CONSTRUCTION: no primitive draws facial-feature paths, and every
figure-depicting primitive stamps ``data-figure="true" data-faceless="true"`` on its root
group (``modesty_report`` asserts on this pair).

Fragments are authored as valid XML (text content HTML-escaped, attributes double-quoted so the
system font's single quotes are legal) so the template can parse-and-embed each fragment into the
namespaced SVG tree without a second escaping pass.

Design contract: docs/STYLE_PROFILES.md Profile 1 (the only taste source).
"""

from __future__ import annotations

from html import escape
from typing import Literal

# --- Palette fallbacks (all profile hexes are approx=True; these carry until onboarding) -------
# TODO(M3): swap for the confirmed brand hexes once onboarding replaces the approximate values.
_PINK_FALLBACK = "#FD62AD"  # primary — Simply Pink
_BLUSH_FALLBACK = "#F9C6DE"  # accent — Soft Blush
_PLUM_FALLBACK = "#2B0A2E"  # ink / cta_fill — Deep Plum
_LILAC_FALLBACK = "#9B7BA6"  # secondary — Muted Lilac
_CLOUD_FALLBACK = "#FAF7FB"  # ground — Cloud White

# TODO(M3): load the approved heading/body/greeting-script families after onboarding supplies them.
_SYSTEM_FONT = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

# Conservative glyph advance for a 700+-weight face — the SAME 0.60×font factor svg.py/glo2go use
# for box/measurement math, so callers can centre and flow boxed words consistently.
_HEAVY_GLYPH_FACTOR = 0.60


def _f(value: float) -> str:
    """Compact fixed-point number for path/attr strings (trims to 2 decimals)."""
    return f"{value:.2f}".rstrip("0").rstrip(".") if value % 1 else str(int(value))


# =============================================================================================
# v1 primitives (the six the two launch archetypes need)
# =============================================================================================


def lattice_pattern(
    pattern_id: str,
    *,
    tile: int = 120,
    stroke: str,
    stroke_width: float = 3.0,
    motif: Literal["eight_star", "hexagon"] = "eight_star",
    opacity: float = 0.10,
) -> str:
    """Tileable mashrabiya / Islamic-lattice ``<pattern>`` def.

    Returns the pattern element only; a caller references it via ``fill="url(#pattern_id)"`` on a
    ``<rect>`` (backdrop) or another shape (e.g. a shield's inner fill). Geometric 8-point-star or
    hex grid at whisper opacity so it reads as texture, never as competing ornament.
    """
    t = float(tile)
    inner = tuple(_f(v) for v in (t * 0.16, t * 0.84, t * 0.5))
    lo, hi, mid = inner
    if motif == "eight_star":
        # Two overlaid squares (one axis-aligned, one rotated 45°) = an 8-point star, plus a
        # small centre diamond. Stroke-only, whisper opacity — a continuous woven texture.
        motif_svg = (
            f'<rect x="{lo}" y="{lo}" width="{_f(t * 0.68)}" height="{_f(t * 0.68)}" rx="{_f(t * 0.04)}"/>'
            f'<rect x="{lo}" y="{lo}" width="{_f(t * 0.68)}" height="{_f(t * 0.68)}" rx="{_f(t * 0.04)}"'
            f' transform="rotate(45 {mid} {mid})"/>'
            f'<circle cx="{mid}" cy="{mid}" r="{_f(t * 0.10)}"/>'
        )
    else:  # hexagon
        # Pointy-top hexagon centred in the tile.
        cx = t * 0.5
        cy = t * 0.5
        rad = t * 0.42
        pts = []
        # 0.5235987756 rad = 30°; vertices at 30,90,...330
        offsets = (
            (0.5, 0.866),
            (1.0, 0.0),
            (0.5, -0.866),
            (-0.5, -0.866),
            (-1.0, 0.0),
            (-0.5, 0.866),
        )
        for ox, oy in offsets:
            pts.append(f"{_f(cx + rad * ox)},{_f(cy + rad * oy)}")
        motif_svg = f'<polygon points="{" ".join(pts)}"/>'
    return (
        f'<pattern id="{escape(pattern_id, quote=True)}" x="0" y="0" '
        f'width="{_f(t)}" height="{_f(t)}" patternUnits="userSpaceOnUse">'
        f'<g fill="none" stroke="{escape(stroke, quote=True)}" '
        f'stroke-width="{_f(stroke_width)}" opacity="{_f(opacity)}">{motif_svg}</g>'
        f"</pattern>"
    )


def crescent(
    cx: float,
    cy: float,
    r: float,
    *,
    fill: str,
    rotation: float = -20.0,
    thickness: float = 0.42,
) -> str:
    """Flat crescent moon: an outer circle minus an offset inner circle (single even-odd path).

    ``thickness`` (0..1) nudges how far the inner circle is offset — larger = a slimmer crescent.
    Rotated ``rotation`` degrees about (cx, cy).
    """
    outer_r = r
    inner_r = r * 0.86
    offset = r * (0.40 + thickness * 0.28)
    outer = (
        f"M {_f(cx - outer_r)} {_f(cy)} "
        f"a {_f(outer_r)} {_f(outer_r)} 0 1 0 {_f(2 * outer_r)} 0 "
        f"a {_f(outer_r)} {_f(outer_r)} 0 1 0 {_f(-2 * outer_r)} 0 Z"
    )
    inner = (
        f"M {_f(cx + offset - inner_r)} {_f(cy)} "
        f"a {_f(inner_r)} {_f(inner_r)} 0 1 0 {_f(2 * inner_r)} 0 "
        f"a {_f(inner_r)} {_f(inner_r)} 0 1 0 {_f(-2 * inner_r)} 0 Z"
    )
    return (
        f'<path d="{outer} {inner}" fill="{escape(fill, quote=True)}" fill-rule="evenodd" '
        f'transform="rotate({_f(rotation)} {_f(cx)} {_f(cy)})" data-role="crescent"/>'
    )


def _shield_path(cx: float, cy: float, w: float, h: float) -> str:
    """Soft-cornered heater-shield outline path, centred at (cx, cy)."""
    hw = w / 2
    hh = h / 2
    r = min(w, h) * 0.14  # top corner radius
    return (
        f"M {_f(cx - hw)} {_f(cy - hh + r)} "
        f"Q {_f(cx - hw)} {_f(cy - hh)} {_f(cx - hw + r)} {_f(cy - hh)} "
        f"L {_f(cx + hw - r)} {_f(cy - hh)} "
        f"Q {_f(cx + hw)} {_f(cy - hh)} {_f(cx + hw)} {_f(cy - hh + r)} "
        f"L {_f(cx + hw)} {_f(cy - hh + h * 0.42)} "
        f"Q {_f(cx + hw)} {_f(cy + h * 0.16)} {_f(cx)} {_f(cy + hh)} "
        f"Q {_f(cx - hw)} {_f(cy + h * 0.16)} {_f(cx - hw)} {_f(cy - hh + h * 0.42)} Z"
    )


def shield(
    cx: float,
    cy: float,
    w: float,
    h: float,
    *,
    fill: str,
    stroke: str | None = None,
    stroke_width: float = 0.0,
    fill_pattern_id: str | None = None,
) -> str:
    """Soft-cornered heater shield; optional inner lattice fill at low opacity, optional stroke."""
    path = _shield_path(cx, cy, w, h)
    parts = [f'<path d="{path}" fill="{escape(fill, quote=True)}"/>']
    if fill_pattern_id is not None:
        parts.append(
            f'<path d="{path}" fill="url(#{escape(fill_pattern_id, quote=True)})"/>'
        )
    if stroke is not None and stroke_width > 0:
        parts.append(
            f'<path d="{path}" fill="none" stroke="{escape(stroke, quote=True)}" '
            f'stroke-width="{_f(stroke_width)}"/>'
        )
    return f'<g data-role="shield">{"".join(parts)}</g>'


def heart(cx: float, cy: float, size: float, *, fill: str) -> str:
    """Flat rounded heart — no gloss, no outline. ``size`` ≈ bounding width/height."""
    s = size
    d = (
        f"M {_f(cx)} {_f(cy - 0.15 * s)} "
        f"C {_f(cx - 0.05 * s)} {_f(cy - 0.32 * s)}, {_f(cx - 0.28 * s)} {_f(cy - 0.36 * s)}, "
        f"{_f(cx - 0.36 * s)} {_f(cy - 0.22 * s)} "
        f"C {_f(cx - 0.46 * s)} {_f(cy - 0.06 * s)}, {_f(cx - 0.30 * s)} {_f(cy + 0.12 * s)}, "
        f"{_f(cx)} {_f(cy + 0.34 * s)} "
        f"C {_f(cx + 0.30 * s)} {_f(cy + 0.12 * s)}, {_f(cx + 0.46 * s)} {_f(cy - 0.06 * s)}, "
        f"{_f(cx + 0.36 * s)} {_f(cy - 0.22 * s)} "
        f"C {_f(cx + 0.28 * s)} {_f(cy - 0.36 * s)}, {_f(cx + 0.05 * s)} {_f(cy - 0.32 * s)}, "
        f"{_f(cx)} {_f(cy - 0.15 * s)} Z"
    )
    return f'<path d="{d}" fill="{escape(fill, quote=True)}" data-role="heart"/>'


def _half_heart(cx: float, cy: float, s: float, *, side: Literal["left", "right"]) -> str:
    """One half of a heart, closed down the central seam — a cupped-hand silhouette."""
    sign = -1.0 if side == "left" else 1.0
    return (
        f"M {_f(cx)} {_f(cy - 0.15 * s)} "
        f"C {_f(cx + sign * 0.05 * s)} {_f(cy - 0.32 * s)}, "
        f"{_f(cx + sign * 0.28 * s)} {_f(cy - 0.36 * s)}, {_f(cx + sign * 0.36 * s)} {_f(cy - 0.22 * s)} "
        f"C {_f(cx + sign * 0.46 * s)} {_f(cy - 0.06 * s)}, "
        f"{_f(cx + sign * 0.30 * s)} {_f(cy + 0.12 * s)}, {_f(cx)} {_f(cy + 0.34 * s)} Z"
    )


# Pack-seed note: v1 uses an ENGINE-AUTHORED path composition (two half-hearts + sleeve cuffs)
# as a stand-in for the operator-approved organic trace. Replace with a CC0 / free-for-commercial
# vector-pack trace (record source URL + license here) once the license-verified pick is made
# (STYLE_PROFILES open decision #4). Signature does not change on the swap.
def hands_forming_heart(
    cx: float,
    cy: float,
    size: float,
    *,
    fill: str,
    sleeve_fill: str | None = None,
) -> str:
    """Two cupped dua hands whose inner contours form a heart-shaped opening."""
    s = size
    cuff = sleeve_fill or fill
    left_hand = (
        f"M {_f(cx - 0.03 * s)} {_f(cy + 0.30 * s)} "
        f"C {_f(cx - 0.18 * s)} {_f(cy + 0.22 * s)}, {_f(cx - 0.34 * s)} {_f(cy + 0.06 * s)}, "
        f"{_f(cx - 0.37 * s)} {_f(cy - 0.10 * s)} "
        f"C {_f(cx - 0.39 * s)} {_f(cy - 0.22 * s)}, {_f(cx - 0.31 * s)} {_f(cy - 0.28 * s)}, "
        f"{_f(cx - 0.25 * s)} {_f(cy - 0.20 * s)} "
        f"L {_f(cx - 0.18 * s)} {_f(cy - 0.02 * s)} "
        f"C {_f(cx - 0.14 * s)} {_f(cy + 0.05 * s)}, {_f(cx - 0.08 * s)} {_f(cy + 0.08 * s)}, "
        f"{_f(cx)} {_f(cy + 0.18 * s)} "
        f"C {_f(cx - 0.06 * s)} {_f(cy + 0.10 * s)}, {_f(cx - 0.10 * s)} {_f(cy + 0.02 * s)}, "
        f"{_f(cx - 0.09 * s)} {_f(cy - 0.08 * s)} "
        f"L {_f(cx - 0.08 * s)} {_f(cy - 0.30 * s)} "
        f"C {_f(cx - 0.08 * s)} {_f(cy - 0.38 * s)}, {_f(cx - 0.02 * s)} {_f(cy - 0.40 * s)}, "
        f"{_f(cx + 0.01 * s)} {_f(cy - 0.33 * s)} "
        f"L {_f(cx + 0.02 * s)} {_f(cy - 0.06 * s)} "
        f"C {_f(cx + 0.02 * s)} {_f(cy + 0.08 * s)}, {_f(cx - 0.01 * s)} {_f(cy + 0.20 * s)}, "
        f"{_f(cx - 0.03 * s)} {_f(cy + 0.30 * s)} Z"
    )
    # Mirror the left hand rather than maintaining two divergent silhouettes.
    right_transform = f"translate({_f(2 * cx)} 0) scale(-1 1)"
    left_cuff = (
        f"M {_f(cx - 0.31 * s)} {_f(cy + 0.20 * s)} "
        f"L {_f(cx - 0.04 * s)} {_f(cy + 0.31 * s)} "
        f"L {_f(cx - 0.10 * s)} {_f(cy + 0.48 * s)} "
        f"L {_f(cx - 0.39 * s)} {_f(cy + 0.35 * s)} Z"
    )
    return (
        '<g data-role="hands-heart" data-figure="true" data-faceless="true">'
        f'<path d="{left_cuff}" fill="{escape(cuff, quote=True)}"/>'
        f'<path d="{left_cuff}" fill="{escape(cuff, quote=True)}" transform="{right_transform}"/>'
        f'<path d="{left_hand}" fill="{escape(fill, quote=True)}"/>'
        f'<path d="{left_hand}" fill="{escape(fill, quote=True)}" transform="{right_transform}"/>'
        "</g>"
    )


def shield_crescent(
    cx: float,
    cy: float,
    size: float,
    *,
    fill: str,
    shield_fill: str,
    stroke: str,
) -> str:
    """A centred crescent fully contained within a soft heater shield."""
    shield_width = size * 0.72
    stroke_width = max(2.0, size * 0.012)
    moon_radius = size * 0.18
    return (
        '<g data-role="shield-crescent" data-figure="true" data-faceless="true">'
        f"{shield(cx, cy, shield_width, size, fill=shield_fill, stroke=stroke, stroke_width=stroke_width)}"
        f"{crescent(cx, cy - size * 0.06, moon_radius, fill=fill, rotation=-18)}"
        "</g>"
    )


def highlighted_word_box(
    word: str,
    *,
    x: float,
    y: float,
    font_size: float,
    box_fill: str,
    text_fill: str,
    font_family: str,
    pad_x_em: float = 0.45,
    pad_y_em: float = 0.22,
    rx: float = 14.0,
) -> tuple[str, float, float]:
    """The decisive deep-plum box with one uppercase key word reversed out in Cloud White.

    ``x``/``y`` are the box top-left. Returns ``(svg, box_width, box_height)`` measured with the
    same conservative 0.60×font glyph factor the glo2go/svg code uses, so callers can centre/flow it.
    """
    up = word.upper()
    box_w = len(up) * _HEAVY_GLYPH_FACTOR * font_size + 2 * pad_x_em * font_size
    box_h = font_size + 2 * pad_y_em * font_size
    svg = (
        '<g data-role="highlight-word">'
        f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(box_w)}" height="{_f(box_h)}" '
        f'rx="{_f(rx)}" fill="{escape(box_fill, quote=True)}"/>'
        f'<text x="{_f(x + box_w / 2)}" y="{_f(y + box_h / 2)}" fill="{escape(text_fill, quote=True)}" '
        f'font-family="{escape(font_family, quote=True)}" font-size="{_f(font_size)}" '
        f'font-weight="760" text-anchor="middle" dominant-baseline="central">'
        f"{escape(up)}</text>"
        "</g>"
    )
    return svg, box_w, box_h


# =============================================================================================
# v1 helpers (composition-level)
# =============================================================================================


def wordmark(
    cx: float,
    y: float,
    *,
    height: float,
    fill: str,
    font_family: str,
    logo_ref: str | None = None,
) -> str:
    """'simply nikāh' top-centre. Typographic until a logo asset (already-embedded data-URI or
    href string) is supplied via ``logo_ref``; then the logo image reverses in. ``y`` is the text
    baseline (the generic wordmark-baseline placement). Root ``<g data-role="wordmark">`` — the
    ONLY group where a raster ``<image>`` is modesty-approved.
    """
    if logo_ref:
        img_w = height * 5.0
        img_h = height * 1.15
        return (
            '<g data-role="wordmark">'
            f'<image x="{_f(cx - img_w / 2)}" y="{_f(y - img_h * 0.85)}" '
            f'width="{_f(img_w)}" height="{_f(img_h)}" preserveAspectRatio="xMidYMid meet" '
            f'href="{escape(logo_ref, quote=True)}"/>'
            "</g>"
        )
    return (
        '<g data-role="wordmark">'
        f'<text x="{_f(cx)}" y="{_f(y)}" fill="{escape(fill, quote=True)}" '
        f'font-family="{escape(font_family, quote=True)}" font-size="{_f(height)}" '
        f'font-weight="600" letter-spacing="0.01em" text-anchor="middle">simply nikāh</text>'
        "</g>"
    )


def cta_pill(
    cx: float,
    y: float,
    *,
    height: float,
    label: str,
    fill: str,
    text_fill: str,
    font_family: str,
) -> tuple[str, float]:
    """Rounded pill CTA centred on ``cx`` with its top at ``y``. Returns ``(svg, pill_width)``."""
    font_size = height * 0.40
    pad_x = height * 0.72
    pill_w = max(height * 2.2, len(label) * _HEAVY_GLYPH_FACTOR * font_size + 2 * pad_x)
    left = cx - pill_w / 2
    svg = (
        '<g data-role="cta">'
        f'<rect x="{_f(left)}" y="{_f(y)}" width="{_f(pill_w)}" height="{_f(height)}" '
        f'rx="{_f(height / 2)}" fill="{escape(fill, quote=True)}"/>'
        f'<text x="{_f(cx)}" y="{_f(y + height / 2)}" fill="{escape(text_fill, quote=True)}" '
        f'font-family="{escape(font_family, quote=True)}" font-size="{_f(font_size)}" '
        f'font-weight="700" text-anchor="middle" dominant-baseline="central">'
        f"{escape(label)}</text>"
        "</g>"
    )
    return svg, pill_w


def glow_ellipse(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    *,
    fill: str,
    opacity: float = 0.5,
) -> str:
    """Restrained blush radial glow behind a hero symbol.

    Done as a radial-gradient ellipse (NOT an SVG blur filter) so headless rasterizers agree on the
    pixels. The gradient id is derived from the centre so multiple glows stay unique in one doc.
    """
    grad_id = f"nk-glow-{int(round(cx))}-{int(round(cy))}"
    return (
        '<g data-role="glow">'
        "<defs>"
        f'<radialGradient id="{grad_id}" cx="50%" cy="50%" r="50%">'
        f'<stop offset="0%" stop-color="{escape(fill, quote=True)}" stop-opacity="{_f(opacity)}"/>'
        f'<stop offset="70%" stop-color="{escape(fill, quote=True)}" stop-opacity="{_f(opacity * 0.35)}"/>'
        f'<stop offset="100%" stop-color="{escape(fill, quote=True)}" stop-opacity="0"/>'
        "</radialGradient>"
        "</defs>"
        f'<ellipse cx="{_f(cx)}" cy="{_f(cy)}" rx="{_f(rx)}" ry="{_f(ry)}" fill="url(#{grad_id})"/>'
        "</g>"
    )


# =============================================================================================
# Deferred primitives — signatures reserved for archetypes 2/3/4/6. Do NOT build in v1.
# =============================================================================================


def mihrab_arch_frame(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    stroke: str,
    stroke_width: float = 6.0,
    style: Literal["line", "double"] = "line",
) -> str:
    """Pointed mihrab / ogee arch outline framing content. For the Mihrab/Lattice Frame archetype.

    Deferred (v1 ships only the Highlighted-Word and Protection-Symbol heroes).
    """
    raise NotImplementedError("mihrab_arch_frame is a deferred primitive (post-v1 archetype).")


def faceless_avatar_card(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    variant: Literal["hijabi", "beard", "plain"],
    card_fill: str,
    figure_fill: str,
    rx: float = 24.0,
) -> str:
    """Rounded card holding a bust-level faceless silhouette (hijab or beard outline, zero facial
    features). Would stamp ``data-figure``/``data-faceless``. For the Connected Match Cards archetype.

    Deferred (v1 ships only the Highlighted-Word and Protection-Symbol heroes).
    """
    raise NotImplementedError("faceless_avatar_card is a deferred primitive (post-v1 archetype).")


def connector_path(
    points,
    *,
    stroke: str,
    stroke_width: float = 4.0,
    dash: str | None = "2 10",
    dot_terminals: bool = True,
) -> str:
    """Gentle dashed connector line joining cards, dot at each end. For Connected Match Cards.

    Deferred (v1 ships only the Highlighted-Word and Protection-Symbol heroes).
    """
    raise NotImplementedError("connector_path is a deferred primitive (post-v1 archetype).")


def calligraphy_panel_frame(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    stroke: str,
    fill: str,
    rx: float = 28.0,
) -> str:
    """Ornamented panel frame that HOSTS supplied calligraphy artwork — the frame is engine vector;
    the ayah calligraphy itself is an approved asset, never engine-drawn. For Ayah & Translation.

    Deferred (v1 ships only the Highlighted-Word and Protection-Symbol heroes).
    """
    raise NotImplementedError(
        "calligraphy_panel_frame is a deferred primitive (post-v1 archetype)."
    )


def lantern(cx: float, cy: float, h: float, *, fill: str, glow: bool = False) -> str:
    """Flat Ramadan / fanous lantern silhouette (pack-seeded path). For seasonal/Eid content.

    Deferred (v1 ships only the Highlighted-Word and Protection-Symbol heroes).
    """
    raise NotImplementedError("lantern is a deferred primitive (post-v1 archetype).")


def phone_mockup(
    cx: float,
    cy: float,
    h: float,
    *,
    frame_fill: str,
    screen_fill: str,
    screen_content_svg: str = "",
) -> str:
    """Flat rounded phone frame with an injectable screen-content slot. For Phone-and-Hijabi.

    Deferred (v1 ships only the Highlighted-Word and Protection-Symbol heroes).
    """
    raise NotImplementedError("phone_mockup is a deferred primitive (post-v1 archetype).")
