"""Minimal OpenRouter chat-completions client for text generation."""

from __future__ import annotations

import json
import os
import urllib.request
from contextvars import ContextVar

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "google/gemini-2.5-flash"
_REQUEST_TIMEOUT: ContextVar[int] = ContextVar("openrouter_text_timeout", default=30)


def _post(url: str, headers: dict[str, str], body: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(  # noqa: S310 (fixed openrouter host)
        req,
        timeout=_REQUEST_TIMEOUT.get(),
    ) as resp:
        return json.loads(resp.read())


def generate_text(
    prompt: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    timeout: int = 30,
) -> str:
    """Generate text through OpenRouter. Raises RuntimeError if the key is missing."""
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    resolved_model = model or os.environ.get("OPENROUTER_TEXT_MODEL") or _DEFAULT_MODEL
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {
        "model": resolved_model,
        "messages": [{"role": "user", "content": prompt}],
    }
    timeout_token = _REQUEST_TIMEOUT.set(timeout)
    try:
        data = _post(_ENDPOINT, headers, body)
    finally:
        _REQUEST_TIMEOUT.reset(timeout_token)
    return data["choices"][0]["message"]["content"]
