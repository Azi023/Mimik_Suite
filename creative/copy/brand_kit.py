"""Draft a Brand Kit narrative from one brand record via the shared free text path."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mimik_contracts import Brand, GeneratedBrandKitNarrative

from creative import prompting

PROMPT_NAME = "brand_kit_narrative"
PROMPT_REF = f"{PROMPT_NAME}@v1"
_OVERRIDE_VAR = "MIMIK_BRAND_KIT_PROMPT"
_BUNDLED_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / f"{PROMPT_NAME}.md"
_BRAND_RECORD_TAG_RE = prompting.tag_stripper("brand_record")
_RETRY_SUFFIX = (
    "\n\nYour previous reply was rejected because it was not the required strict JSON object "
    "with every discovery and direction field populated. Reply again with ONLY that JSON object."
)


class BrandKitDraftError(RuntimeError):
    """The text provider failed to return a valid Brand Kit narrative after one retry."""


@dataclass(frozen=True)
class BrandKitDraft:
    narrative: GeneratedBrandKitNarrative
    prompt_ref: str


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return _BRAND_RECORD_TAG_RE.sub("", value).strip()


def _brand_record(brand: Brand) -> str:
    """Serialize only canonical brand fields after stripping literal data-fence tags."""
    record = {
        "name": _clean(brand.name),
        "niche": _clean(brand.niche),
        "services": [_clean(item) for item in brand.services],
        "target_audience": _clean(brand.target_audience),
        "brand_voice": _clean(brand.brand_voice),
        "tone_keywords": [_clean(item) for item in brand.tone_keywords],
        "dos": [_clean(item) for item in brand.dos],
        "donts": [_clean(item) for item in brand.donts],
        "imagery_style": _clean(brand.imagery_style),
        "colors": [
            {
                "name": _clean(color.name),
                "hex": color.hex,
                "usage": _clean(color.usage),
                "display_name": _clean(color.display_name),
                "rationale": _clean(color.rationale),
            }
            for color in brand.tokens.colors
        ],
    }
    return json.dumps(record, ensure_ascii=False, indent=2)


def _load_template() -> str:
    """The mimik-knowledge prompt IS the version (same contract as copy_l0). The bundled copy is
    only a resilience fallback for a deploy where the knowledge package is unavailable."""
    try:
        return prompting.load_template(PROMPT_NAME, _OVERRIDE_VAR)
    except FileNotFoundError:
        return _BUNDLED_PROMPT.read_text(encoding="utf-8")


def _build_prompt(brand: Brand) -> str:
    return prompting.fill_slots(_load_template(), {"brand_record": _brand_record(brand)})


def draft_brand_kit(
    brand: Brand,
    *,
    generate: Callable[[str], str] | None = None,
) -> BrandKitDraft:
    """Generate the two narrative chapters with strict JSON and one corrective retry."""
    if generate is None:
        generate, _source_model = prompting.default_generate()
    narrative = prompting.generate_with_retry(
        _build_prompt(brand),
        _RETRY_SUFFIX,
        generate,
        GeneratedBrandKitNarrative.model_validate,
        BrandKitDraftError,
    )
    return BrandKitDraft(narrative=narrative, prompt_ref=PROMPT_REF)
