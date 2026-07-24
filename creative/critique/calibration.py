"""Golden-set threshold calibration for the design critic."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from .report import CritiqueReport

CRITIC_PASS_THRESHOLD = 3.8


class CalibrationItem(BaseModel):
    """One scored golden anchor and its operator-recorded expected verdict."""

    name: str
    expected_verdict: str
    report: CritiqueReport


class CalibrationResult(BaseModel):
    threshold: float
    passed: bool
    rank_ordered: bool
    failures: list[str] = Field(default_factory=list)


def calibrate_threshold(
    evaluations: Sequence[CalibrationItem],
    *,
    preferred_threshold: float = CRITIC_PASS_THRESHOLD,
) -> CalibrationResult:
    """Pick the preferred threshold when it separates every PASS from every FAIL.

    If the preferred value falls outside the valid interval, choose the midpoint between
    the highest FAIL score and lowest PASS score. Hard fails remain failures regardless of
    score. The returned result is the regression-gate verdict, not a silent best effort.
    """
    pass_scores = [
        item.report.craft_score
        for item in evaluations
        if item.expected_verdict == "PASS" and item.report.craft_score is not None
    ]
    fail_scores = [
        item.report.craft_score
        for item in evaluations
        if item.expected_verdict == "FAIL" and item.report.craft_score is not None
    ]
    if not pass_scores or not fail_scores:
        return CalibrationResult(
            threshold=preferred_threshold,
            passed=False,
            rank_ordered=False,
            failures=["Golden set requires at least one scored PASS and one scored FAIL anchor."],
        )

    pass_floor = min(pass_scores)
    fail_ceiling = max(fail_scores)
    rank_ordered = fail_ceiling < pass_floor
    threshold = preferred_threshold
    if not (fail_ceiling < threshold <= pass_floor) and rank_ordered:
        threshold = round((fail_ceiling + pass_floor) / 2.0, 3)

    failures: list[str] = []
    for item in evaluations:
        expected_pass = item.expected_verdict == "PASS"
        actual_pass = item.report.passed_at(threshold)
        if actual_pass != expected_pass:
            failures.append(
                f"{item.name}: expected {item.expected_verdict}, "
                f"score={item.report.craft_score}, hard_fail={item.report.any_hard_fail}"
            )
    if not rank_ordered:
        failures.append(
            f"Rank ordering failed: highest FAIL {fail_ceiling:.3f} >= lowest PASS {pass_floor:.3f}."
        )
    return CalibrationResult(
        threshold=threshold,
        passed=not failures,
        rank_ordered=rank_ordered,
        failures=failures,
    )
