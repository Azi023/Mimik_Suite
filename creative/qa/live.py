"""Live-path brand-QA gate.

`run_brand_qa` (checks.py) is bound to the OLD template registry (`get_template().geometry`)
and only works for registry templates driven by a `TemplateContext`. The LIVE generation path
(`api/services/creative_generation._render_creative_artifacts`) does NOT use that registry: it
renders a semantic SVG (`creative.export.svg.render_creative_svg`) with named, bbox-carrying
layers (`<g id="layer-headline" data-bbox="x y w h">`, `layer-badge`, ...) plus a raster
preview. This module gates that ACTUAL rendered output.

It reuses the checks.py / contrast.py primitives wholesale — luminance/ratio/png math, the
safe-zone overflow helper, the logo-luminance sampler, and the browser gate — so there is one
source of truth for the WCAG math. What is new here is the geometry source: named-layer bboxes
parsed from the emitted SVG instead of `TemplateGeometry` from the registry.
"""

from __future__ import annotations

import base64
import logging
import struct
from xml.etree import ElementTree

from creative.qa.checks import (
    HEADLINE_MIN_RATIO,
    LOGO_MIN_RATIO,
    QAReport,
    _safe_zone_overflows,
)
from creative.qa.contrast import (
    logo_mean_luminance,
    luminance_ratio,
    relative_luminance,
    sampled_zone_luminance,
)
from creative.render.compositor import browser_available, png_size
from creative.render.templates import ZoneRect
from creative.style_profile import ImageSource, StyleProfile
from mimik_contracts import Brand, get_format

logger = logging.getLogger(__name__)

# Flip to True to turn the recorded gate into a HARD gate: a failing live-QA report then raises
# LiveQABlocked out of the generation path instead of only logging a WARNING. Left False so the
# operator keeps assisted-autonomy (record + human review) until they choose to escalate.
LIVE_QA_BLOCKING = False

# Real-photography source kinds. The modesty/source guard only fires for these — a solid
# `brand_placeholder` or a vector source is never "real photography of people".
_REAL_PHOTO_SOURCES = frozenset(
    {
        ImageSource.LICENSED_STOCK.value,
        ImageSource.AI_REALISTIC.value,
        ImageSource.PRODUCT_CUTOUT.value,
    }
)

_SVG_NS = "http://www.w3.org/2000/svg"

# Which named SVG layers are text (headline/subhead/cta) vs the logo-bearing layer (badge).
_TEXT_LAYER_IDS = ("layer-headline", "layer-subhead", "layer-cta")
_LOGO_LAYER_ID = "layer-badge"
_HEADLINE_LAYER_ID = "layer-headline"


class LiveQABlocked(RuntimeError):
    """Raised out of the generation path only when LIVE_QA_BLOCKING is True and QA failed."""

    def __init__(self, report: QAReport) -> None:
        super().__init__("; ".join(report.failures) or "live brand-QA failed")
        self.report = report


def _svg_tag(local_name: str) -> str:
    return f"{{{_SVG_NS}}}{local_name}"


def _parse_layers(svg: str) -> dict[str, ElementTree.Element]:
    """Map every `<g id="layer-...">` element by its id.

    The SVG is our own machine-generated output from `render_creative_svg` (never external
    XML), and client freeform copy reaches it only as escaped element text — no DOCTYPE/entity
    can be injected, so there is no XXE surface. Uses stdlib ElementTree to match the existing
    parse path in `creative.export.svg` / `creative.export.psd`.
    """
    root = ElementTree.fromstring(svg)
    layers: dict[str, ElementTree.Element] = {}
    for group in root.iter(_svg_tag("g")):
        layer_id = group.get("id")
        if layer_id and layer_id.startswith("layer-"):
            layers[layer_id] = group
    return layers


def _layer_bbox(layer: ElementTree.Element) -> ZoneRect | None:
    """Parse the `data-bbox="x y w h"` a layer carries into a ZoneRect (None if absent/empty)."""
    raw = layer.get("data-bbox")
    if not raw:
        return None
    parts = raw.split()
    if len(parts) != 4:
        return None
    x, y, w, h = (int(round(float(value))) for value in parts)
    if w <= 0 or h <= 0:
        return None
    return ZoneRect(x=x, y=y, w=w, h=h)


def _first_attr(layer: ElementTree.Element, local_name: str, attr: str) -> str | None:
    tag = _svg_tag(local_name)
    for element in layer.iter(tag):
        value = element.get(attr)
        if value:
            return value
    return None


def _headline_fill(layer: ElementTree.Element) -> str | None:
    """The fill the headline actually rendered with (the ink color on <text>/<tspan>)."""
    for local_name in ("text", "tspan"):
        fill = _first_attr(layer, local_name, "fill")
        if fill and fill.startswith("#"):
            return fill
    return None


async def _png_zone_mean_luminance(
    preview_png: bytes, zone: ZoneRect, viewport: tuple[int, int]
) -> float:
    """Mean WCAG relative luminance of the rendered preview under a zone bbox.

    Reuses `sampled_zone_luminance` (browser crop + canvas decode) by handing it the preview
    PNG as a full-canvas <img>, so there is no second luminance/decode implementation. The
    preview is the shipped raster, so this samples what actually ships (text baked in — see the
    module note: a clean text-hidden ground would need an SVG re-render the live path skips).
    """
    data_uri = "data:image/png;base64," + base64.b64encode(preview_png).decode("ascii")
    width, height = viewport
    html = (
        f'<img src="{data_uri}" '
        f'style="display:block;width:{width}px;height:{height}px" />'
    )
    # hide_css must match nothing in this doc — the <img> has no text to hide.
    return await sampled_zone_luminance(html, zone, viewport, hide_css="script")


