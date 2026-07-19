"""Paid image adapters + routing: spend guard, transport-mocked generation, fallback chain.

NO test here may ever hit the network — the urllib `_post` seam is always monkeypatched
before the spend gate is opened, and the gate itself is exercised with fake keys only.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from creative.adapters import (
    GeminiImageAdapter,
    GPTImageAdapter,
    ImageAdapter,
    ImageGenerationFailed,
    OpenRouterAdapter,
    PaidImageSpendNotApproved,
    choose_backend,
    generate_with_fallback,
    get_adapter,
)
from creative.adapters import gemini_image as gemini_image_mod
from creative.adapters import gpt_image as gpt_image_mod
from creative.adapters import openrouter as openrouter_mod
from creative.adapters.base import ImageRequest, ImageResult
from mimik_contracts import ImageBackend

_PNG = b"\x89PNG\r\n\x1a\nfake-image-bytes"
_PNG_B64 = base64.b64encode(_PNG).decode()

_PAID_ADAPTERS: list[tuple[type[ImageAdapter], str]] = [
    (GPTImageAdapter, "OPENAI_API_KEY"),
    (OpenRouterAdapter, "OPENROUTER_API_KEY"),
    (GeminiImageAdapter, "GEMINI_API_KEY"),
]


def _request() -> ImageRequest:
    return ImageRequest(prompt="a serene clinic interior", width=1080, height=1080)


def _assert_artifact(result: ImageResult, backend: ImageBackend, tmp_path: Path) -> None:
    assert result.backend is backend
    assert result.prompt == "a serene clinic interior"
    artifact = Path(result.artifact_ref)
    assert artifact.parent == tmp_path
    assert artifact.name.startswith(f"{backend.value}_")
    assert artifact.suffix == ".png"
    assert artifact.read_bytes() == _PNG


# ---------- spend guard (the hard budget gate) ----------


@pytest.mark.parametrize(("adapter_cls", "key_env"), _PAID_ADAPTERS)
async def test_spend_guard_blocks_every_paid_adapter(
    adapter_cls: type[ImageAdapter],
    key_env: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MIMIK_ALLOW_PAID_IMAGES", raising=False)
    monkeypatch.setenv(key_env, "fake-key")  # guard must fire BEFORE the key check
    adapter = adapter_cls(artifacts_dir=tmp_path)  # type: ignore[call-arg]
    with pytest.raises(PaidImageSpendNotApproved):
        await adapter.generate(_request())


# ---------- generation with the transport seam mocked ----------


async def test_gpt_image_generates_from_canned_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MIMIK_ALLOW_PAID_IMAGES", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
    bodies: list[dict] = []

    def fake_post(url: str, headers: dict[str, str], body: dict) -> dict:
        bodies.append(body)
        return {"data": [{"b64_json": _PNG_B64}]}

    monkeypatch.setattr(gpt_image_mod, "_post", fake_post)
    result = await GPTImageAdapter(artifacts_dir=tmp_path).generate(_request())
    _assert_artifact(result, ImageBackend.GPT_IMAGE, tmp_path)
    assert result.model == "gpt-image-2"
    assert bodies[0]["size"] == "1024x1024"  # 1080x1080 maps to the closest supported square


async def test_openrouter_generates_from_data_uri_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MIMIK_ALLOW_PAID_IMAGES", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    monkeypatch.delenv("OPENROUTER_IMAGE_MODEL", raising=False)
    bodies: list[dict] = []

    def fake_post(url: str, headers: dict[str, str], body: dict) -> dict:
        bodies.append(body)
        image = {"image_url": {"url": f"data:image/png;base64,{_PNG_B64}"}}
        return {"choices": [{"message": {"images": [image]}}]}

    monkeypatch.setattr(openrouter_mod, "_post", fake_post)
    result = await OpenRouterAdapter(artifacts_dir=tmp_path).generate(_request())
    _assert_artifact(result, ImageBackend.OPENROUTER, tmp_path)
    assert result.model == "google/gemini-2.5-flash-image"
    assert bodies[0]["modalities"] == ["image", "text"]


async def test_gemini_image_generates_from_inline_data_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MIMIK_ALLOW_PAID_IMAGES", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.delenv("GEMINI_IMAGE_MODEL", raising=False)
    bodies: list[dict] = []

    def fake_post(url: str, headers: dict[str, str], body: dict) -> dict:
        bodies.append(body)
        parts = [{"text": "here you go"}, {"inlineData": {"data": _PNG_B64}}]
        return {"candidates": [{"content": {"parts": parts}}]}

    monkeypatch.setattr(gemini_image_mod, "_post", fake_post)
    result = await GeminiImageAdapter(artifacts_dir=tmp_path).generate(_request())
    _assert_artifact(result, ImageBackend.GEMINI_IMAGE, tmp_path)
    assert result.model == "gemini-2.5-flash-image"
    assert bodies[0]["generationConfig"] == {"responseModalities": ["IMAGE"]}


# ---------- choose_backend ----------


def test_choose_backend_none_and_empty_and_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND_PRIMARY", "none")
    assert choose_backend("dev") is None
    monkeypatch.setenv("IMAGE_BACKEND_HERO", "")
    assert choose_backend("hero") is None
    monkeypatch.delenv("IMAGE_BACKEND_HERO", raising=False)
    assert choose_backend("hero") is None


def test_choose_backend_resolves_paid_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND_HERO", "gpt_image")
    assert choose_backend("hero") is ImageBackend.GPT_IMAGE


def test_choose_backend_garbage_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND_HERO", "dall-e-9000")
    with pytest.raises(ValueError):
        choose_backend("hero")


# ---------- generate_with_fallback ----------


async def test_fallback_none_backend_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND_HERO", "none")
    assert await generate_with_fallback(_request()) is None


async def test_fallback_primary_fails_twice_then_alternate_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_BACKEND_HERO", "gpt_image")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")  # alternate must look configured
    attempts: list[str] = []
    ok = ImageResult(backend=ImageBackend.OPENROUTER, artifact_ref="x.png", prompt="p")

    async def failing(self: GPTImageAdapter, request: ImageRequest) -> ImageResult:
        attempts.append("gpt_image")
        raise RuntimeError("transport down")

    async def succeeding(self: OpenRouterAdapter, request: ImageRequest) -> ImageResult:
        attempts.append("openrouter")
        return ok

    monkeypatch.setattr(GPTImageAdapter, "generate", failing)
    monkeypatch.setattr(OpenRouterAdapter, "generate", succeeding)
    result = await generate_with_fallback(_request())
    assert result is ok
    assert attempts == ["gpt_image", "gpt_image", "openrouter"]  # retry once, then alternate


async def test_fallback_all_fail_raises_generation_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_BACKEND_HERO", "openrouter")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")  # alternate gpt_image is in the chain

    async def failing(self: ImageAdapter, request: ImageRequest) -> ImageResult:
        raise RuntimeError("transport down")

    monkeypatch.setattr(OpenRouterAdapter, "generate", failing)
    monkeypatch.setattr(GPTImageAdapter, "generate", failing)
    with pytest.raises(ImageGenerationFailed):
        await generate_with_fallback(_request())


# ---------- registry ----------


def test_registry_resolves_paid_backends() -> None:
    for backend in (ImageBackend.GPT_IMAGE, ImageBackend.OPENROUTER, ImageBackend.GEMINI_IMAGE):
        assert get_adapter(backend).backend is backend


def test_none_is_a_route_not_an_adapter() -> None:
    with pytest.raises(KeyError):
        get_adapter(ImageBackend.NONE)
