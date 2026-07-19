"""L0 copy drafting: Brand + assignment -> CopyBlock (DRAFT), via the free Gemini TEXT path.

The prompt is built from the versioned `copy_l0` template in mimik-knowledge — that markdown
file IS the version, and `prompt_ref` ("copy_l0@v1") records which one produced the draft.

Security (locked constraint #3): `topic` is client freeform text = UNTRUSTED. It only ever
fills the `<topic>...</topic>` data fence in the template — never a system-level directive —
and any literal topic tags the client typed are stripped so the fence can't be broken out of.
Brand fields fill constrained named slots.

House taste is enforced in code, not just asked for: the reply must be strict JSON and the
headline must fit ≤ 9 words / ≤ 60 chars. One corrective retry, then fail loud
(`CopyDraftError`) — the shared plumbing lives in `creative.prompting`.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from mimik_contracts import Brand, CopyBlock, CopyStatus, get_format
from mimik_knowledge import list_golden_exemplars

from creative import prompting

PROMPT_NAME = "copy_l0"
PROMPT_REF = f"{PROMPT_NAME}@v1"
_OVERRIDE_VAR = "MIMIK_COPY_L0_PROMPT"

_HEADLINE_MAX_WORDS = 9
_HEADLINE_MAX_CHARS = 60

# Appended to the SAME prompt for the single retry — corrective, not a new brief.
_RETRY_SUFFIX = (
    "\n\nYour previous reply was rejected: it was not one strict JSON object, or the headline "
    f"broke the hard rules (at most {_HEADLINE_MAX_WORDS} words AND at most "
    f"{_HEADLINE_MAX_CHARS} characters). Reply again with ONLY the JSON object."
)

# Literal topic tags inside client text — stripped so the data fence can't be escaped.
_TOPIC_TAG_RE = prompting.tag_stripper("topic")
# Same treatment for the pin-pointed revision instruction (also client freeform text).
_REVISION_TAG_RE = prompting.tag_stripper("revision")

# The audit header a promoted golden carries (provenance for humans, noise for the model).
# Single-line match (no DOTALL): the header is one sanitized line by construction, and a
# multi-line match would let crafted content extend "the header" into the body.
_GOLDEN_HEADER_RE = re.compile(r"^<!--\s*promoted-by:[^\n]*?-->\n?")
# The client scope is extracted as a FIELD and compared exactly — never substring-scanned,
# so content or reviewer text containing "client: <other-id>" cannot forge scope.
_GOLDEN_CLIENT_RE = re.compile(r"\bclient:\s*([A-Za-z0-9._-]+)")
_MAX_VOICE_EXAMPLES = 3


def _voice_examples(brand: Brand) -> str:
    """This brand's approved copy_voice goldens (client-scoped via the audit header),
    newest first, capped. Empty golden set is normal — the slot degrades gracefully."""
    examples: list[str] = []
    for content in list_golden_exemplars(task="copy"):
        header = _GOLDEN_HEADER_RE.match(content)
        if not header:
            continue
        scope = _GOLDEN_CLIENT_RE.search(header.group(0))
        # Only exemplars promoted from THIS client's context may shape this brand's voice.
        if not scope or scope.group(1) != brand.client_id:
            continue
        body = _GOLDEN_HEADER_RE.sub("", content).strip()
        if body:
            examples.append(body)
        if len(examples) >= _MAX_VOICE_EXAMPLES:
            break
    if not examples:
        return "(none yet — rely on the brand voice slots above)"
    return "\n\n---\n\n".join(examples)


class CopyDraftError(RuntimeError):
    """The model failed to produce house-valid copy after the corrective retry."""


def _build_prompt(
    brand: Brand,
    *,
    pillar_name: str,
    topic: str,
    format_key: str,
    language: str,
    revision_note: str | None = None,
) -> str:
    slots = {
        "brand_voice": prompting.slot(brand.brand_voice),
        "tone_keywords": prompting.join_list(brand.tone_keywords, sep=", "),
        "dos": prompting.join_list(brand.dos),
        "donts": prompting.join_list(brand.donts),
        "target_audience": prompting.slot(brand.target_audience),
        "niche": prompting.slot(brand.niche),
        "pillar": prompting.slot(pillar_name),
        "format_label": get_format(format_key).label,  # KeyError for unknown keys (fail loud)
        "language": language,
        "voice_examples": _voice_examples(brand),
        "topic": _TOPIC_TAG_RE.sub("", topic).strip(),
        "revision": _REVISION_TAG_RE.sub("", revision_note).strip()
        if revision_note
        else "(none — first draft)",
    }
    return prompting.fill_slots(prompting.load_template(PROMPT_NAME, _OVERRIDE_VAR), slots)


# Display-copy editor rules (senior-designer feedback): a headline/CTA is display type,
# not a sentence — it never ends in terminal punctuation, and semicolons never appear in
# display copy at all.
_DISPLAY_TRAILING = " .;,:"


def _edit_display(text: str, *, field: str) -> str:
    """Apply the editor pass to one display-copy field. Trailing terminal punctuation is
    stripped silently (an edit, not an error); a semicolon anywhere is a reject (retry)."""
    # Semicolon check runs on the ORIGINAL text — checking after the trailing strip would
    # silently launder the most common model mistake (a trailing ";") past the reject.
    if ";" in text:
        raise ValueError(f"{field} contains a semicolon — display copy never does: {text!r}")
    cleaned = text.strip().rstrip(_DISPLAY_TRAILING).strip()
    if not cleaned:
        raise ValueError(f"{field} is empty after the editor pass: {text!r}")
    return cleaned


def _to_copy_block(
    data: dict[str, object], *, language: str, source_model: str
) -> CopyBlock:
    headline = data.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        raise ValueError("reply has no headline")
    headline = _edit_display(headline, field="headline")
    if len(headline) > _HEADLINE_MAX_CHARS or len(headline.split()) > _HEADLINE_MAX_WORDS:
        raise ValueError(
            f"headline breaks house taste (> {_HEADLINE_MAX_WORDS} words or "
            f"> {_HEADLINE_MAX_CHARS} chars): {headline!r}"
        )
    subhead = data.get("subhead")
    cta = data.get("cta")
    return CopyBlock(
        headline=headline,
        # Optional fields: anything that isn't a non-empty string collapses to None.
        subhead=subhead.strip() if isinstance(subhead, str) and subhead.strip() else None,
        cta=_edit_display(cta, field="cta") if isinstance(cta, str) and cta.strip() else None,
        language=language,
        status=CopyStatus.DRAFT,
        source_model=source_model,
        prompt_ref=PROMPT_REF,
    )


def draft_copy(
    brand: Brand,
    pillar_name: str,
    topic: str,
    format_key: str,
    *,
    language: str = "en",
    revision_note: str | None = None,
    generate: Callable[[str], str] | None = None,
) -> CopyBlock:
    """Draft L0 copy for one creative. Sync — callers thread/queue as needed.

    `revision_note` is the pin-pointed change ask from a reviewer (client freeform =
    UNTRUSTED; it only ever fills the `<revision>` data fence) — pass it to re-draft in
    response to a targeted change request instead of starting blind. `generate` is
    injectable for tests; the default is the free Gemini TEXT wrapper with the model
    pinned up front so provenance (`source_model`) matches the call. Raises
    CopyDraftError if the model can't produce house-valid copy in two tries.
    """
    if generate is None:
        generate, source_model = prompting.default_generate()
    else:
        source_model = "injected"  # honest provenance: we can't see inside the callable

    prompt = _build_prompt(
        brand,
        pillar_name=pillar_name,
        topic=topic,
        format_key=format_key,
        language=language,
        revision_note=revision_note,
    )
    return prompting.generate_with_retry(
        prompt,
        _RETRY_SUFFIX,
        generate,
        lambda data: _to_copy_block(data, language=language, source_model=source_model),
        CopyDraftError,
    )
