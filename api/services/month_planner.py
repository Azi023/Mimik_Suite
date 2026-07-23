"""Pillar-balanced monthly content planner (M-17).

Given a client's content pillars and a target volume, lay out a month of posts that:

* honours each pillar's share (explicit weights when supplied, else an even split),
* never runs the same pillar more than `MAX_CONSECUTIVE_RUN` posts in a row — the
  "no five promos in a row" guard — so the calendar stays varied,
* spreads posts with an even rhythm across the month's days (no clumping),
* is fully deterministic: the target month is a parameter and every tie-break is
  seeded by index, so there is no wall-clock or randomness. Same input → same plan.
  That makes it trivially testable and resumable, and lets it feed the Command Center
  fan-out (M-09) as its natural upstream input.

The core `plan_month` is a PURE function (no DB, no I/O): the caller supplies the pillar
list, so it can be unit-tested in isolation. `build_month_plan` is a thin, tenant-scoped
DB-facing wrapper (constraint #2) that resolves a client's adopted pillars and delegates
to the pure core.

`PlannedPost` is a small frozen model defined locally: `mimik-contracts` has no
planning/schedule contract yet and this output is not on a route. When a plan-calendar
contract lands, promote this into `mimik-contracts` and produce it instead (constraint #1).
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping, Sequence
from datetime import date

from mimik_contracts import PRESETS
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.auth import Principal, is_client_in_scope
from api.db import repo

# The whole point of the module: the maximum number of same-pillar posts allowed
# back-to-back. Two promos in a row is fine; a third starts to read as spam. Named so the
# guard is a single source of truth the tests can assert against.
MAX_CONSECUTIVE_RUN = 2

# Default format when the caller names none. Matches the Command Center default so the two
# planning surfaces agree.
_DEFAULT_FORMAT = "ig_post"


class PlannedPost(BaseModel):
    """One slot on the planned calendar. Internal (not yet on the wire), so frozen + strict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pillar: str
    publish_date: date
    topic_seed: str = Field(min_length=1)
    format_key: str


class PlanInfeasibleError(ValueError):
    """The requested mix cannot satisfy the run guard — one pillar's share is too large to
    break into runs of `MAX_CONSECUTIVE_RUN` given the other posts. Fail loud, never emit an
    unbalanced calendar that violates the invariant."""


def _normalise_weights(
    pillars: Sequence[str] | Mapping[str, float],
) -> list[tuple[str, float]]:
    """Return (pillar, weight) pairs in a stable order. A plain sequence → even weights.

    Order is the caller's order (dict insertion order preserved); duplicates and empties are
    rejected so quota maths and index tie-breaks are unambiguous."""
    if isinstance(pillars, Mapping):
        items = [(str(name), float(weight)) for name, weight in pillars.items()]
    else:
        items = [(str(name), 1.0) for name in pillars]

    if not items:
        raise ValueError("plan_month needs at least one pillar.")
    names = [name for name, _ in items]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate pillar names are not allowed: {names}")
    for name, weight in items:
        if not name.strip():
            raise ValueError("pillar names must be non-empty.")
        if weight <= 0:
            raise ValueError(f"pillar weight must be > 0, got {weight!r} for {name!r}.")
    return items


def _quota_by_pillar(
    weighted: list[tuple[str, float]], count: int
) -> dict[str, int]:
    """Split `count` posts across pillars by weight using the largest-remainder (Hamilton)
    method: floor each ideal share, then hand the leftover posts to the largest fractional
    remainders. Guarantees the quotas sum to exactly `count` and tracks the weights closely.
    Ties in the remainder are broken by pillar index (stable, deterministic)."""
    total_weight = sum(weight for _, weight in weighted)
    ideal = [(name, count * weight / total_weight) for name, weight in weighted]

    quotas = {name: int(share) for name, share in ideal}
    leftover = count - sum(quotas.values())
    # Distribute the leftover to the biggest fractional parts; index breaks ties so the result
    # is identical every run.
    order = sorted(
        range(len(ideal)),
        key=lambda i: (-(ideal[i][1] - int(ideal[i][1])), i),
    )
    for i in order[:leftover]:
        quotas[ideal[i][0]] += 1
    return quotas


def _interleave(quotas: dict[str, int]) -> list[str]:
    """Order the pooled pillar slots so no pillar appears more than `MAX_CONSECUTIVE_RUN`
    times in a row. Greedy: at each step take the pillar with the most slots left that would
    NOT create an over-long run; ties break by the pillar's original index (deterministic).

    Raises `PlanInfeasibleError` if the mix cannot satisfy the guard, so any returned sequence
    provably honours it — the invariant is never silently broken."""
    names = list(quotas)
    index_of = {name: i for i, name in enumerate(names)}

    # Feasibility: to break M posts of the dominant pillar into runs of <= k, they need
    # ceil(M/k) - 1 separators drawn from the other posts. So feasible iff, for the busiest
    # pillar, M <= k * (others + 1). When `others` is 0 there is only one pillar in the plan —
    # nothing to interleave, so the run guard is vacuous and we let it through.
    total = sum(quotas.values())
    if total:
        busiest = max(quotas.values())
        others = total - busiest
        if others and busiest > MAX_CONSECUTIVE_RUN * (others + 1):
            raise PlanInfeasibleError(
                f"a pillar with {busiest} of {total} posts cannot be spread with no more than "
                f"{MAX_CONSECUTIVE_RUN} in a row — reduce its weight or raise the post count."
            )

    remaining = dict(quotas)
    sequence: list[str] = []
    run_pillar: str | None = None
    run_len = 0
    for _ in range(total):
        # Blocked = the pillar that already fills the last MAX_CONSECUTIVE_RUN slots.
        blocked = run_pillar if run_len >= MAX_CONSECUTIVE_RUN else None
        candidates = [n for n in names if remaining[n] > 0 and n != blocked]
        # Only empty when the blocked pillar is the sole one left — the single-pillar case,
        # where there is nothing to interleave with, so we place it anyway.
        if not candidates:
            candidates = [n for n in names if remaining[n] > 0]
        pick = max(candidates, key=lambda n: (remaining[n], -index_of[n]))
        sequence.append(pick)
        remaining[pick] -= 1
        if pick == run_pillar:
            run_len += 1
        else:
            run_pillar, run_len = pick, 1
    return sequence


