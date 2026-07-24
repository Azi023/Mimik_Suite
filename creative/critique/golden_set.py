"""Small in-repo golden set for Slice-2 calibration.

The long-term golden set belongs in mimik-knowledge. This deliberately small harness keeps
the two operator-rejected v1 renders and one clean control executable in this repository,
with expected verdicts stored as data. Vision replies are fixed calibration observations,
so regression tests stay deterministic and the separate live-vision exit test remains
gracefully skipped without GEMINI_API_KEY.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from mimik_contracts import Brand
from pydantic import BaseModel

from creative.render.nikah_templates import render_nikah

from .calibration import CalibrationItem
from .critic import run_critique


class GoldenAnchor(BaseModel):
    name: str
    expected_verdict: Literal["PASS", "FAIL"]
    render_kwargs: dict[str, Any]
    vision_reply: str
    note: str


GOLDEN_ANCHORS = (
    GoldenAnchor(
        name="simply-nikah-clean-crescent",
        expected_verdict="PASS",
        render_kwargs={
            "archetype": "protection_symbol_hero",
            "copy": {
                "headline": "One clear intention",
                "sub": "Simple, calm and recognisable.",
                "cta": "Learn more",
            },
            "format_key": "carousel",
            "hero_symbol": "crescent",
        },
        vision_reply=(
            '{"symbols":[{"name":"crescent moon","verdict":"instant",'
            '"reason":"single clear silhouette"}],"overall":"clean"}'
        ),
        note="Clean simple creative: one recognisable motif and an uncluttered message.",
    ),
    GoldenAnchor(
        name="simply-nikah-v1-highlighted-word-hero",
        expected_verdict="FAIL",
        render_kwargs={
            "archetype": "highlighted_word_hero",
            "copy": {
                "headline": "Built on the RIGHT INTENTION",
                "highlight": "RIGHT INTENTION",
                "sub": "...",
                "cta": "Start your search",
            },
            "format_key": "carousel",
            "hero_symbol": "hands_heart",
        },
        vision_reply=(
            '{"symbols":[{"name":"unnameable hands-heart blob",'
            '"verdict":"unrecognizable","reason":"parts do not fuse into one object"}],'
            '"overall":"fails F3 naming test"}'
        ),
        note="Operator-rejected v1: F3 meaningless iconography.",
    ),
    GoldenAnchor(
        name="simply-nikah-v1-protection-symbol-hero",
        expected_verdict="FAIL",
        render_kwargs={
            "archetype": "protection_symbol_hero",
            "copy": {
                "headline": "Your trust, protected from the first hello",
                "sub": "...",
                "cta": "Learn more",
            },
            "format_key": "carousel",
            "hero_symbol": "shield_crescent",
        },
        vision_reply=(
            '{"symbols":[{"name":"shield and crescent","verdict":"glitch",'
            '"reason":"overlapping parts read as a broken composite"}],'
            '"overall":"fails F2 integrity test"}'
        ),
        note="Operator-rejected v1: F2 broken symbol composition.",
    ),
)

BOLD_BUT_GOOD_TRIPWIRE_NOTES = (
    "Bold-but-good tripwire: unconventional scale or asymmetry is not a failure by itself; "
    "reject only a named side effect such as illegibility, guardrail breach, or hierarchy collapse.",
)


async def evaluate_golden_set(
    *,
    brand: Brand,
    renderer: Callable[..., Awaitable[bytes]] = render_nikah,
) -> list[CalibrationItem]:
    """Render and deterministically critique every stored anchor.

    `renderer` defaults to the real Simply Nikah rasterizer. Tests may inject a stable PNG
    renderer when Chromium is unavailable; the exact production render calls remain stored
    in `GOLDEN_ANCHORS` and are exercised by the live exit test on a browser-capable host.
    """
    evaluations: list[CalibrationItem] = []
    for anchor in GOLDEN_ANCHORS:
        png = await renderer(**anchor.render_kwargs)

        def fixed_vision(_prompt: str, reply: str = anchor.vision_reply) -> str:
            return reply

        report = run_critique(png, brand=brand, vision_generate=fixed_vision)
        evaluations.append(
            CalibrationItem(
                name=anchor.name,
                expected_verdict=anchor.expected_verdict,
                report=report,
            )
        )
    return evaluations
