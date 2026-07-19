"""Brand-derived color math: tints and shades computed FROM the client's palette.

The rule this module exists to enforce (a real client-feedback lesson): a client creative
never borrows another brand's colors. When a palette needs an extra role (an accent chip,
a soft ground, a wave shape), it is DERIVED from the client's own primary — never pulled
from a house default.

Same math is used by the templates (render) and the contrast semantics (QA), so what QA
computes is exactly what renders.
"""

from __future__ import annotations


def _split(hex_color: str) -> tuple[int, int, int]:
    raw = hex_color.lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def mix(hex_a: str, hex_b: str, t: float) -> str:
    """Linear sRGB mix of two hex colors; t=0 -> a, t=1 -> b. t clamped into [0, 1]."""
    t = min(1.0, max(0.0, t))
    ra, ga, ba = _split(hex_a)
    rb, gb, bb = _split(hex_b)
    return "#{:02X}{:02X}{:02X}".format(
        round(ra + (rb - ra) * t), round(ga + (gb - ga) * t), round(ba + (bb - ba) * t)
    )


def tint(hex_color: str, t: float) -> str:
    """Mix toward white: tint('#642766', 0.9) is the pale wash of that purple."""
    return mix(hex_color, "#FFFFFF", t)


def shade(hex_color: str, t: float) -> str:
    """Mix toward black: shade('#642766', 0.2) is the deep version of that purple."""
    return mix(hex_color, "#000000", t)
