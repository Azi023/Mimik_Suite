"""Design critic orchestrator — Slice 1 (A1 + A5, advisory-only).

`run_critique` scores a rendered PNG on the two Slice-1 axes and returns a `CritiqueReport`.
It does NOT gate generation, does NOT regenerate, and never touches the generation path — it
is a standalone, advisory scorer (DESIGN_CRITIC_SPEC.md §6, Slice 1).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy.typing as npt
from mimik_contracts import Brand

from .color_diff import critique_a1
from .iconography import critique_a5
from .report import AxisScore, CritiqueReport


def _brand_palette(brand: Brand) -> list[str]:
    """The brand's token hexes (deduped, order-preserving). Empty tokens → empty palette."""
    seen: set[str] = set()
    palette: list[str] = []
    for role in brand.tokens.colors:
        hex_value = (role.hex or "").strip()
        if hex_value and hex_value.upper() not in seen:
            seen.add(hex_value.upper())
            palette.append(hex_value)
    return palette


def _summarize(axes: list[AxisScore]) -> str:
    parts: list[str] = []
    for a in axes:
        shown = "unknown" if a.score is None else str(a.score)
        flag = " [HARD-FAIL]" if a.hard_fail else ""
        parts.append(f"{a.axis} {a.name}: {shown}/5{flag}")
    verdict = "advisory — no gating"
    if any(a.hard_fail for a in axes):
        verdict = "advisory — a ◆ hard-fail condition fired (would reject once gating is live)"
    return " | ".join(parts) + f"  ({verdict})"


def run_critique(
    png_bytes: bytes,
    *,
    brand: Brand,
    vision_generate: Callable[[str], str] | None = None,
    exempt_mask: npt.NDArray | None = None,
) -> CritiqueReport:
    """Score one rendered creative on A1 (objective color) + A5 (vision iconography).

    - `brand`: the `mimik_contracts.Brand` whose `tokens.colors` supply the A1 palette.
    - `vision_generate`: optional prompt->reply callable for A5 (injected in tests); default
      uses the free Gemini vision client. A missing backend degrades A5 to unknown, never crashes.
    - `exempt_mask`: optional (H, W) bool mask of illustration regions exempt from A1 (Slice 4).
    """
    a1 = critique_a1(png_bytes, _brand_palette(brand), exempt_mask=exempt_mask)
    a5 = critique_a5(png_bytes, generate=vision_generate)
    axes = [a1, a5]
    return CritiqueReport(advisory=True, axes=axes, summary=_summarize(axes))
