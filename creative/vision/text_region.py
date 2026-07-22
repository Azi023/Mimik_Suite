"""Locate calm negative space for text using the existing free-Gemini vision seam."""

from __future__ import annotations

import asyncio
import base64
import binascii
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from creative import prompting
from creative.vision.gemini_vision import generate_vision

_PROMPT = """Analyze this image for a text overlay.
Where is the main subject, and which region has the calmest negative space for a text overlay
that must NOT cover the subject's face/product?

Reply with ONLY one strict JSON object in this shape:
{"region":"top|bottom|left|right|top_left|top_right|bottom_left|bottom_right|center",
"reason":"brief evidence-based explanation"}
Choose exactly one listed region. Do not return markdown or extra keys.
"""
_RETRY_SUFFIX = (
    "\n\nYour previous reply was rejected: it was not one strict JSON object matching the "
    "output spec. Reply again with ONLY the JSON object."
)
_MIME_BY_SUFFIX = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_ALLOWED_MIMES = frozenset(_MIME_BY_SUFFIX.values())


class TextRegion(BaseModel):
    """A coarse, compositor-ready area that is safe for text."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    region: Literal[
        "top",
        "bottom",
        "left",
        "right",
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
        "center",
    ]
    reason: str = Field(min_length=1)


class TextRegionError(RuntimeError):
    """Gemini did not return a valid text-safe region after one corrective retry."""


def _read_image_ref(image_ref: str) -> tuple[bytes, str]:
    if image_ref.startswith("data:image/"):
        header, separator, encoded = image_ref.partition(",")
        if not separator or not header.endswith(";base64"):
            raise ValueError("text-region image data URI must be base64 encoded")
        mime = header.removeprefix("data:").removesuffix(";base64")
        if mime not in _ALLOWED_MIMES:
            raise ValueError(f"unsupported image mime for text-region vision: {mime!r}")
        try:
            return base64.b64decode(encoded, validate=True), mime
        except (binascii.Error, ValueError) as exc:
            raise ValueError("text-region image data URI contains invalid base64") from exc

    path = Path(image_ref)
    if not path.is_file():
        raise FileNotFoundError(f"text-region image path is not a local file: {image_ref}")
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower())
    if mime is None:
        supported = ", ".join(sorted(_MIME_BY_SUFFIX))
        raise ValueError(f"text-region image must use one of these extensions: {supported}")
    return path.read_bytes(), mime


def _to_text_region(data: dict[str, object]) -> TextRegion:
    return TextRegion.model_validate(data)


def _find_text_region_sync(image_ref: str) -> TextRegion:
    image_bytes, mime = _read_image_ref(image_ref)

    def generate(prompt: str) -> str:
        return generate_vision(prompt, image_bytes, mime)

    return prompting.generate_with_retry(
        _PROMPT,
        _RETRY_SUFFIX,
        generate,
        _to_text_region,
        TextRegionError,
    )


async def find_text_region(image_ref: str) -> TextRegion:
    """Return the safest coarse text region without blocking the caller's event loop."""

    return await asyncio.to_thread(_find_text_region_sync, image_ref)
