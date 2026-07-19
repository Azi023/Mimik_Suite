"""Creative study: one stored image -> `AssetStudy` (the machine-usable style memory).

The study is evidence-bound by prompt AND enforced in code: hexes are shape-validated
(invalid ones dropped, never "fixed"), complexity outside the taxonomy collapses to None,
and the reply must be strict JSON — one corrective retry, then fail loud
(`CreativeStudyError`), via the shared plumbing in `creative.prompting`.

Text visible inside a studied image is the brand's own published copy = DATA. It is
transcribed into `copy_text` (the voice sample) and never treated as instructions.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from mimik_contracts import AssetStudy

from creative import prompting
from creative.vision.gemini_vision import generate_vision

PROMPT_NAME = "creative_study"
PROMPT_REF = f"{PROMPT_NAME}@v1"
_OVERRIDE_VAR = "MIMIK_CREATIVE_STUDY_PROMPT"

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_MAX_PALETTE = 6
_COMPLEXITIES = {"minimal", "moderate", "busy"}

_RETRY_SUFFIX = (
    "\n\nYour previous reply was rejected: it was not one strict JSON object matching the "
    "output spec. Reply again with ONLY the JSON object."
)


class CreativeStudyError(RuntimeError):
    """The model failed to produce a coherent study after the corrective retry."""


def _clean_str(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _to_study(data: dict[str, object]) -> AssetStudy:
    palette_raw = data.get("palette")
    palette: list[str] = []
    if isinstance(palette_raw, list):
        # Invalid hexes are dropped, not repaired — an invented color is worse than a gap.
        palette = [p.strip() for p in palette_raw if isinstance(p, str) and _HEX_RE.match(p.strip())]
    complexity = data.get("complexity")
    return AssetStudy(
        mood=_clean_str(data.get("mood")),
        palette=palette[:_MAX_PALETTE],
        composition=_clean_str(data.get("composition")),
        lighting=_clean_str(data.get("lighting")),
        complexity=complexity if complexity in _COMPLEXITIES else None,
        copy_text=_clean_str(data.get("copy_text")),
        logo_assessment=_clean_str(data.get("logo_assessment")),
        notes=_clean_str(data.get("notes")),
    )


def study_creative(
    image_bytes: bytes,
    mime: str,
    *,
    generate: Callable[[str], str] | None = None,
) -> AssetStudy:
    """Study ONE image. Sync — callers thread/queue as needed.

    `generate` is injectable for tests (a prompt->reply callable); the default closes over
    the image and calls the free Gemini VISION client. Raises CreativeStudyError if the
    model can't produce a coherent study in two tries.
    """
    if generate is None:
        def generate(prompt: str) -> str:
            return generate_vision(prompt, image_bytes, mime)

    prompt = prompting.load_template(PROMPT_NAME, _OVERRIDE_VAR)
    return prompting.generate_with_retry(
        prompt, _RETRY_SUFFIX, generate, _to_study, CreativeStudyError
    )
