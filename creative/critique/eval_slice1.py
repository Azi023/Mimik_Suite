"""Slice-1 eval harness — render real creatives, run the critic, PRINT the scores.

Renders the two rejected Simply Nikah v1 archetypes (blob hands-heart / glitchy
shield-crescent) plus a clean control (single-glyph crescent), scores each with
`run_critique`, and prints the per-axis result. Advisory-only — nothing here gates.

The EXIT TEST (DESIGN_CRITIC_SPEC.md §6 calibration gate) is asserted in
`tests/test_critique.py`; this script is the operator-facing readout. Run:

    uv run python -m creative.critique.eval_slice1
"""

from __future__ import annotations

import asyncio

from mimik_contracts import Brand, BrandTokens, ColorRole

from creative.critique import run_critique
from creative.critique.report import CritiqueReport
from creative.render.nikah_templates import render_nikah
from creative.style_profile import get_style_profile


def simply_nikah_brand() -> Brand:
    """Build the Simply Nikah Brand from its locked style-profile palette (the A1 tokens)."""
    profile = get_style_profile("simply-nikah")
    colors = [
        ColorRole(name=f"{c.role}:{c.name}", hex=c.hex, usage=c.role)
        for c in profile.palette
        if c.hex
    ]
    return Brand(
        tenant_id="eval-tenant",
        client_id="simply-nikah",
        name="Simply Nikah",
        slug="simply-nikah",
        tokens=BrandTokens(colors=colors),
    )


async def _render_fixtures() -> list[tuple[str, bytes]]:
    """(label, png_bytes) for the two SN v1 archetypes + a clean single-glyph control."""
    v1_hero = await render_nikah(
        "highlighted_word_hero",
        copy={
            "headline": "Built on the RIGHT INTENTION",
            "highlight": "RIGHT INTENTION",
            "sub": "A marriage-first platform for practising Muslims.",
            "cta": "Start your search",
        },
        format_key="carousel",
        hero_symbol="hands_heart",
    )
    v1_protect = await render_nikah(
        "protection_symbol_hero",
        copy={
            "headline": "Your trust, protected from the first hello",
            "sub": "Guardians involved, privacy respected, intentions clear.",
            "cta": "Learn more",
        },
        format_key="carousel",
        hero_symbol="shield_crescent",
    )
    clean = await render_nikah(
        "protection_symbol_hero",
        copy={
            "headline": "One clear crescent, one clear intention",
            "sub": "A calm, recognisable mark — nothing broken, nothing to squint at.",
            "cta": "Learn more",
        },
        format_key="carousel",
        hero_symbol="crescent",
    )
    return [
        ("SN v1 — highlighted_word_hero (hands_heart blob)", v1_hero),
        ("SN v1 — protection_symbol_hero (shield_crescent glitch)", v1_protect),
        ("SN clean control — protection_symbol_hero (single-glyph crescent)", clean),
    ]


def _print_report(label: str, report: CritiqueReport) -> None:
    print(f"\n=== {label} ===")
    print(report.summary)
    for axis in report.axes:
        shown = "unknown" if axis.score is None else f"{axis.score}/5"
        print(f"  [{axis.axis}] {axis.name}: {shown}  (anchor: {axis.anchor})")
        for finding in axis.findings:
            print(f"      - {finding}")


async def main() -> None:
    brand = simply_nikah_brand()
    print("Simply Nikah palette (A1 tokens):", [c.hex for c in brand.tokens.colors])
    for label, png in await _render_fixtures():
        report = run_critique(png, brand=brand)
        _print_report(label, report)


if __name__ == "__main__":
    asyncio.run(main())
