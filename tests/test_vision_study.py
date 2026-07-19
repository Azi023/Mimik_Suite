"""Vision study: strict-JSON study parsing, hex/complexity enforcement in code, the
corrective-retry contract, and the vision client's mime allow-list."""

from __future__ import annotations

import json

import pytest

from creative.vision.gemini_vision import generate_vision
from creative.vision.study import CreativeStudyError, study_creative

_PNG = b"\x89PNG\r\n\x1a\n fake-bytes"


def _reply(**overrides: object) -> str:
    data: dict[str, object] = {
        "mood": "clean clinical calm",
        "palette": ["#8E4B8F", "#FFFFFF", "#808080"],
        "composition": "centered subject, text band below",
        "lighting": "soft diffuse studio",
        "complexity": "minimal",
        "copy_text": "Glow from within. Book a consult.",
        "logo_assessment": "top-left wordmark, legible, usable as-is",
        "notes": "purple-on-white house style",
    }
    data.update(overrides)
    return json.dumps(data)


def test_study_parses_full_reply() -> None:
    study = study_creative(_PNG, "image/png", generate=lambda p: _reply())
    assert study.mood == "clean clinical calm"
    assert study.palette == ["#8E4B8F", "#FFFFFF", "#808080"]
    assert study.complexity == "minimal"
    assert study.copy_text is not None and "Glow from within" in study.copy_text


def test_invalid_hexes_are_dropped_not_repaired() -> None:
    study = study_creative(
        _PNG,
        "image/png",
        generate=lambda p: _reply(palette=["#8E4B8F", "purple", "#GGGGGG", "#fff"]),
    )
    assert study.palette == ["#8E4B8F", "#fff"]


def test_unknown_complexity_collapses_to_none() -> None:
    study = study_creative(_PNG, "image/png", generate=lambda p: _reply(complexity="ornate"))
    assert study.complexity is None


def test_palette_capped_at_six() -> None:
    many = [f"#00000{i}" for i in range(9)]
    study = study_creative(_PNG, "image/png", generate=lambda p: _reply(palette=many))
    assert len(study.palette) == 6


def test_non_json_reply_retries_then_fails_loud() -> None:
    calls: list[str] = []

    def generate(prompt: str) -> str:
        calls.append(prompt)
        return "I cannot help with that."

    with pytest.raises(CreativeStudyError):
        study_creative(_PNG, "image/png", generate=generate)
    assert len(calls) == 2  # original + one corrective retry, never a loop


def test_vision_client_rejects_unsupported_mime() -> None:
    with pytest.raises(ValueError, match="unsupported image mime"):
        generate_vision("describe", _PNG, "image/svg+xml")


def test_vision_client_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        generate_vision("describe", _PNG, "image/png")
