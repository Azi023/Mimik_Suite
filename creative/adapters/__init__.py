"""Adapter registry: resolve an ImageBackend enum to a concrete adapter.

Callers ask for a backend by enum; they never import a concrete class. Adding a paid API
later = register one more class here, nothing else changes.
"""

from __future__ import annotations

from mimik_contracts import ImageBackend

from .base import ImageAdapter, ImageRequest, ImageResult
from .chatgpt_browser import ChatGPTBrowserAdapter
from .gemini_free import GeminiFreeAdapter

_REGISTRY: dict[ImageBackend, type[ImageAdapter]] = {
    ImageBackend.CHATGPT_BROWSER: ChatGPTBrowserAdapter,
    ImageBackend.GEMINI_FREE: GeminiFreeAdapter,
    # Paid APIs (IDEOGRAM, FLUX, GPT_IMAGE) register here once there's budget.
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
    "get_adapter",
    "available_backends",
    "ChatGPTBrowserAdapter",
    "GeminiFreeAdapter",
]
