"""Backend routing + the hard spend gate for paid image generation.

`choose_backend` maps a purpose ("dev"/"hero") to the configured ImageBackend; "none"/empty/
unset means the placeholder path (pipeline renders solid brand ground, zero spend).
`generate_with_fallback` runs the retry/fallback chain and raises ImageGenerationFailed as
the L2-human-fallback signal.

Shared paid-adapter plumbing lives here too: `ensure_spend_approved` — the
MIMIK_ALLOW_PAID_IMAGES hard guard (~$8 total credits, operator-gated; a refusal, not a
warning) — and `write_image_artifact`. Keys and env contents are never logged.
"""

from __future__ import annotations

import base64
import logging
import os
import uuid
from pathlib import Path
from typing import Literal

from mimik_contracts import ImageBackend

from .base import ImageRequest, ImageResult

logger = logging.getLogger(__name__)

_PURPOSE_ENV: dict[str, str] = {
    "dev": "IMAGE_BACKEND_PRIMARY",
    "hero": "IMAGE_BACKEND_HERO",
}
# Key env var per fallback-eligible paid backend (a backend without its key is never tried).
_KEY_ENV: dict[ImageBackend, str] = {
    ImageBackend.GPT_IMAGE: "OPENAI_API_KEY",
    ImageBackend.OPENROUTER: "OPENROUTER_API_KEY",
}


class PaidImageSpendNotApproved(RuntimeError):
    """A paid adapter was invoked without the operator's MIMIK_ALLOW_PAID_IMAGES=1 approval."""


class ImageGenerationFailed(RuntimeError):
    """Every configured backend failed — the pipeline's signal to fall back to an L2 human."""


def ensure_spend_approved(backend: ImageBackend) -> None:
    """Hard budget gate: refuse any paid image call unless the operator explicitly approved."""
    if os.environ.get("MIMIK_ALLOW_PAID_IMAGES") != "1":
        raise PaidImageSpendNotApproved(
            f"{backend.value}: paid image generation is operator-gated — "
            "set MIMIK_ALLOW_PAID_IMAGES=1 to approve real spend."
        )


def write_image_artifact(artifacts_dir: Path, backend: ImageBackend, b64_data: str) -> Path:
    """Decode base64 image bytes and land them under artifacts_dir (created on demand)."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / f"{backend.value}_{uuid.uuid4().hex}.png"
    path.write_bytes(base64.b64decode(b64_data))
    return path


def choose_backend(purpose: Literal["dev", "hero"]) -> ImageBackend | None:
    """Resolve the configured backend for a purpose; None = placeholder path (zero spend)."""
    try:
        env_var = _PURPOSE_ENV[purpose]
    except KeyError:
        raise ValueError(f"unknown image purpose: {purpose!r} (expected 'dev' or 'hero')") from None
    raw = (os.environ.get(env_var) or "").strip().lower()
    if raw in ("", "none"):
        return None
    try:
        return ImageBackend(raw)
    except ValueError:
        raise ValueError(f"{env_var}={raw!r} is not a known image backend") from None


def _alternate_paid_backend(primary: ImageBackend) -> ImageBackend | None:
    """The single paid backend to try after `primary` fails — only if its key is configured."""
    for candidate in (ImageBackend.GPT_IMAGE, ImageBackend.OPENROUTER):
        if candidate != primary and os.environ.get(_KEY_ENV[candidate]):
            return candidate
    return None


async def generate_with_fallback(
    request: ImageRequest, purpose: str = "hero"
) -> ImageResult | None:
    """Generate via the configured backend with retry-once + one paid alternate.

    None backend → None (placeholder path). Primary gets two attempts; on a second failure
    ONE alternate paid backend (key-configured) gets a single attempt — each attempt is real
    money once the spend gate is open. All failures → ImageGenerationFailed.
    """
    backend = choose_backend(purpose)  # type: ignore[arg-type]  # validated inside
    if backend is None:
        logger.info("image backend for purpose=%s is 'none' — placeholder path, zero spend", purpose)
        return None

    from . import get_adapter  # local import: the registry lives in the package root

    chain: list[ImageBackend] = [backend]
    alternate = _alternate_paid_backend(backend)
    if alternate is not None:
        chain.append(alternate)

    last_error: Exception | None = None
    for index, candidate in enumerate(chain):
        adapter = get_adapter(candidate)
        tries = 2 if index == 0 else 1
        for attempt in range(1, tries + 1):
            try:
                result = await adapter.generate(request)
            except PaidImageSpendNotApproved:
                raise  # operator gate — neither retry nor fallback can approve spend
            except (KeyError, ValueError, TypeError):
                raise  # wiring/programming bug — fail loud, don't burn paid retries on it
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "image generation via %s failed (attempt %d/%d): %s",
                    candidate.value,
                    attempt,
                    tries,
                    exc,
                )
            else:
                logger.info(
                    "image generated via %s (attempt %d, purpose=%s)",
                    candidate.value,
                    attempt,
                    purpose,
                )
                return result
    raise ImageGenerationFailed(
        f"all image backends failed for purpose={purpose!r} "
        f"(tried: {', '.join(b.value for b in chain)})"
    ) from last_error
