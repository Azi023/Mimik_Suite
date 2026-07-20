"""Adapter registry: resolve an ImageBackend enum to a concrete adapter.

Callers ask for a backend by enum; they never import a concrete class. Adding a paid API
later = register one more class here, nothing else changes.
"""

from __future__ import annotations

from mimik_contracts import ImageBackend

from .base import ImageAdapter, ImageRequest, ImageResult
from .chatgpt_browser import ChatGPTBrowserAdapter
from .gemini_free import GeminiFreeAdapter
from .gemini_image import GeminiImageAdapter
from .gpt_image import GPTImageAdapter
from .leonardo_browser import LeonardoBrowserAdapter
from .openrouter import OpenRouterAdapter
from .router import (
    ImageGenerationFailed,
    PaidImageSpendNotApproved,
    choose_backend,
    generate_with_fallback,
)

_REGISTRY: dict[ImageBackend, type[ImageAdapter]] = {
    ImageBackend.CHATGPT_BROWSER: ChatGPTBrowserAdapter,
    ImageBackend.LEONARDO_BROWSER: LeonardoBrowserAdapter,  # subscription browser path (no API cost)
    ImageBackend.GEMINI_FREE: GeminiFreeAdapter,
    # Paid APIs — spend-gated inside each adapter (MIMIK_ALLOW_PAID_IMAGES=1):
    ImageBackend.GPT_IMAGE: GPTImageAdapter,
    ImageBackend.OPENROUTER: OpenRouterAdapter,
    ImageBackend.GEMINI_IMAGE: GeminiImageAdapter,
    # ImageBackend.NONE is the no-op placeholder route, NOT an adapter — stays unregistered.
    # IDEOGRAM / FLUX register here once there's budget.
}


def get_adapter(backend: ImageBackend) -> ImageAdapter:
    """Return an adapter instance for the backend. Raises KeyError for unregistered backends."""
    return _REGISTRY[backend]()


def available_backends() -> list[ImageBackend]:
    return list(_REGISTRY)


__all__ = [
    "ImageAdapter",
    "ImageRequest",
    "ImageResult",
    "ImageGenerationFailed",
    "PaidImageSpendNotApproved",
    "choose_backend",
    "generate_with_fallback",
    "get_adapter",
    "available_backends",
    "ChatGPTBrowserAdapter",
    "LeonardoBrowserAdapter",
    "GeminiFreeAdapter",
    "GeminiImageAdapter",
    "GPTImageAdapter",
    "OpenRouterAdapter",
]
