"""Command Center — the operator's natural-language cockpit (A-05 / M-09).

An operator types "generate 5 Educational posts for Glo2Go this week" and it fans out into
queued generation jobs. This module turns that free text into the constrained `CommandPlan`
contract and (on confirm) enqueues the jobs through the EXISTING A-03 queue path.

Trust model (constraint #3 nuance): this is OPERATOR input — team-gated, internal — not
untrusted client text. But it is still parsed into the constrained `CommandPlan` schema and
NEVER fed into a system prompt or executed as an instruction. The parse below is fully
deterministic (regex + case-insensitive / fuzzy match against real tenant DB values). If an
LLM extraction seam is ever added it must emit strictly into `CommandPlan` (structured output),
never free execution — the executor only ever loops over the resolved, validated plan.

Unresolvable references (unknown client, missing count, out-of-range count) raise
`CommandParseError` → a clear 422, never a guess. Non-fatal ambiguities (defaulted format,
unrecognised timeframe) surface as `CommandPlan.warnings` so the operator can confirm or retype.
"""

from __future__ import annotations

import difflib
import re
from datetime import date, timedelta

from mimik_contracts import (
    PILLAR_PRESETS,
    PRESETS,
    CommandExecutionResult,
    CommandPlan,
    GenerationQueueItem,
)
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal
from api.db import repo
from api.services.generation_queue import enqueue_generation

# CommandPlan.count is bounded ge=1, le=20 — enforce the ceiling here so we raise a friendly
# error instead of a pydantic ValidationError deep in construction.
_MAX_COUNT = 20

# Spelled-out counts we accept. "a"/"an" are deliberately excluded — too ambiguous to read as a
# count ("posts for a client") — the operator must give a real number word or digit.
_NUMBER_WORDS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

# Format keyword → PRESETS key. Checked most-specific-first (see _resolve_format) so
# "facebook post" resolves to fb_post rather than the generic ig_post "post".
_FORMAT_ALIASES: tuple[tuple[str, str], ...] = (
    ("facebook post", "fb_post"),
    ("fb post", "fb_post"),
    ("story", "ig_story"),
    ("stories", "ig_story"),
    ("poster", "poster_a"),
    ("carousel", "carousel"),
    ("instagram post", "ig_post"),
    ("ig post", "ig_post"),
    ("post", "ig_post"),
)
_DEFAULT_FORMAT = "ig_post"

# A standalone integer: not glued to letters/digits, so the "2" inside "Glo2Go" is never read
# as a count. \w spans letters+digits+underscore, so a boundary only exists at real separators.
_COUNT_DIGIT = re.compile(r"(?<!\w)(\d+)(?!\w)")


class CommandParseError(Exception):
    """A command could not be resolved into a valid plan (unknown client, missing count, …).

    Carries a human-readable message the router maps to HTTP 422 — never a silent guess.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _extract_count(text: str) -> int:
    """First standalone number in the command (digit or spelled-out word). Raises if none or
    out of the CommandPlan 1..20 range."""
    digit = _COUNT_DIGIT.search(text)
    word_hit: tuple[int, int] | None = None  # (position, value)
    for word, value in _NUMBER_WORDS.items():
        match = re.search(rf"\b{word}\b", text, flags=re.IGNORECASE)
        if match and (word_hit is None or match.start() < word_hit[0]):
            word_hit = (match.start(), value)

    if digit and word_hit:
        count = int(digit.group(1)) if digit.start() < word_hit[0] else word_hit[1]
    elif digit:
        count = int(digit.group(1))
    elif word_hit:
        count = word_hit[1]
    else:
        raise CommandParseError(
            "Could not determine how many creatives to generate — start with a number, "
            "e.g. 'generate 5 …'."
        )

    if count < 1:
        raise CommandParseError("Count must be at least 1.")
    if count > _MAX_COUNT:
        raise CommandParseError(f"Count must be between 1 and {_MAX_COUNT} (got {count}).")
    return count


async def _resolve_client(
    session: AsyncSession, *, principal: Principal, text: str
) -> tuple[str, str]:
    """Resolve a client NAME in the command to (client_id, client_name), scoped to the
    operator's tenant. Only this tenant's clients are ever considered — a command naming
    another tenant's client simply fails to match (IDOR defence, constraint #2)."""
    clients = await repo.list_clients(session, tenant_id=principal.tenant_id)
    if not clients:
        raise CommandParseError("No clients exist for this tenant yet.")

    low = text.lower()
    # Prefer a direct name mention; on ties the longest (most specific) name wins.
    substring_hits = [c for c in clients if c.name.lower() in low]
    if substring_hits:
        best = max(substring_hits, key=lambda c: len(c.name))
        return best.id, best.name

    # No literal mention — try a fuzzy match on whatever follows "for".
    for_match = re.search(r"\bfor\s+(.+?)(?:\s+this\b|\s+next\b|\s+today\b|$)", text, re.IGNORECASE)
    candidate = for_match.group(1).strip() if for_match else text
    by_name = {c.name.lower(): c for c in clients}
    close = difflib.get_close_matches(candidate.lower(), list(by_name), n=1, cutoff=0.6)
    if close:
        hit = by_name[close[0]]
        return hit.id, hit.name

    known = ", ".join(sorted(c.name for c in clients))
    raise CommandParseError(f"Unknown client in command. Known clients: {known}.")


