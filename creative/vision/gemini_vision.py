"""Minimal free-Gemini VISION client — image + prompt in, text out.

Mirrors `creative.copy.gemini_text`: REST via stdlib (no SDK dep), GEMINI_API_KEY from the
environment (sent only to Google over TLS, never logged), `gemini-flash-latest` fallback on
a 404'd pinned model. Vision (image understanding) is free-tier on Flash; this client never
calls image *generation* models.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_FALLBACK_MODEL = "gemini-flash-latest"

_ALLOWED_MIMES = {"image/png", "image/jpeg", "image/webp"}


def _call(model: str, key: str, prompt: str, image_b64: str, mime: str, timeout: int) -> dict:
    url = _ENDPOINT.format(model=model)
    body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": mime, "data": image_b64}},
                        {"text": prompt},
                    ]
                }
            ]
        }
    ).encode()
    # Key in a header, never the query string — query strings leak into proxy/access logs.
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed google host)
        return json.loads(resp.read())


def generate_vision(
    prompt: str,
    image_bytes: bytes,
    mime: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    timeout: int = 60,
) -> str:
    """Describe/analyze one image. Raises RuntimeError on a missing key, ValueError on a
    mime the render path doesn't accept anyway."""
    if mime not in _ALLOWED_MIMES:
        raise ValueError(f"unsupported image mime for vision study: {mime!r}")
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    model = model or os.environ.get("GEMINI_VISION_MODEL") or os.environ.get(
        "GEMINI_TEXT_MODEL"
    ) or _FALLBACK_MODEL
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    try:
        data = _call(model, key, prompt, image_b64, mime, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and model != _FALLBACK_MODEL:
            data = _call(_FALLBACK_MODEL, key, prompt, image_b64, mime, timeout)
        else:
            raise
    return data["candidates"][0]["content"]["parts"][0]["text"]
