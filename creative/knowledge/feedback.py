"""Persist and render the design rules learned from creative feedback."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RULES_PATH = Path(__file__).with_name("design_rules.json")

_ACCEPT_WEIGHT_DELTA = 0.1
_DECLINE_WEIGHT_DELTA = 0.2
_LEARNED_RULE_ID = re.compile(r"^L(?P<number>\d+)$")


class DesignRule(BaseModel):
    """One active or superseded design instruction in the flywheel store."""

    model_config = ConfigDict(extra="forbid")

    id: str
    rule: str
    why: str
    applies_to: list[str] = Field(min_length=1)
    source: str
    active: bool = True
    weight: float = Field(default=1.0, ge=0)
    created: str


def _read_rules() -> list[DesignRule]:
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("design_rules.json must contain a JSON list")
    return [DesignRule.model_validate(item) for item in payload]


def _write_rules(rules: list[DesignRule]) -> None:
    """Replace the rule store atomically after flushing the complete JSON payload."""
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=RULES_PATH.parent,
        prefix=f".{RULES_PATH.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(
                [rule.model_dump(mode="json") for rule in rules],
                temporary_file,
                ensure_ascii=False,
                indent=2,
            )
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, RULES_PATH)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_rules(profile_id: str | None = None) -> list[DesignRule]:
    """Load active rules, optionally limited to the global and matching profile scopes."""
    rules = [rule for rule in _read_rules() if rule.active]
    if profile_id is not None:
        rules = [
            rule
            for rule in rules
            if "all" in rule.applies_to or profile_id in rule.applies_to
        ]
    return sorted(rules, key=lambda rule: rule.weight, reverse=True)


def _normalise_reason(reason: str) -> str:
    return " ".join(reason.split()).casefold()


def _next_learned_id(rules: list[DesignRule]) -> str:
    learned_numbers = [
        int(match.group("number"))
        for rule in rules
        if (match := _LEARNED_RULE_ID.fullmatch(rule.id)) is not None
    ]
    return f"L{max(learned_numbers, default=0) + 1}"


def _raised_weight(rule: DesignRule, verdict: Literal["accept", "decline"]) -> DesignRule:
    delta = _ACCEPT_WEIGHT_DELTA if verdict == "accept" else _DECLINE_WEIGHT_DELTA
    return rule.model_copy(update={"weight": round(rule.weight + delta, 4)})


def record_feedback(
    *,
    verdict: Literal["accept", "decline"],
    reason: str,
    rule_id: str | None = None,
    profile_id: str | None = None,
    source: str = "claude",
) -> DesignRule:
    """Raise a known rule's priority or persist a new rule learned from feedback."""
    if verdict not in {"accept", "decline"}:
        raise ValueError("verdict must be 'accept' or 'decline'")

    clean_reason = " ".join(reason.split())
    if not clean_reason:
        raise ValueError("reason must not be empty")

    rules = _read_rules()
    if rule_id is not None:
        for index, rule in enumerate(rules):
            if rule.id == rule_id:
                updated_rule = _raised_weight(rule, verdict)
                rules[index] = updated_rule
                _write_rules(rules)
                return updated_rule
        raise ValueError(f"unknown design rule id: {rule_id}")

    normalised_reason = _normalise_reason(clean_reason)
    for index, rule in enumerate(rules):
        if rule.active and _normalise_reason(rule.rule) == normalised_reason:
            updated_rule = _raised_weight(rule, verdict)
            rules[index] = updated_rule
            _write_rules(rules)
            return updated_rule

    learned_rule = DesignRule(
        id=_next_learned_id(rules),
        rule=clean_reason,
        why=f"Captured from {'accepted' if verdict == 'accept' else 'declined'} design feedback.",
        applies_to=[profile_id or "all"],
        source=source,
        active=True,
        weight=1.0,
        created=date.today().isoformat(),
    )
    rules.append(learned_rule)
    _write_rules(rules)
    return learned_rule


def rules_as_prompt_block(profile_id: str | None = None) -> str:
    """Render active rules in descending priority for an art-director prompt."""
    lines = ["Design rules to obey:"]
    lines.extend(f"- {rule.id}: {rule.rule}" for rule in load_rules(profile_id))
    return "\n".join(lines)
