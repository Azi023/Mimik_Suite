"""Text-safe region selection reuses the mocked free-Gemini vision seam."""

from __future__ import annotations

from pathlib import Path

import pytest

from creative.vision import text_region as text_region_module


async def test_find_text_region_reads_local_image_and_parses_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image = tmp_path / "portrait.png"
    image_bytes = b"\x89PNG\r\n\x1a\nunit-test-image"
    image.write_bytes(image_bytes)
    calls: list[tuple[str, bytes, str]] = []

    def generate(prompt: str, supplied_bytes: bytes, mime: str) -> str:
        calls.append((prompt, supplied_bytes, mime))
        return '{"region":"left","reason":"The subject and face occupy the right side."}'

    monkeypatch.setattr(text_region_module, "generate_vision", generate)

    result = await text_region_module.find_text_region(str(image))

    assert result.region == "left"
    assert result.reason == "The subject and face occupy the right side."
    assert calls[0][1:] == (image_bytes, "image/png")
    assert "calmest negative space" in calls[0][0]
    assert "must NOT cover the subject's face/product" in calls[0][0]


async def test_find_text_region_retries_invalid_json_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def generate(prompt: str, supplied_bytes: bytes, mime: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            return '{"region":"near_the_face","reason":"Not an allowed region."}'
        return '{"region":"bottom_left","reason":"Calm floor area away from the product."}'

    monkeypatch.setattr(text_region_module, "generate_vision", generate)

    result = await text_region_module.find_text_region("data:image/png;base64,aGk=")

    assert result.region == "bottom_left"
    assert len(calls) == 2
    assert "previous reply was rejected" in calls[1]
