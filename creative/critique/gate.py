"""Pure gate decision policy for the design-critic retry ladder."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from .calibration import CRITIC_PASS_THRESHOLD
from .report import CritiqueReport

MAX_CRITIC_REGENERATIONS = 3


class RetryDirective(str, Enum):
    NONE = "none"
    RE_ART_DIRECT_SAME_ARCHETYPE = "re_art_direct_same_archetype"
    SWAP_ARCHETYPE = "swap_archetype"
    FINISH_ESCALATION = "finish_escalation"
    QUARANTINE = "quarantine"
    NEEDS_ART_DIRECTION = "needs_art_direction"


class GateDecision(BaseModel):
    passed: bool
    dominant_failing_axis: str | None = None
    retry_directive: RetryDirective


_STRUCTURE_AXES = frozenset({"A2", "A3", "A7"})
_FINISH_AXES = frozenset({"A5", "A6"})


def decide_gate(
    report: CritiqueReport,
    *,
    threshold: float = CRITIC_PASS_THRESHOLD,
    regenerations: int = 0,
) -> GateDecision:
    """Return the next deterministic retry-ladder action for one critique report."""
    dominant = report.dominant_failing_axis
    if report.guardrail_breach:
        return GateDecision(
            passed=False,
            dominant_failing_axis=dominant,
            retry_directive=RetryDirective.QUARANTINE,
        )
    if report.passed_at(threshold):
        return GateDecision(
            passed=True,
            dominant_failing_axis=dominant,
            retry_directive=RetryDirective.NONE,
        )
    if regenerations >= MAX_CRITIC_REGENERATIONS:
        directive = RetryDirective.NEEDS_ART_DIRECTION
    elif regenerations == 0:
        directive = RetryDirective.RE_ART_DIRECT_SAME_ARCHETYPE
    elif regenerations == 1 and dominant in _STRUCTURE_AXES:
        directive = RetryDirective.SWAP_ARCHETYPE
    elif regenerations == 1 and dominant in _FINISH_AXES:
        directive = RetryDirective.FINISH_ESCALATION
    else:
        # The third and final regeneration is a constrained same-archetype pass. If it
        # still fails, the next decision hits the hard cap and parks.
        directive = RetryDirective.RE_ART_DIRECT_SAME_ARCHETYPE
    return GateDecision(
        passed=False,
        dominant_failing_axis=dominant,
        retry_directive=directive,
    )
