"""Golden-set calibration and rejection-evidence regression tests."""

from __future__ import annotations

import asyncio
import struct
import zlib

import numpy as np

from creative.critique import CRITIC_PASS_THRESHOLD
from creative.critique.calibration import calibrate_threshold
from creative.critique.eval_slice1 import simply_nikah_brand
from creative.critique.golden_set import (
    BOLD_BUT_GOOD_TRIPWIRE_NOTES,
    GOLDEN_ANCHORS,
    evaluate_golden_set,
)


def _on_brand_png() -> bytes:
    arr = np.zeros((16, 16, 4), dtype=np.uint8)
    arr[:, :, :] = (253, 98, 173, 255)
    raw = b"".join(b"\x00" + row.tobytes() for row in arr)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + b"\x00\x00\x00\x00"
        )

    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


async def _stable_renderer(**_kwargs: object) -> bytes:
    return _on_brand_png()


def test_golden_set_calibrates_provisional_threshold() -> None:
    evaluations = asyncio.run(
        evaluate_golden_set(brand=simply_nikah_brand(), renderer=_stable_renderer)
    )

    result = calibrate_threshold(evaluations, preferred_threshold=CRITIC_PASS_THRESHOLD)

    assert result.passed is True
    assert result.threshold == CRITIC_PASS_THRESHOLD == 3.8
    assert result.rank_ordered is True
    assert [item.expected_verdict for item in evaluations].count("PASS") >= 1
    assert [item.expected_verdict for item in evaluations].count("FAIL") == 2
    assert all(
        item.report.passed_at(result.threshold) == (item.expected_verdict == "PASS")
        for item in evaluations
    )


def test_golden_set_records_exact_v1_failures_and_bold_tripwire() -> None:
    by_name = {anchor.name: anchor for anchor in GOLDEN_ANCHORS}

    highlighted = by_name["simply-nikah-v1-highlighted-word-hero"]
    protected = by_name["simply-nikah-v1-protection-symbol-hero"]

    assert highlighted.render_kwargs["archetype"] == "highlighted_word_hero"
    assert highlighted.render_kwargs["hero_symbol"] == "hands_heart"
    assert highlighted.render_kwargs["copy"] == {
        "headline": "Built on the RIGHT INTENTION",
        "highlight": "RIGHT INTENTION",
        "sub": "...",
        "cta": "Start your search",
    }
    assert protected.render_kwargs["archetype"] == "protection_symbol_hero"
    assert protected.render_kwargs["hero_symbol"] == "shield_crescent"
    assert protected.render_kwargs["copy"] == {
        "headline": "Your trust, protected from the first hello",
        "sub": "...",
        "cta": "Learn more",
    }
    assert BOLD_BUT_GOOD_TRIPWIRE_NOTES
    assert "bold" in BOLD_BUT_GOOD_TRIPWIRE_NOTES[0].casefold()


def test_every_failing_golden_axis_names_element_axis_and_anchor() -> None:
    evaluations = asyncio.run(
        evaluate_golden_set(brand=simply_nikah_brand(), renderer=_stable_renderer)
    )

    for evaluation in evaluations:
        if evaluation.expected_verdict != "FAIL":
            continue
        failing_axes = [
            axis for axis in evaluation.report.axes if axis.score is not None and axis.score <= 2
        ]
        assert failing_axes
        for axis in failing_axes:
            assert axis.axis
            assert axis.observations
            assert axis.rejection_element
            assert axis.anchor