def _month_days(year: int, month: int) -> int:
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1..12, got {month}.")
    return calendar.monthrange(year, month)[1]


def _spread_dates(count: int, year: int, month: int) -> list[date]:
    """Pick `count` publish days spread evenly across the month, in ascending order. Day i lands
    at 1 + floor(i * days / count), so slots march across the whole month instead of clumping.
    When count > days, days repeat (multiple posts share a day) rather than spilling out of the
    month — every date is guaranteed to fall inside the target month."""
    days = _month_days(year, month)
    return [date(year, month, 1 + (i * days) // count) for i in range(count)]


def _resolve_count(
    count: int | None, posts_per_week: float | None, year: int, month: int
) -> int:
    """Exactly one of `count` / `posts_per_week` must be given. A cadence is converted to a
    whole-month total against the actual number of days, so February and March differ."""
    if (count is None) == (posts_per_week is None):
        raise ValueError("pass exactly one of count or posts_per_week.")
    if count is not None:
        if count < 1:
            raise ValueError(f"count must be >= 1, got {count}.")
        return count
    if posts_per_week <= 0:
        raise ValueError(f"posts_per_week must be > 0, got {posts_per_week}.")
    days = _month_days(year, month)
    resolved = round(posts_per_week * days / 7)
    return max(1, resolved)


def _validate_formats(allowed_formats: Sequence[str] | None) -> list[str]:
    """Formats to cycle through, validated against the preset library (fail loud on unknown
    keys, matching `formats.get_format`). None → the single default format."""
    formats = list(allowed_formats) if allowed_formats else [_DEFAULT_FORMAT]
    if not formats:
        raise ValueError("allowed_formats, if given, must be non-empty.")
    for key in formats:
        if key not in PRESETS:
            raise ValueError(
                f"unknown format_key {key!r}; known: {', '.join(sorted(PRESETS))}."
            )
    return formats


def plan_month(
    pillars: Sequence[str] | Mapping[str, float],
    *,
    year: int,
    month: int,
    count: int | None = None,
    posts_per_week: float | None = None,
    allowed_formats: Sequence[str] | None = None,
) -> list[PlannedPost]:
    """Lay out a pillar-balanced month of posts. PURE — no DB, no clock, no randomness.

    Args:
        pillars: pillar names (even split) OR a {name: weight} map (weighted split).
        year, month: the target month (1..12). Supplied, never read from the clock.
        count / posts_per_week: the volume — pass exactly one. A cadence is resolved against
            the month's real day count.
        allowed_formats: format keys to round-robin across posts; defaults to the house default.

    Returns an ascending-by-date list of `PlannedPost`. Guarantees: quotas honour the weights
    (largest-remainder), no pillar runs longer than `MAX_CONSECUTIVE_RUN`, dates spread evenly
    and all fall inside the month. Raises `PlanInfeasibleError` if the run guard is unsatisfiable.
    """
    weighted = _normalise_weights(pillars)
    resolved_count = _resolve_count(count, posts_per_week, year, month)
    formats = _validate_formats(allowed_formats)

    quotas = _quota_by_pillar(weighted, resolved_count)
    ordered_pillars = _interleave(quotas)
    dates = _spread_dates(resolved_count, year, month)

    posts: list[PlannedPost] = []
    for i, (pillar, publish_date) in enumerate(zip(ordered_pillars, dates, strict=True)):
        posts.append(
            PlannedPost(
                pillar=pillar,
                publish_date=publish_date,
                topic_seed=f"{pillar} post #{i + 1}",
                format_key=formats[i % len(formats)],
            )
        )
    return posts


async def build_month_plan(
    session: AsyncSession,
    *,
    principal: Principal,
    client_id: str,
    year: int,
    month: int,
    count: int | None = None,
    posts_per_week: float | None = None,
    allowed_formats: Sequence[str] | None = None,
) -> list[PlannedPost]:
    """Tenant-scoped DB wrapper: resolve a client's adopted pillars, then call the pure core.

    Every read is filtered by `principal.tenant_id` and the client is checked against the
    principal's scope (constraint #2 — never trust the caller-supplied client_id alone). The
    client's pillars carry no weight field today, so they feed an even split; when a per-client
    weight lands, pass a {name: weight} map here instead — the pure core already honours it."""
    if not is_client_in_scope(principal, client_id):
        raise PermissionError("client is not in this principal's scope.")

    rows = await repo.list_pillars(
        session, tenant_id=principal.tenant_id, client_id=client_id
    )
    pillar_names = [row.name for row in rows]
    if not pillar_names:
        raise ValueError(
            "client has no content pillars — adopt pillars before planning a month."
        )

    return plan_month(
        pillar_names,
        year=year,
        month=month,
        count=count,
        posts_per_week=posts_per_week,
        allowed_formats=allowed_formats,
    )
