"""Slice-1 design-critic tests: A1 (deterministic) + A5 (vision) + the exit-test gate.

Fast/deterministic tests always run (synthetic PNGs for A1, injected replies for A5). The
EXIT TEST renders the real SN v1 pair and hits the live vision backend — it is skipped when
GEMINI_API_KEY is unset (advisory degradation is covered by a deterministic test instead).
"""

from __future__ import annotations

import os
import struct
import zlib

import numpy as np
import pytest

from creative.critique import critique_a1, critique_a5, run_critique
from creative.critique.eval_slice1 import _render_fixtures, simply_nikah_brand

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _encode_png_rgba(arr: np.ndarray) -> bytes:
    """Minimal non-interlaced 8-bit RGBA PNG (filter 0, zero CRC — the repo decoder ignores CRC)."""
    h, w = arr.shape[:2]
    raw = bytearray()
    for row in arr:
        raw.append(0)  # filter type: none
        raw.extend(row.astype(np.uint8).tobytes())
    idat = zlib.compress(bytes(raw))

    def chunk(typ: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + typ + data + b"\x00\x00\x00\x00"

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return _PNG_SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _solid(hex_color: str, size: int = 64) -> np.ndarray:
    raw = hex_color.lstrip("#")
    r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3] = r, g, b, 255
    return arr


# ---------------------------------------------------------------------------------------
# A1 — deterministic brand-token-diff
# ---------------------------------------------------------------------------------------
def test_a1_on_brand_color_scores_high() -> None:
    palette = ["#FD62AD", "#2B0A2E", "#FAF7FB"]  # SN primary / ink / ground
    png = _encode_png_rgba(_solid("#FD62AD"))
    axis = critique_a1(png, palette)
    assert axis.objective is True
    assert axis.score == 5
    assert axis.hard_fail is False


def test_a1_off_palette_hard_fails() -> None:
    palette = ["#FD62AD", "#2B0A2E", "#FAF7FB"]
    png = _encode_png_rgba(_solid("#00FF00"))  # pure green — far from every SN token
    axis = critique_a1(png, palette)
    assert axis.score == 1
    assert axis.hard_fail is True
    assert any("off-palette" in f for f in axis.findings)


def test_a1_empty_palette_is_unknown_not_crash() -> None:
    axis = critique_a1(_encode_png_rgba(_solid("#FD62AD")), [])
    assert axis.score is None
    assert axis.objective is True


# ---------------------------------------------------------------------------------------
# A5 — vision iconography scoring (injected replies, no network)
# ---------------------------------------------------------------------------------------
def _fake_vision(reply: str):
    def gen(_prompt: str) -> str:
        return reply
    return gen


def test_a5_glitch_symbol_hard_fails() -> None:
    reply = (
        '{"symbols": [{"name": "shield with crescent", "verdict": "glitch",'
        ' "reason": "parts do not resolve"}], "overall": "broken mark"}'
    )
    axis = critique_a5(b"", generate=_fake_vision(reply))
    assert axis.score == 1
    assert axis.hard_fail is True
    assert any("glitch" in f for f in axis.findings)


def test_a5_blob_fails_naming_test() -> None:
    reply = '{"symbols": [{"name": "unnameable blob", "verdict": "unrecognizable"}], "overall": "x"}'
    axis = critique_a5(b"", generate=_fake_vision(reply))
    assert axis.score == 1
    assert axis.hard_fail is False


def test_a5_clean_symbol_scores_high() -> None:
    reply = '{"symbols": [{"name": "a crescent moon", "verdict": "instant"}], "overall": "clean"}'
    axis = critique_a5(b"", generate=_fake_vision(reply))
    assert axis.score == 5


def test_a5_missing_backend_degrades_to_unknown() -> None:
    def boom(_prompt: str) -> str:
        raise RuntimeError("GEMINI_API_KEY is not set")

    axis = critique_a5(b"", generate=boom)
    assert axis.score is None  # degraded, not crashed
    assert axis.objective is False


# ---------------------------------------------------------------------------------------
# EXIT TEST — the spec's Slice-1 calibration gate (live vision; gated on the key)
# ---------------------------------------------------------------------------------------
@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="EXIT TEST needs a live vision backend (GEMINI_API_KEY)",
)
def test_exit_gate_v1_pair_fails_a5_clean_control_higher() -> None:
    import asyncio

    brand = simply_nikah_brand()
    fixtures = asyncio.run(_render_fixtures())
    labels = [f[0] for f in fixtures]
    reports = [run_critique(png, brand=brand) for _, png in fixtures]

    a5_scores = [r.axis("A5").score for r in reports]
    v1_hero_a5, v1_protect_a5, clean_a5 = a5_scores

    # The offender the model actually sees in each broken render (the hands_heart reads as a
    # broken heart/shape composite, never as "hands" — that failure to recognise IS the point).
    offender_keywords = [
        {"heart", "shape", "oval", "blob", "hand", "fuse"},  # hands_heart blob
        {"shield", "crescent", "glitch", "moon"},  # shield_crescent glitch
    ]

    # Both v1 renders must FAIL A5 (score 1) with the offending symbol named in findings.
    for label, report, keywords in zip(labels[:2], reports[:2], offender_keywords, strict=True):
        axis = report.axis("A5")
        assert axis.score == 1, f"{label} should FAIL A5, got {axis.score}: {axis.findings}"
        text = " ".join(axis.findings).lower()
        assert any(k in text for k in keywords), f"{label} A5 did not name the offender: {axis.findings}"

    # The clean single-glyph control must score strictly higher than either broken render.
    assert clean_a5 is not None
    assert clean_a5 > v1_hero_a5 and clean_a5 > v1_protect_a5
