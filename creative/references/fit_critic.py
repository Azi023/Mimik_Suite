"""Reference fit-critic: scraped reference + brand + content context -> FitVerdict.

Vetted references become a style descriptor (mood/palette/composition/lighting/complexity)
that shapes the generation prompt — references guide STYLE, the brief guides BRAND,
copy + layout guide STRUCTURE; a reference is never reproduced. The critic scores each
candidate against the `reference_fit` rubric AND states its reasoning; a human approves
the final set (`vet_references` returns every verdict — nothing is silently dropped).

Security (locked constraint #3): reference metadata and content context are UNTRUSTED
scraped text. They only ever fill the `<reference>`/`<context>` data fences in the
template — never a system-level directive — and any literal fence tags inside them are
stripped so the fences can't be broken out of. Brand fields fill constrained named slots.

Coherence is enforced in code, not just asked for: the reply must be strict JSON,
`fit_score` is clamped into [0, 1], and `fits=true` requires the clamped score >= 0.5 plus
non-empty reasoning. One corrective retry, then fail loud (`ReferenceCriticError`) — the
shared plumbing lives in `creative.prompting`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ValidationError

from mimik_contracts import Brand, Reference

from creative import prompting

PROMPT_NAME = "reference_fit"
PROMPT_REF = f"{PROMPT_NAME}@v1"
_OVERRIDE_VAR = "MIMIK_REFERENCE_FIT_PROMPT"

_FIT_THRESHOLD = 0.5
_NOTE_MAX_CHARS = 300

# Appended to the SAME prompt for the single retry — corrective, not a new brief.
_RETRY_SUFFIX = (
    "\n\nYour previous reply was rejected: it was not one strict JSON object, or the verdict "
    f"was incoherent (fits=true requires fit_score >= {_FIT_THRESHOLD} AND non-empty "
    "reasoning). Reply again with ONLY the JSON object."
)

# Literal fence tags inside untrusted scraped text — stripped so the data fences hold.
_FENCE_TAG_RE = prompting.tag_stripper("reference", "context")


class StyleDescriptor(BaseModel):
    """The reusable style output of a fitting reference — what actually shapes the prompt."""

    mood: str
    palette: list[str]
    composition: str
    lighting: str
    complexity: Literal["minimal", "moderate", "busy"]
    notes: str | None = None


class FitVerdict(BaseModel):
    """One critic verdict: score + human-actionable reasoning (+ style when it fits)."""

    fit_score: float
    fits: bool
    reasoning: str
    style: StyleDescriptor | None = None


class ReferenceCriticError(RuntimeError):
    """The model failed to produce a coherent verdict after the corrective retry."""


def _sanitize(text: str) -> str:
    """Strip literal fence tags from untrusted text so the data fences can't be escaped."""
    return _FENCE_TAG_RE.sub("", text).strip()


def _render_reference(reference_meta: dict[str, str]) -> str:
    """Scraped fields as sanitized `key: value` lines — tolerant of missing/empty keys."""
    lines = [
        f"{_sanitize(key)}: {_sanitize(value)}"
        for key, value in reference_meta.items()
        if value and value.strip()
    ]
    return "\n".join(lines) or "(no metadata)"


def _build_prompt(brand: Brand, *, reference_meta: dict[str, str], content_context: str) -> str:
    slots = {
        "brand_voice": prompting.slot(brand.brand_voice),
        "niche": prompting.slot(brand.niche),
        "imagery_style": prompting.slot(brand.imagery_style),
        "dos": prompting.join_list(brand.dos),
        "donts": prompting.join_list(brand.donts),
        "context": _sanitize(content_context) or "(not specified)",
        "reference": _render_reference(reference_meta),
    }
    return prompting.fill_slots(prompting.load_template(PROMPT_NAME, _OVERRIDE_VAR), slots)


def _to_verdict(data: dict[str, object]) -> FitVerdict:
    score = data.get("fit_score")
    if isinstance(score, bool) or not isinstance(score, int | float):
        raise ValueError(f"fit_score is not a number: {score!r}")
    data = {**data, "fit_score": min(1.0, max(0.0, float(score)))}  # clamp into [0, 1]
    try:
        verdict = FitVerdict.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"reply failed schema validation: {exc}") from exc
    # Coherence enforced in code: a "fits" verdict must clear the threshold AND carry
    # reasoning a human reviewer can act on.
    if verdict.fits and (verdict.fit_score < _FIT_THRESHOLD or not verdict.reasoning.strip()):
        raise ValueError(
            f"incoherent verdict: fits=true with fit_score={verdict.fit_score} "
            f"and reasoning={verdict.reasoning!r}"
        )
    return verdict


def assess_reference(
    brand: Brand,
    reference_meta: dict[str, str],
    content_context: str,
    *,
    generate: Callable[[str], str] | None = None,
) -> FitVerdict:
    """Judge ONE scraped reference against the brand + content context. Sync — callers
    thread/queue as needed.

    `reference_meta` carries whatever the scraper found ({"url", "source", "title",
    "description", "palette_hint", ...}) — missing keys are fine. `generate` is injectable
    for tests; the default is the free Gemini TEXT wrapper. Raises ReferenceCriticError if
    the model can't produce a coherent verdict in two tries.
    """
    if generate is None:
        generate, _ = prompting.default_generate()

    prompt = _build_prompt(brand, reference_meta=reference_meta, content_context=content_context)
    return prompting.generate_with_retry(
        prompt, _RETRY_SUFFIX, generate, _to_verdict, ReferenceCriticError
    )


def vet_references(
    brand: Brand,
    references: list[dict[str, str]],
    content_context: str,
    *,
    generate: Callable[[str], str] | None = None,
) -> list[tuple[dict[str, str], FitVerdict]]:
    """Assess every candidate and return ALL of them, verdict-paired, in input order.

    Rejects are returned too, never silently dropped — the HUMAN approves the set, and a
    reject's reasoning is exactly what they need to overrule or confirm it.
    """
    return [
        (meta, assess_reference(brand, meta, content_context, generate=generate))
        for meta in references
    ]


def to_contract_reference(reference_meta: dict[str, str], verdict: FitVerdict) -> Reference:
    """Approved verdict -> the contract `Reference` stored on the Brand.

    KeyError for a url-less ref (fail loud): a contract Reference is meaningless without one.
    The reasoning becomes the vetting note, truncated to fit a human-scannable card.
    """
    source = reference_meta.get("source")
    note = verdict.reasoning.strip()[:_NOTE_MAX_CHARS]
    return Reference(
        url=reference_meta["url"],
        source=source.strip() if source and source.strip() else None,
        fit_score=verdict.fit_score,
        note=note or None,
    )
