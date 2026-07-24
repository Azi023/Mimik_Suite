"""Design critic — calibrated scorer and opt-in generation gate policy.

Scores a rendered creative PNG on A1 (brand-token-diff, objective) + A5 (iconography
recognizability, vision). Advisory-only: it does not gate generation, does not regenerate,
and does not touch the generation path. See docs/DESIGN_CRITIC_SPEC.md §6.
"""

from .color_diff import critique_a1
from .calibration import CRITIC_PASS_THRESHOLD
from .critic import run_critique
from .gate import GateDecision, RetryDirective, decide_gate
from .iconography import critique_a5
from .report import AxisScore, CritiqueReport

__all__ = [
    "CRITIC_PASS_THRESHOLD",
    "run_critique",
    "decide_gate",
    "GateDecision",
    "RetryDirective",
    "CritiqueReport",
    "AxisScore",
    "critique_a1",
    "critique_a5",
]
