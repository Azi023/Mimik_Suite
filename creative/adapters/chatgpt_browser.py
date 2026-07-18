"""ChatGPT image generation via browser automation (build-phase primary).

Uses Playwright to drive chatgpt.com image gen on the operator's subscription — no API cost.
Fragility (UI drift, rate limits) is accepted for the build phase and isolated behind the
adapter so swapping to the paid GPT-Image API later is a one-line config change.

Implementation lands in P2.
"""

from __future__ import annotations

from mimik_contracts import ImageBackend

from .base import ImageAdapter, ImageRequest, ImageResult


class ChatGPTBrowserAdapter(ImageAdapter):
    backend = ImageBackend.CHATGPT_BROWSER

    async def generate(self, request: ImageRequest) -> ImageResult:
        raise NotImplementedError(
            "ChatGPTBrowserAdapter.generate is wired in P2 (Playwright browser automation)."
        )
