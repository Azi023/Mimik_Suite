"""Design critic (Slice 1) — advisory post-generation scorer.

Scores a rendered creative PNG on A1 (brand-token-diff, objective) + A5 (iconography
recognizability, vision). Advisory-only: it does not gate generation, does not regenerate,
and does not touch the generation path. See docs/DESIGN_CRITIC_SPEC.md §6.
"""

from .color_diff import critique_a1
from .critic import run_critique
from .iconography import critique_a5
from .report import AxisScore, CritiqueReport

__all__ = ["run_critique", "CritiqueReport", "AxisScore", "critique_a1", "critique_a5"]
