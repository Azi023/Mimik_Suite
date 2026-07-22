"""Tests for the machine-readable design-feedback flywheel."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def isolated_feedback_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ModuleType, Path]:
    """Point feedback writes at a temporary copy of the checked-in rubric seed."""
    try:
        feedback = importlib.import_module("creative.knowledge.feedback")
    except ModuleNotFoundError as exc:
        pytest.fail(f"feedback store is not implemented: {exc}")

    seed_path = Path(feedback.__file__).with_name("design_rules.json")
    rules_path = tmp_path / "design_rules.json"
    rules_path.write_text(seed_path.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(feedback, "RULES_PATH", rules_path)
    return feedback, rules_path


def test_loads_current_rubric_seed(isolated_feedback_store: tuple[ModuleType, Path]) -> None:
    feedback, _ = isolated_feedback_store

    rules = feedback.load_rules()

    assert {rule.id for rule in rules} == {"C1", "C2", "T1", "T2", "B1", "B2", "P1", "G1", "G2"}
    assert all(rule.active and rule.weight == 1.0 for rule in rules)


def test_records_weight_change_and_new_decline_rule(
    isolated_feedback_store: tuple[ModuleType, Path],
) -> None:
    feedback, rules_path = isolated_feedback_store
    initial_weight = next(rule.weight for rule in feedback.load_rules() if rule.id == "T1")

    accepted = feedback.record_feedback(
        verdict="accept",
        reason="The CTA hierarchy worked.",
        rule_id="T1",
        source="claude",
    )
    learned = feedback.record_feedback(
        verdict="decline",
        reason="Keep supporting icons outside the headline's clear space.",
        profile_id="glo2go-aesthetics",
        source="operator",
    )

    persisted = json.loads(rules_path.read_text(encoding="utf-8"))
    persisted_by_id = {item["id"]: item for item in persisted}
    assert accepted.weight > initial_weight
    assert persisted_by_id["T1"]["weight"] == accepted.weight
    assert learned.id.startswith("L")
    assert persisted_by_id[learned.id]["rule"] == learned.rule
    assert learned.why == "Captured from declined design feedback."
    assert persisted_by_id[learned.id]["applies_to"] == ["glo2go-aesthetics"]
    assert learned.id in {rule.id for rule in feedback.load_rules("glo2go-aesthetics")}


def test_prompt_block_contains_active_rule_line(
    isolated_feedback_store: tuple[ModuleType, Path],
) -> None:
    feedback, _ = isolated_feedback_store
    first_rule = feedback.load_rules("simply-nikah")[0]

    block = feedback.rules_as_prompt_block("simply-nikah")

    assert block.startswith("Design rules to obey:")
    assert f"- {first_rule.id}: {first_rule.rule}" in block
