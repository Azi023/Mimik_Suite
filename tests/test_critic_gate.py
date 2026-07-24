"""Design-critic gate verdict and retry-ladder tests."""

from __future__ import annotations

import pytest

from creative.critique.gate import RetryDirective, decide_gate
from creative.critique.report import AxisScore, CritiqueReport


def _report(
    *,
    axis: str = "A2",
    score: int = 1,
    hard_fail: bool = False,
    guardrail_breach: bool = False,
) -> CritiqueReport:
    return CritiqueReport(
        axes=[
            AxisScore(
                axis=axis,
                name="test axis",
                objective=False,
                score=score,
                findings=["named observation"],
                rejection_element="headline",
                anchor="anchor 1: hierarchy collapse",
                hard_fail=hard_fail,
            )
        ],
        craft_score=float(score),
        verdict="HARD_FAIL" if hard_fail else "FAIL",
        dominant_failing_axis=axis,
        guardrail_breach=guardrail_breach,
    )


def test_gate_pass_has_no_retry() -> None:
    report = _report(score=5)
    report.verdict = "PASS"

    decision = decide_gate(report, threshold=3.8, regenerations=0)

    assert decision.passed is True
    assert decision.retry_directive is RetryDirective.NONE


def test_first_failure_re_art_directs_same_archetype() -> None:
    decision = decide_gate(_report(), threshold=3.8, regenerations=0)

    assert decision.passed is False
    assert decision.dominant_failing_axis == "A2"
    assert decision.retry_directive is RetryDirective.RE_ART_DIRECT_SAME_ARCHETYPE


@pytest.mark.parametrize("axis", ["A2", "A3", "A7"])
def test_second_failure_swaps_archetype_for_structure_axes(axis: str) -> None:
    decision = decide_gate(_report(axis=axis), threshold=3.8, regenerations=1)

    assert decision.retry_directive is RetryDirective.SWAP_ARCHETYPE


@pytest.mark.parametrize("axis", ["A5", "A6"])
def test_second_failure_selects_finish_escalation_for_craft_axes(axis: str) -> None:
    decision = decide_gate(_report(axis=axis), threshold=3.8, regenerations=1)

    assert decision.retry_directive is RetryDirective.FINISH_ESCALATION


def test_third_regeneration_is_last_constrained_pass() -> None:
    decision = decide_gate(_report(), threshold=3.8, regenerations=2)

    assert decision.retry_directive is RetryDirective.RE_ART_DIRECT_SAME_ARCHETYPE


def test_hard_cap_parks_for_art_direction() -> None:
    decision = decide_gate(_report(), threshold=3.8, regenerations=3)

    assert decision.passed is False
    assert decision.retry_directive is RetryDirective.NEEDS_ART_DIRECTION


def test_guardrail_breach_quarantines_instantly() -> None:
    decision = decide_gate(
        _report(hard_fail=True, guardrail_breach=True),
        threshold=3.8,
        regenerations=0,
    )

    assert decision.passed is False
    assert decision.retry_directive is RetryDirective.QUARANTINE
