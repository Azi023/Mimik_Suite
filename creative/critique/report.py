"""Design-critic report shapes (Slice 1 — A1 + A5, advisory-only).

Schema-first (locked constraint #1): the critic's cross-boundary payload is a Pydantic
model, not an ad-hoc dict. This lives in the critique package (a NEW critique model in our
own module) rather than `mimik-contracts`; when the full rubric lands (Slice 2) these shapes
graduate into `mimik-contracts` as `CriticReport`/`AxisScore` per DESIGN_CRITIC_SPEC.md §5.

`score` is 1-5 for a graded axis, or ``None`` for an axis that degraded to *unknown*
(e.g. A5 with no vision backend). Advisory mode: this report never gates generation — it
scores the rendered PNG and reports.
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
    anchor: str | None = None  # which 1/3/5 anchor the score matched
    hard_fail: bool = False  # a ◆ showstopper condition fired (F2-class glitch, etc.)


class CritiqueReport(BaseModel):
    """Advisory critique of one rendered creative across the Slice-1 axes."""

    advisory: bool = True  # Slice 1 never gates the pipeline — verdicts are logged, not enforced
    axes: list[AxisScore] = Field(default_factory=list)
    summary: str = ""

    def axis(self, axis_id: str) -> AxisScore | None:
        for entry in self.axes:
            if entry.axis == axis_id:
                return entry
        return None

    @property
    def any_hard_fail(self) -> bool:
        return any(a.hard_fail for a in self.axes)