async def _resolve_pillar(
    session: AsyncSession, *, principal: Principal, client_id: str, text: str
) -> str | None:
    """Match a pillar by name against the preset library AND the client's adopted pillars.
    Optional — returns None when no pillar word is present."""
    low = text.lower()
    candidates: list[str] = [p.name for p in PILLAR_PRESETS]
    key_to_name = {p.key: p.name for p in PILLAR_PRESETS}
    adopted = await repo.list_pillars(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    candidates.extend(p.name for p in adopted)

    # Longest names first so "Behind the Scenes" beats a stray "Scenes"-like partial.
    for name in sorted(set(candidates), key=len, reverse=True):
        if name.lower() in low:
            return name
    for key, name in key_to_name.items():
        if re.search(rf"\b{re.escape(key)}\b", low):
            return name
    return None


def _resolve_format(text: str, warnings: list[str]) -> str:
    low = text.lower()
    for alias, key in _FORMAT_ALIASES:
        if alias in low:
            return key
    warnings.append(
        f"No format keyword found — defaulted to {_DEFAULT_FORMAT} "
        f"({PRESETS[_DEFAULT_FORMAT].label})."
    )
    return _DEFAULT_FORMAT


def _resolve_window(text: str, warnings: list[str]) -> tuple[date | None, date | None]:
    """Map a timeframe phrase to a publish-date window. Deterministic against today."""
    low = text.lower()
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if "this week" in low:
        return monday, monday + timedelta(days=6)
    if "next week" in low:
        next_monday = monday + timedelta(days=7)
        return next_monday, next_monday + timedelta(days=6)
    if "today" in low:
        return today, today
    if "tomorrow" in low:
        return today + timedelta(days=1), today + timedelta(days=1)
    if "this month" in low:
        first = today.replace(day=1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        return first, next_month - timedelta(days=1)
    return None, None


def _build_topics(count: int, *, pillar: str | None, text: str) -> list[str]:
    """One topic seed per creative. An explicit 'about X' clause wins; otherwise the pillar
    name (or a neutral fallback) seeds every topic. Numbered when count > 1 so the queue and
    board stay legible. Every topic is non-blank — enqueue_generation rejects blank topics."""
    about = re.search(r"\babout\s+(.+?)(?:\s+for\b|\s+this\b|\s+next\b|\s+today\b|$)", text, re.IGNORECASE)
    if about and about.group(1).strip():
        base = " ".join(about.group(1).split())
    elif pillar:
        base = f"{pillar} post"
    else:
        base = "Untitled post"
    if count == 1:
        return [base]
    return [f"{base} #{index}" for index in range(1, count + 1)]


async def build_plan(
    session: AsyncSession, *, principal: Principal, text: str
) -> CommandPlan:
    """Parse an operator command into a constrained, DB-resolved CommandPlan (the dry-run
    preview). Raises CommandParseError for anything unresolvable — never guesses."""
    warnings: list[str] = []
    count = _extract_count(text)
    client_id, client_name = await _resolve_client(session, principal=principal, text=text)
    pillar = await _resolve_pillar(
        session, principal=principal, client_id=client_id, text=text
    )
    if pillar is None:
        warnings.append("No content pillar recognised — creatives will be untagged.")
    format_key = _resolve_format(text, warnings)
    window_start, window_end = _resolve_window(text, warnings)
    if window_start is None:
        warnings.append("No timeframe recognised — jobs created without a scheduled window.")
    topics = _build_topics(count, pillar=pillar, text=text)

    return CommandPlan(
        intent="generate_batch",
        client_id=client_id,
        client_name=client_name,
        count=count,
        pillar=pillar,
        format_key=format_key,
        topics=topics,
        window_start=window_start,
        window_end=window_end,
        warnings=warnings,
    )


async def execute_plan(
    session: AsyncSession, *, principal: Principal, text: str
) -> CommandExecutionResult:
    """Re-parse the command under the operator's tenant scope, then enqueue one generation job
    per creative via the EXISTING A-03 queue path (never a reimplementation). Re-parsing (rather
    than trusting a posted plan) keeps the resolve step server-side, so no hand-crafted client_id
    can cross a tenant boundary. Each enqueued job is tenant-scoped + audited (actor + ts) inside
    enqueue_generation (constraints #2, #8)."""
    plan = await build_plan(session, principal=principal, text=text)
    queued: list[GenerationQueueItem] = []
    for topic in plan.topics:
        item = await enqueue_generation(
            session,
            principal=principal,
            client_id=plan.client_id,
            topic=topic,
            pillar=plan.pillar,
            format_key=plan.format_key,
        )
        queued.append(item)
    return CommandExecutionResult(queued=queued)
