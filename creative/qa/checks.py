"""Brand-QA hard checks (rubric v1, code half): exact dims, safe zones, logo presence,
WCAG contrast. Any fail routes the creative back to auto-fix/regeneration, never to a human.

The scrim is CONDITIONAL: only when the contrast check flags a text zone OVER IMAGERY does
the report raise needs_scrim — the pipeline then re-renders with ctx.scrim=True and re-checks.
A bad solid-ground pairing is a plain failure (no scrim fixes brand-color-on-brand-color).
"""

from __future__ import annotations

from pydantic import BaseModel

from creative.qa.contrast import (
    contrast_ratio,
    cta_colors,
    headline_colors,
    logo_ground,
    logo_mean_luminance,
    luminance_ratio,
    relative_luminance,
    sampled_zone_luminance,
    zone_contrast_over_imagery,
)
from creative.render.compositor import browser_available, png_size
from creative.render.templates import TemplateContext, ZoneRect, get_template
from mimik_contracts import get_format

# WCAG 2.x AA thresholds: headline renders at large-text sizes; the CTA label is body-scale.
HEADLINE_MIN_RATIO = 3.0
CTA_MIN_RATIO = 4.5
# WCAG 1.4.11 non-text contrast — below this a mark visually dissolves into its ground.
LOGO_MIN_RATIO = 3.0


class QAReport(BaseModel):
    passed: bool
    failures: list[str]  # human-readable "check: detail" strings
    needs_scrim: bool = False


def _safe_zone_overflows(zone: ZoneRect, format_key: str) -> list[str]:
    """How far a zone breaches the format's safe area, per edge (empty = fully inside)."""
    fmt = get_format(format_key)
    sz = fmt.safe_zone
    overflows: list[str] = []
    if zone.x < sz.left:
        overflows.append(f"left by {sz.left - zone.x}px")
    if zone.y < sz.top:
        overflows.append(f"top by {sz.top - zone.y}px")
    if zone.x + zone.w > fmt.width - sz.right:
        overflows.append(f"right by {zone.x + zone.w - (fmt.width - sz.right)}px")
    if zone.y + zone.h > fmt.height - sz.bottom:
        overflows.append(f"bottom by {zone.y + zone.h - (fmt.height - sz.bottom)}px")
    return overflows


async def run_brand_qa(
    png: bytes, ctx: TemplateContext, template_key: str, *, expect_logo: bool
) -> QAReport:
    """Run the code-side brand-QA gate on one rendered creative. No network: imagery paths
    re-render the template locally (data-URI assets) to sample the pixels under the text."""
    failures: list[str] = []
    needs_scrim = False
    template = get_template(template_key)
    geo = template.geometry(ctx)

    # 1. Dims: the raster must match the requested format exactly (rubric #6).
    actual = png_size(png)
    expected = ctx.size()
    if actual != expected:
        failures.append(
            f"dims: expected {expected[0]}x{expected[1]}, got {actual[0]}x{actual[1]}"
        )

    # 2. Safe zones: every text/logo zone fully inside the format's safe area (rubric #4).
    named_zones = [(f"text[{i}]", z) for i, z in enumerate(geo.text_zones)]
    if geo.logo_zone is not None:
        named_zones.append(("logo", geo.logo_zone))
    for name, zone in named_zones:
        overflows = _safe_zone_overflows(zone, ctx.format_key)
        if overflows:
            failures.append(f"safe_zone: {name} breaches safe area ({', '.join(overflows)})")

    # 3. Logo presence (rubric #1).
    if expect_logo:
        if ctx.logo_ref is None:
            failures.append("logo: brand has a logo but the creative doesn't reference it")
        elif geo.logo_zone is None:
            failures.append("logo: template placed no logo zone despite a logo_ref")

    # 4. Logo visibility (the Glo2Go dogfood lesson: a purple mark on the purple hero
    #    ground renders invisible while every text check passes). Pixel-honest: mean
    #    luminance of the mark's OPAQUE pixels vs its actual ground. Data-URI logos only
    #    (no network in QA) and browser-gated like every sampling path — the real pipeline
    #    always has the browser (it just rendered the PNG).
    if ctx.logo_ref is not None and geo.logo_zone is not None and browser_available():
        logo_lum = await logo_mean_luminance(ctx.logo_ref)
        if logo_lum is not None:
            if geo.text_over_imagery:
                ground_lum = await sampled_zone_luminance(
                    template.render(ctx), geo.logo_zone, ctx.size(), hide_css="h1,p,span,img"
                )
            else:
                ground_lum = relative_luminance(logo_ground(template_key, ctx))
            logo_ratio = luminance_ratio(logo_lum, ground_lum)
            if logo_ratio < LOGO_MIN_RATIO:
                failures.append(
                    f"logo: mark-vs-ground contrast = {logo_ratio:.2f} < {LOGO_MIN_RATIO} "
                    "— use a knockout/light logo variant or a lighter ground"
                )

    # 5. Contrast (rubric #3). Headline vs its ground; CTA label vs its own chip.
    text_hex, ground_hex = headline_colors(template_key, ctx)  # KeyError = unmapped template
    headline_zone = geo.text_zones[0]
    if geo.text_over_imagery:
        ratio = await zone_contrast_over_imagery(
            template.render(ctx), headline_zone, ctx.size(), text_hex
        )
        if ratio < HEADLINE_MIN_RATIO:
            failures.append(
                f"contrast: headline {text_hex} over imagery = {ratio:.2f} "
                f"< {HEADLINE_MIN_RATIO} — re-render with scrim"
            )
            needs_scrim = True
    else:
        ratio = contrast_ratio(text_hex, ground_hex)
        if ratio < HEADLINE_MIN_RATIO:
            failures.append(
                f"contrast: headline {text_hex} on solid {ground_hex} = {ratio:.2f} "
                f"< {HEADLINE_MIN_RATIO} — scrim won't fix a solid-ground pairing"
            )
    if ctx.cta:
        label_hex, chip_hex = cta_colors(ctx, template_key)
        cta_ratio = contrast_ratio(label_hex, chip_hex)
        if cta_ratio < CTA_MIN_RATIO:
            failures.append(
                f"contrast: CTA label {label_hex} on chip {chip_hex} = {cta_ratio:.2f} "
                f"< {CTA_MIN_RATIO}"
            )

    return QAReport(passed=not failures, failures=failures, needs_scrim=needs_scrim)
