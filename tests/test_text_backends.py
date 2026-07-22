"""Text-provider clients and ordered fallback routing, with every transport mocked."""

from __future__ import annotations

import importlib
import importlib.util
import urllib.error
from types import ModuleType

import pytest

from creative import prompting
from creative.copy import gemini_text


def _load_text_module(name: str) -> ModuleType:
    qualified_name = f"creative.copy.{name}"
    assert importlib.util.find_spec(qualified_name) is not None, f"{qualified_name} is missing"
    return importlib.import_module(qualified_name)


@pytest.mark.parametrize(
    ("module_name", "key_env", "model_env", "default_model", "endpoint"),
    [
        (
            "openrouter_text",
            "OPENROUTER_API_KEY",
            "OPENROUTER_TEXT_MODEL",
            "google/gemini-2.5-flash",
            "https://openrouter.ai/api/v1/chat/completions",
        ),
        (
            "openai_text",
            "OPENAI_API_KEY",
            "OPENAI_TEXT_MODEL",
            "gpt-4o-mini",
            "https://api.openai.com/v1/chat/completions",
        ),
    ],
)
def test_chat_text_backend_returns_content(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    key_env: str,
    model_env: str,
    default_model: str,
    endpoint: str,
) -> None:
    module = _load_text_module(module_name)
    monkeypatch.delenv(model_env, raising=False)
    calls: list[tuple[str, dict[str, str], dict]] = []

    def fake_post(url: str, headers: dict[str, str], body: dict) -> dict:
        calls.append((url, headers, body))
        return {"choices": [{"message": {"content": "canned text"}}]}

    monkeypatch.setattr(module, "_post", fake_post)

    assert module.generate_text("Draft this", api_key="test-key") == "canned text"
    assert calls == [
        (
            endpoint,
            {"Authorization": "Bearer test-key", "Content-Type": "application/json"},
            {
                "model": default_model,
                "messages": [{"role": "user", "content": "Draft this"}],
            },
        )
    ]


@pytest.mark.parametrize(
    ("module_name", "key_env"),
    [
        ("openrouter_text", "OPENROUTER_API_KEY"),
        ("openai_text", "OPENAI_API_KEY"),
    ],
)
def test_chat_text_backend_requires_key(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    key_env: str,
) -> None:
    module = _load_text_module(module_name)
    monkeypatch.delenv(key_env, raising=False)
    monkeypatch.setattr(
        module,
        "_post",
        lambda *_args, **_kwargs: pytest.fail("missing-key calls must not reach transport"),
    )

    with pytest.raises(RuntimeError, match=key_env):
        module.generate_text("Draft this")


def _set_all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.delenv("TEXT_BACKEND_ORDER", raising=False)


def _rate_limit() -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/",
        429,
        "rate limited",
        hdrs=None,
        fp=None,
    )


def test_chain_falls_through_from_gemini_429_to_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openrouter_text = _load_text_module("openrouter_text")
    openai_text = _load_text_module("openai_text")
    _set_all_keys(monkeypatch)
    attempts: list[str] = []

    def gemini_call(*_args: object) -> dict:
        attempts.append("gemini")
        raise _rate_limit()

    def openrouter_post(*_args: object) -> dict:
        attempts.append("openrouter")
        return {"choices": [{"message": {"content": "openrouter result"}}]}

    monkeypatch.setattr(gemini_text, "_call", gemini_call)
    monkeypatch.setattr(openrouter_text, "_post", openrouter_post)
    monkeypatch.setattr(
        openai_text,
        "_post",
        lambda *_args: pytest.fail("the chain must stop after the first success"),
    )

    generate, model = prompting.default_generate()

    assert generate("Draft this") == "openrouter result"
    assert model == "chain:gemini,openrouter,openai"
    assert attempts == ["gemini", "openrouter"]


def test_chain_falls_through_to_openai_when_first_two_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openrouter_text = _load_text_module("openrouter_text")
    openai_text = _load_text_module("openai_text")
    _set_all_keys(monkeypatch)
    attempts: list[str] = []

    def gemini_call(*_args: object) -> dict:
        attempts.append("gemini")
        raise _rate_limit()

    def openrouter_post(*_args: object) -> dict:
        attempts.append("openrouter")
        raise OSError("openrouter unavailable")

    def openai_post(*_args: object) -> dict:
        attempts.append("openai")
        return {"choices": [{"message": {"content": "openai result"}}]}

    monkeypatch.setattr(gemini_text, "_call", gemini_call)
    monkeypatch.setattr(openrouter_text, "_post", openrouter_post)
    monkeypatch.setattr(openai_text, "_post", openai_post)

    generate, _model = prompting.default_generate()

    assert generate("Draft this") == "openai result"
    assert attempts == ["gemini", "openrouter", "openai"]


def test_chain_propagates_final_exception_when_all_providers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openrouter_text = _load_text_module("openrouter_text")
    openai_text = _load_text_module("openai_text")
    _set_all_keys(monkeypatch)
    final_error = RuntimeError("openai final failure")

    monkeypatch.setattr(gemini_text, "_call", lambda *_args: (_ for _ in ()).throw(_rate_limit()))
    monkeypatch.setattr(
        openrouter_text,
        "_post",
        lambda *_args: (_ for _ in ()).throw(OSError("openrouter unavailable")),
    )
    monkeypatch.setattr(
        openai_text,
        "_post",
        lambda *_args: (_ for _ in ()).throw(final_error),
    )

    generate, _model = prompting.default_generate()

    with pytest.raises(RuntimeError) as exc_info:
        generate("Draft this")
    assert exc_info.value is final_error


def test_chain_skips_provider_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    openrouter_text = _load_text_module("openrouter_text")
    openai_text = _load_text_module("openai_text")
    monkeypatch.setenv("TEXT_BACKEND_ORDER", "openrouter, openai")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setattr(
        openrouter_text,
        "_post",
        lambda *_args: pytest.fail("a provider without a key must be skipped"),
    )
    monkeypatch.setattr(
        openai_text,
        "_post",
        lambda *_args: {"choices": [{"message": {"content": "openai result"}}]},
    )

    generate, model = prompting.default_generate()

    assert generate("Draft this") == "openai result"
    assert model == "chain:openrouter,openai"


def test_chain_respects_configured_order(monkeypatch: pytest.MonkeyPatch) -> None:
    openai_text = _load_text_module("openai_text")
    monkeypatch.setenv("TEXT_BACKEND_ORDER", " openai, gemini ")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setattr(
        openai_text,
        "_post",
        lambda *_args: {"choices": [{"message": {"content": "openai first"}}]},
    )
    monkeypatch.setattr(
        gemini_text,
        "_call",
        lambda *_args: pytest.fail("configured order must stop after OpenAI succeeds"),
    )

    generate, model = prompting.default_generate()

    assert generate("Draft this") == "openai first"
    assert model == "chain:openai,gemini"
