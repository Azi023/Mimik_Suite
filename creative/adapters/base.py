"""Image generation adapter interface — the seam that makes 'subscription now, API later'
a config change, not a rewrite.

Every backend (browser-automated ChatGPT, free Gemini tier, or a paid API later) implements
`ImageAdapter`. Callers depend only on this interface, never on a concrete backend.
"""

from __future__ import annotations

import abc

from pydantic import BaseModel, Field

from mimik_contracts import ImageBackend


class ImageRequest(BaseModel):
    prompt: str
    width: int
    height: int
    reference_urls: list[str] = Field(default_factory=list)
    params: dict[str, object] = Field(default_factory=dict)


class ImageResult(BaseModel):
    backend: ImageBackend
    artifact_ref: str  # where the produced image landed (local path / storage ref)
    # Full recipe echo so the CreativeDoc layer can store reproducible prompt-DNA:
    prompt: str
    model: str | None = None


class ImageAdapter(abc.ABC):
    """A source of generated imagery for L1/L2."""

    backend: ImageBackend

    @abc.abstractmethod
    async def generate(self, request: ImageRequest) -> ImageResult:
        """Produce an image for the request. Implementations land in P2."""
        raise NotImplementedError
