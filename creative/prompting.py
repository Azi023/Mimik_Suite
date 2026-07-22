"""Shared prompt plumbing for the LLM critics (L0 copy, reference fit, future critics).

One implementation of: versioned-template loading, literal slot filling, untrusted-text
fencing, strict-JSON reply parsing, and the two-attempt corrective-retry loop. Each critic
keeps only its own slots, validators, and error type.

Security (locked constraint #3): untrusted text (client freeform, scraped web content) only
ever fills a data fence (`<tag>...</tag>`) whose template marks it data-never-instructions.
`tag_stripper` removes literal fence tags from the untrusted text — including spaced
(`< / topic >`) and attribute (`<topic x=1>`) variants — so the fence can't be broken out of.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from mimik_knowledge import load_prompt

T = TypeVar("T")

logger = logging.getLogger(__name__)

# ```json ... ``` (or bare ```) wrapping the whole reply — models add these despite the ask.
_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*(.*?)\s*```$", re.DOTALL)


def tag_stripper(*names: str) -> re.Pattern[str]:
    """Pattern matching literal data-fence tags for `names`, tolerant of the evasive forms:
    any case, internal whitespace (`< / topic >`), and attributes (`<topic x=1>`)."""
    joined = "|".join(re.escape(n) for n in names)
    return re.compile(rf"<\s*/?\s*(?:{joined})\b[^>]*>", re.IGNORECASE)


def load_template(prompt_name: str, override_var: str) -> str:
    """Versioned prompt body, loaded at call time (edits land without a restart).

    `override_var` names an env var holding a file-path override; both paths share the
    loader's fail-loud contract (FileNotFoundError if missing).
    """
    override = os.environ.get(override_var)
    if override:
        return Path(override).read_text(encoding="utf-8")
    return load_prompt(prompt_name).body


def slot(value: str | None) -> str:
    return value.strip() if value and value.strip() else "(not specified)"


def join_list(items: list[str], sep: str = "; ") -> str:
    return sep.join(i.strip() for i in items if i.strip()) or "(none)"


def fill_slots(template: str, slots: dict[str, str]) -> str:
    # Literal per-slot replace, NOT str.format: the template legitimately contains JSON
    # braces in its output spec, and untrusted text must never be format-interpolated.
    for name, value in slots.items():
        template = template.replace("{" + name + "}", value)
    return template


def parse_json_reply(reply: str) -> dict[str, object]:
    """Strict-JSON reply → dict; ValueError (incl. JSONDecodeError) on anything else."""
    text = reply.strip()
    fenced = _CODE_FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")
    return data


def default_generate() -> tuple[Callable[[str], str], str]:
    """Return an env-ordered text-provider chain and its best-effort provenance label."""
    # Imported here, not at module level: creative.copy imports this module, so a
    # top-level import back into creative.copy is a circular-import trap whose failure
    # depends on which package a test file happens to import first.
    from creative.copy import gemini_text, openai_text, openrouter_text

    order = tuple(
        name.strip().casefold()
        for name in os.environ.get(
            "TEXT_BACKEND_ORDER",
            "gemini,openrouter,openai",
        ).split(",")
        if name.strip()
    )
    providers = {
        "gemini": ("GEMINI_API_KEY", gemini_text.generate_text),
        "openrouter": ("OPENROUTER_API_KEY", openrouter_text.generate_text),
        "openai": ("OPENAI_API_KEY", openai_text.generate_text),
    }

    def generate(prompt: str) -> str:
        last_error: RuntimeError | OSError | None = None
        for provider_name in order:
            provider = providers.get(provider_name)
            if provider is None:
                logger.warning("Unknown text provider '%s'; skipping", provider_name)
                continue
            key_env, provider_generate = provider
            if not os.environ.get(key_env):
                continue
            try:
                return provider_generate(prompt)
            except (RuntimeError, OSError) as exc:
                last_error = exc
                logger.warning("Text provider '%s' failed: %s", provider_name, exc)
        if last_error is not None:
            raise last_error
        raise RuntimeError("No configured text provider has an API key")

    return generate, f"chain:{','.join(order)}"


def generate_with_retry(
    prompt: str,
    retry_suffix: str,
    generate: Callable[[str], str],
    convert: Callable[[dict[str, object]], T],
    error: type[Exception],
) -> T:
    """Two attempts — the original prompt, then one corrective retry — validated by
    `convert` (which raises ValueError on a non-compliant reply). A model that can't
    comply twice is a failure, not something to loop on: raises `error`."""
    last_error: Exception | None = None
    for attempt in (prompt, prompt + retry_suffix):
        try:
            return convert(parse_json_reply(generate(attempt)))
        except ValueError as exc:
            last_error = exc
    raise error(f"reply rejected after corrective retry: {last_error}") from last_error