async def run_live_qa(
    preview_png: bytes,
    svg: str,
    *,
    brand: Brand,
    profile: StyleProfile | None,
    format_key: str,
    source_kind: str,
    expect_logo: bool,
) -> QAReport:
    """Brand-QA gate for the LIVE render path (semantic SVG + raster preview).

    Checks: exact dims, named-layer safe zones, headline contrast (sampled), logo visibility
    (the Glo2Go purple-on-purple lesson), and code-checkable profile guardrails.
    """
    failures: list[str] = []
    needs_scrim = False

    fmt = get_format(format_key)
    layers = _parse_layers(svg)

    # 1. Dims: the raster must match the requested format exactly. A preview that is not even a
    #    decodable PNG is itself a QA failure — record it, never let it crash generation (the
    #    gate is recorded, not fatal, unless the operator flips LIVE_QA_BLOCKING).
    try:
        actual = png_size(preview_png)
    except (ValueError, IndexError, struct.error):
        actual = None
        failures.append("dims: preview is not a decodable PNG")
    if actual is not None and actual != (fmt.width, fmt.height):
        failures.append(
            f"dims: expected {fmt.width}x{fmt.height}, got {actual[0]}x{actual[1]}"
        )

    # 2. Safe zones: every text + logo layer bbox fully inside the format's safe area.
    for layer_id in (*_TEXT_LAYER_IDS, _LOGO_LAYER_ID):
        layer = layers.get(layer_id)
        if layer is None:
            continue
        zone = _layer_bbox(layer)
        if zone is None:
            continue
        overflows = _safe_zone_overflows(zone, format_key)
        if overflows:
            name = layer_id.removeprefix("layer-")
            failures.append(
                f"safe_zone: {name} breaches safe area ({', '.join(overflows)})"
            )

    # 3. Headline contrast: sample the preview under the headline bbox, compare to the ink the
    #    headline actually rendered with. Browser-gated exactly like checks.py's imagery path.
    headline_layer = layers.get(_HEADLINE_LAYER_ID)
    if headline_layer is not None and actual is not None and browser_available():
        headline_zone = _layer_bbox(headline_layer)
        ink_hex = _headline_fill(headline_layer)
        if headline_zone is not None and ink_hex is not None:
            ground_lum = await _png_zone_mean_luminance(
                preview_png, headline_zone, (fmt.width, fmt.height)
            )
            ratio = luminance_ratio(relative_luminance(ink_hex), ground_lum)
            if ratio < HEADLINE_MIN_RATIO:
                failures.append(
                    f"contrast: headline {ink_hex} on rendered ground = {ratio:.2f} "
                    f"< {HEADLINE_MIN_RATIO} — re-render with a scrim/darker ground"
                )
                needs_scrim = True

    # 4. Logo visibility (the Glo2Go dogfood lesson: a purple mark on the purple badge ground
    #    renders invisible while every text check passes). The SVG embeds the logo as a data
    #    URI, so logo_mean_luminance can sample it; the badge <rect> fill is the true ground.
    if expect_logo:
        logo_layer = layers.get(_LOGO_LAYER_ID)
        logo_href = (
            _first_attr(logo_layer, "image", "href") if logo_layer is not None else None
        )
        if logo_href is None:
            failures.append(
                "logo: brand has a logo but the creative rendered no logo image"
            )
        elif browser_available():
            logo_lum = await logo_mean_luminance(logo_href)
            ground_hex = _first_attr(logo_layer, "rect", "fill")
            if logo_lum is not None and ground_hex is not None and ground_hex.startswith("#"):
                ground_lum = relative_luminance(ground_hex)
                logo_ratio = luminance_ratio(logo_lum, ground_lum)
                if logo_ratio < LOGO_MIN_RATIO:
                    failures.append(
                        f"logo: mark-vs-ground contrast = {logo_ratio:.2f} < {LOGO_MIN_RATIO} "
                        "— use a knockout/light logo variant or a lighter badge ground"
                    )

    # 5. Profile guardrails (code-checkable subset).
    if profile is not None:
        failures.extend(_source_guardrail_failures(profile, source_kind))
        # TODO(palette): palette-adherence — sample the rendered creative's dominant hues and
        # assert they stay inside profile.palette. Skipped for now (needs a color-quantize pass).

    return QAReport(passed=not failures, failures=failures, needs_scrim=needs_scrim)


def _source_guardrail_failures(profile: StyleProfile, source_kind: str) -> list[str]:
    """Modesty/source guard: a real-photo source disallowed by the profile is a hard fail.

    Generic across profiles via `profile.image_sources`; Simply Nikah is the load-bearing case
    (forbids real photography of people). A `brand_placeholder`/unknown kind is never a photo of
    a person, so it never trips this guard.
    """
    if source_kind not in _REAL_PHOTO_SOURCES:
        return []
    allowed = {source.value for source in profile.image_sources}
    if source_kind in allowed:
        return []
    if profile.id == "simply-nikah":
        return [
            f"source: Simply Nikah forbids real photography of people; source must be "
            f"generated_vector or ai_illustration (got {source_kind})"
        ]
    allowed_list = ", ".join(sorted(allowed)) or "(none)"
    return [
        f"source: {profile.client} forbids image source {source_kind}; "
        f"allowed sources: {allowed_list}"
    ]
