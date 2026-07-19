"""Paid Gemini image generation via generateContent with IMAGE modality.

Same GEMINI_API_KEY as the free text path (creative/copy/gemini_text.py), but images are
billing-gated on Google's side — this adapter is paid, full stop. REST via stdlib; the
blocking urllib call is wrapped in asyncio.to_thread; tests monkeypatch the `_post` seam so
nothing here ever hits the network in dev/test. Spend is operator-gated
(MIMIK_ALLOW_PAID_IMAGES=1) BEFORE any key check. The key travels in a header over TLS,
never in the URL, never logged.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from pathlib import Path

from mimik_contracts import ImageBackend

from .base import ImageAdapter, ImageRequest, ImageResult
from .router import ensure_spend_approved, write_image_artifact

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_DEFAULT_MODEL = "gemini-2.5-flash-image"


def _post(url: str, headers: dict[str, str], body: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (fixed google host)
        return json.loads(resp.read())


class GeminiImageAdapter(ImageAdapter):
    backend = ImageBackend.GEMINI_IMAGE

    def __init__(self, artifacts_dir: Path = Path("artifacts")) -> None:
        self.artifacts_dir = artifacts_dir

    async def generate(self, request: ImageRequest) -> ImageResult:
        ensure_spend_approved(self.backend)  # hard budget gate — before any key/config check
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        model = os.environ.get("GEMINI_IMAGE_MODEL") or _DEFAULT_MODEL
        url = _ENDPOINT.format(model=model)
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
        body = {
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        data = await asyncio.to_thread(_post, url, headers, body)
        parts = data["candidates"][0]["content"]["parts"]
        b64 = next((part["inlineData"]["data"] for part in parts if "inlineData" in part), None)
        if b64 is None:
            raise RuntimeError("gemini image response contained no inlineData image part")
        path = write_image_artifact(self.artifacts_dir, self.backend, b64)
        return ImageResult(
            backend=self.backend, artifact_ref=str(path), prompt=request.prompt, model=model
        )
