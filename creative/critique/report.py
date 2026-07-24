"""Design-critic report shapes.

Schema-first (locked constraint #1): the critic's cross-boundary payload is a Pydantic
model, not an ad-hoc dict. This lives in the critique package (a NEW critique model in our
own module) rather than `mimik-contracts`; when the full rubric lands (Slice 2) these shapes
graduate into `mimik-contracts` as `CriticReport`/`AxisScore` per DESIGN_CRITIC_SPEC.md §5.

`score` is 1-5 for a graded axis, or ``None`` for an axis that degraded to *unknown*
(e.g. A5 with no vision backend). A rejecting axis must carry both `rejection_element`
and `anchor`; without both, §3.1 treats the rejection as taste-only and it cannot gate.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AxisScore(BaseModel):
    """One graded axis of the rubric."""

    axis: str  # "A1", "A5"
    name: str  # human label
    objective: bool  # True = deterministic (no vision judgement); False = vision/advisory
    score: int | None = Field(default=None, ge=1, le=5)  # None = degraded to unknown
    findings: list[str] = Field(default_factory=list)  # element + what + fix direction
    observations: list[str] = Field(default_factory=list)  # written before scores
    rejection_element: str | None = None  # nameable element; required when score <= 2
    anchor: str | None = None  # which 1/3/5 anchor the score matched
    hard_fail: bool = False  # a ◆ showstopper condition fired (F2-class glitch, etc.)

    @property
    def rejection_is_evidence_based(self) -> bool:
        """Whether a low score names the concrete element and rubric anchor it matched."""
        if self.score is None or self.score > 2:
            return True
        return bool(self.rejection_element and self.anchor)


class CritiqueReport(BaseModel):
    """Critique of one rendered creative, suitable for advisory logging or gating."""

    advisory: bool = True
    axes: list[AxisScore] = Field(default_factory=list)
    craft_score: float | None = Field(default=None, ge=1, le=5)
    verdict: str = "UNKNOWN"
    dominant_failing_axis: str | None = None
    guardrail_breach: bool = False
    warnings: list[str] = Field(default_factory=list)
    summary: str = ""

    def axis(self, axis_id: str) -> AxisScore | None:
        for entry in self.axes:
            if entry.axis == axis_id:
                return entry
        return None

    @property
    def any_hard_fail(self) -> bool:
        return any(a.hard_fail for a in self.axes)

    @property
    def invalid_rejections(self) -> list[AxisScore]:
        return [axis for axis in self.axes if not axis.rejection_is_evidence_based]

    def passed_at(self, threshold: float) -> bool:
        """Apply the calibrated threshold plus §3.1 taste-only rejection protection."""
        if self.guardrail_breach:
            return False
        if self.invalid_rejections:
            return True
        if self.any_hard_fail:
            return False
        if self.craft_score is None:
            # An unavailable optional vision axis must not turn the default advisory path into
            # an outage. The gate flag is an explicit operator choice; unknown stays a warning.
            return True
        return self.craft_score >= threshold
