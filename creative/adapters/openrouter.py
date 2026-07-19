"""OpenRouter image generation via chat/completions with image modality (paid fallback).

REST via stdlib (no SDK dep), mirroring creative/copy/gemini_text.py. The blocking urllib
call is wrapped in asyncio.to_thread; tests monkeypatch the `_post` seam so nothing here
ever hits the network in dev/test. Spend is operator-gated (MIMIK_ALLOW_PAID_IMAGES=1)
BEFORE any key check — the ~$3 OpenRouter budget is the tightest, use SPARINGLY.
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

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "google/gemini-2.5-flash-image"


def _post(url: str, headers: dict[str, str], body: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (fixed openrouter host)
        return json.loads(resp.read())


class OpenRouterAdapter(ImageAdapter):
    backend = ImageBackend.OPENROUTER

    def __init__(self, artifacts_dir: Path = Path("artifacts")) -> None:
        self.artifacts_dir = artifacts_dir

    async def generate(self, request: ImageRequest) -> ImageResult:
        ensure_spend_approved(self.backend)  # hard budget gate — before any key/config check
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        model = os.environ.get("OPENROUTER_IMAGE_MODEL") or _DEFAULT_MODEL
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {
            "model": model,
            "messages": [{"role": "user", "content": request.prompt}],
            "modalities": ["image", "text"],
        }
        data = await asyncio.to_thread(_post, _ENDPOINT, headers, body)
        # The image comes back as a data URI: "data:image/png;base64,<payload>".
        data_uri: str = data["choices"][0]["message"]["images"][0]["image_url"]["url"]
        if "," not in data_uri:
            raise RuntimeError("openrouter returned an image URL that is not a data URI")
        b64 = data_uri.split(",", 1)[1]
        path = write_image_artifact(self.artifacts_dir, self.backend, b64)
        return ImageResult(
            backend=self.backend, artifact_ref=str(path), prompt=request.prompt, model=model
        )
