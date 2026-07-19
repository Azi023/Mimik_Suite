"""Minimal free-Gemini TEXT client — the L0 copy foundation.

REST via stdlib (no SDK dep). TEXT ONLY — images use the browser adapters (though this key
CAN list image models; those need billing, so they stay off the free path). Reads
GEMINI_API_KEY from the environment; the key is only sent to Google over TLS, never logged.

`gemini-flash-latest` is the default because it always tracks the current free Flash model —
pinned version IDs (e.g. `gemini-2.5-flash`) can 404 for a given key, so on a 404 we fall
back to it automatically.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_FALLBACK_MODEL = "gemini-flash-latest"


def _call(model: str, key: str, prompt: str, timeout: int) -> dict:
    url = _ENDPOINT.format(model=model)
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    # Key in a header, never the query string — query strings leak into proxy/access logs.
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed google host)
        return json.loads(resp.read())


def generate_text(prompt: str, *, model: str | None = None, api_key: str | None = None, timeout: int = 30) -> str:
    """Generate text from a prompt. Raises RuntimeError if the key is missing."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    model = model or os.environ.get("GEMINI_TEXT_MODEL") or _FALLBACK_MODEL
    try:
        data = _call(model, key, prompt, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and model != _FALLBACK_MODEL:
            data = _call(_FALLBACK_MODEL, key, prompt, timeout)  # stale/invalid pin → current flash
        else:
            raise
    return data["candidates"][0]["content"]["parts"][0]["text"]
