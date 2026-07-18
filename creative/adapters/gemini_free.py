"""Free Google AI Studio (Gemini / Nano Banana) image generation (build-phase co-primary).

API-shaped and robust, free within rate limits — a far sturdier default than browser
automation, and brand-consistent-series capable. Swapping to the paid tier later is a
config change (same adapter). Implementation lands in P2.
"""

from __future__ import annotations

from mimik_contracts import ImageBackend

from .base import ImageAdapter, ImageRequest, ImageResult


class GeminiFreeAdapter(ImageAdapter):
    backend = ImageBackend.GEMINI_FREE

    async def generate(self, request: ImageRequest) -> ImageResult:
        raise NotImplementedError(
            "GeminiFreeAdapter.generate is wired in P2 (Google AI Studio free tier)."
        )
