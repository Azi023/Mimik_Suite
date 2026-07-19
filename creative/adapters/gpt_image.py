"""OpenAI gpt-image-1 via the paid Images API (hero-quality backend).

REST via stdlib (no SDK dep), mirroring creative/copy/gemini_text.py. The blocking urllib
call is wrapped in asyncio.to_thread; tests monkeypatch the `_post` seam so nothing here
ever hits the network in dev/test. Spend is operator-gated (MIMIK_ALLOW_PAID_IMAGES=1)
BEFORE any key check. The key is only sent to OpenAI over TLS, never logged.
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

_ENDPOINT = "https://api.openai.com/v1/images/generations"
# Operator preference: the BEST tier for real deliverables. Overridable via OPENAI_IMAGE_MODEL.
_DEFAULT_MODEL = "gpt-image-2"
# gpt-image-1 supports exactly these output sizes; requests map to the closest aspect ratio.
_SIZES: tuple[tuple[int, int], ...] = ((1024, 1024), (1024, 1536), (1536, 1024))


def _post(url: str, headers: dict[str, str], body: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (fixed openai host)
        return json.loads(resp.read())


def _closest_size(width: int, height: int) -> str:
    ratio = width / height
    w, h = min(_SIZES, key=lambda size: abs(size[0] / size[1] - ratio))
    return f"{w}x{h}"


class GPTImageAdapter(ImageAdapter):
    backend = ImageBackend.GPT_IMAGE

    def __init__(self, artifacts_dir: Path = Path("artifacts")) -> None:
        self.artifacts_dir = artifacts_dir

    async def generate(self, request: ImageRequest) -> ImageResult:
        ensure_spend_approved(self.backend)  # hard budget gate — before any key/config check
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        model = os.environ.get("OPENAI_IMAGE_MODEL") or _DEFAULT_MODEL
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {
            "model": model,
            "prompt": request.prompt,
            "size": _closest_size(request.width, request.height),
        }
        data = await asyncio.to_thread(_post, _ENDPOINT, headers, body)
        items = data.get("data")
        if not isinstance(items, list) or not items or "b64_json" not in items[0]:
            raise RuntimeError(f"gpt-image response has no image data (keys: {sorted(data)})")
        b64 = items[0]["b64_json"]
        path = write_image_artifact(self.artifacts_dir, self.backend, b64)
        return ImageResult(
            backend=self.backend, artifact_ref=str(path), prompt=request.prompt, model=model
        )
