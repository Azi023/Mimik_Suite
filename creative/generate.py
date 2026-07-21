"""The missing M1 seam: art-direct → generate imagery → composite → QA, in one call.

`generate_creative()` (pipeline.py) deliberately never triggers image generation — it expects
a cached L1 artifact. This module is the piece that was never wired: it art-directs a prompt,
runs it through an image backend (paid API or the fallback chain), turns the produced file into
a data-URI L1 artifact, and hands it to the pipeline for compositing + brand-QA.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path

from mimik_contracts import Brand, CopyBlock, ImageBackend, PRESETS

from creative.adapters import generate_with_fallback, get_adapter
from creative.adapters.base import ImageRequest, ImageResult
from creative.art_direction import build_image_request
from creative.copy.l0 import draft_copy
from creative.pipeline import CreativeResult, generate_creative, suggest_template


def _to_data_uri(path: str) -> str:
    b = Path(path).read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode()


async def generate_creative_with_imagery(
    brand: Brand,
    pillar_name: str,
    topic: str,
    format_key: str,
    *,
    backend: ImageBackend | None = None,
    purpose: str = "hero",
    copy_block: CopyBlock | None = None,
    generate: Callable[[str], str] | None = None,
) -> tuple[CreativeResult, ImageRequest, ImageResult | None]:
    """Full real-imagery run for one creative.

    `backend` forces a specific image backend (used for A/B); None routes through
    `generate_with_fallback` (IMAGE_BACKEND_HERO + fallback). Returns the composited result,
    the art-directed ImageRequest (prompt-DNA), and the ImageResult (None on the placeholder
    path). Copy is drafted via the free Gemini seam unless a `copy_block` is supplied.
    """
    fmt = PRESETS[format_key]
    if copy_block is None:
        copy_block = draft_copy(brand, pillar_name, topic, format_key, generate=generate)

    # Layout-FIRST (locked): pick the template before art-directing so the plate reserves the
    # right text zone. has_imagery=True — this path always produces a real plate.
    template_key = suggest_template(copy_block, format_key, has_imagery=True)

    request = build_image_request(
        brand, pillar_name, topic, fmt.label, fmt.width, fmt.height,
        template_key=template_key, generate=generate,
    )

    if backend is not None:
        image = await get_adapter(backend).generate(request)
    else:
        image = await generate_with_fallback(request, purpose=purpose)

    image_artifact = _to_data_uri(image.artifact_ref) if image is not None else None

    result = await generate_creative(
        brand, pillar_name, topic, format_key,
        template_key=template_key, copy_block=copy_block, image_artifact=image_artifact,
    )
    return result, request, image
