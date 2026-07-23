"""Tests for the pillar-balanced monthly planner (M-17).

The core `plan_month` is pure, so most of this file is plain unit tests with no DB. The
invariants under test are the module's whole reason to exist:

* the target count (or cadence) is honoured,
* pillar distribution tracks the supplied weights (within largest-remainder tolerance),
* NO pillar ever runs longer than `MAX_CONSECUTIVE_RUN` — including an adversarial, heavily
  skewed mix that still has to interleave,
* every publish date falls inside the target month,
* the same input always yields the same plan (deterministic — no clock, no randomness).

A single async test exercises the tenant-scoped DB wrapper `build_month_plan`.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.core.auth import Principal
from api.db import repo
from api.db.base import Base
from api.services.month_planner import (
    MAX_CONSECUTIVE_RUN,
    PlanInfeasibleError,
    PlannedPost,
    build_month_plan,
    plan_month,
)


def _max_run(pillars: list[str]) -> int:
    """Longest streak of the same pillar in order."""
    longest = current = 0
    prev = None
    for p in pillars:
        current = current + 1 if p == prev else 1
        longest = max(longest, current)
        prev = p
    return longest


# --- count / cadence ------------------------------------------------------------------


def test_count_is_honoured() -> None:
    posts = plan_month(["Educational", "Promotional"], year=2026, month=7, count=12)
    assert len(posts) == 12
    assert all(isinstance(p, PlannedPost) for p in posts)


def test_posts_per_week_resolves_against_month_length() -> None:
    # 2 posts/week over 31 days -> round(2 * 31 / 7) = 9.
    posts = plan_month(["A", "B", "C"], year=2026, month=7, posts_per_week=2)
    assert len(posts) == 9


def test_exactly_one_of_count_or_cadence() -> None:
    with pytest.raises(ValueError):
        plan_month(["A"], year=2026, month=7)  # neither
    with pytest.raises(ValueError):
        plan_month(["A"], year=2026, month=7, count=5, posts_per_week=1)  # both


# --- weighted distribution ------------------------------------------------------------


def test_even_split_when_no_weights() -> None:
    posts = plan_month(["A", "B", "C"], year=2026, month=7, count=9)
    counts = Counter(p.pillar for p in posts)
    assert counts == {"A": 3, "B": 3, "C": 3}


def test_weights_are_honoured_within_tolerance() -> None:
    posts = plan_month(
        {"Promotional": 0.5, "Educational": 0.3, "Social Proof": 0.2},
        year=2026,
        month=7,
        count=20,
    )
    counts = Counter(p.pillar for p in posts)
    # Largest-remainder on 20 posts: exact integer shares.
    assert counts["Promotional"] == 10
    assert counts["Educational"] == 6
    assert counts["Social Proof"] == 4
    assert sum(counts.values()) == 20


# --- the run guard (the whole point) --------------------------------------------------


def test_no_run_exceeds_max_for_even_mix() -> None:
    posts = plan_month(["A", "B", "C"], year=2026, month=7, count=15)
    assert _max_run([p.pillar for p in posts]) <= MAX_CONSECUTIVE_RUN


def test_run_guard_holds_for_dominant_pillar() -> None:
    # Adversarial: one pillar owns 70% of a 10-post month. It MUST still interleave, never
    # ship five (or three) promos in a row. Promo=7, Edu=3 is the tightest feasible skew.
    posts = plan_month(
        {"Promotional": 0.7, "Educational": 0.3}, year=2026, month=7, count=10
    )
    pillars = [p.pillar for p in posts]
    assert Counter(pillars)["Promotional"] == 7
    assert _max_run(pillars) <= MAX_CONSECUTIVE_RUN


def test_infeasible_skew_fails_loud() -> None:
    # 9 of 10 posts one pillar: impossible to keep runs <= 2. Fail loud, never emit a plan
    # that breaks the invariant.
    with pytest.raises(PlanInfeasibleError):
        plan_month(
            {"Promotional": 0.9, "Educational": 0.1}, year=2026, month=7, count=10
        )


# --- dates ----------------------------------------------------------------------------


def test_all_dates_fall_within_target_month() -> None:
    posts = plan_month(["A", "B"], year=2026, month=2, count=8)  # Feb 2026 = 28 days
    for p in posts:
        assert p.publish_date.year == 2026
        assert p.publish_date.month == 2
        assert 1 <= p.publish_date.day <= 28
    # Ascending and spread (not clumped on one day).
    days = [p.publish_date for p in posts]
    assert days == sorted(days)
    assert len({d.day for d in days}) == 8


def test_leap_day_is_reachable_but_not_exceeded() -> None:
    posts = plan_month(["A"], year=2024, month=2, count=29)  # leap Feb = 29 days
    assert max(p.publish_date for p in posts) <= date(2024, 2, 29)
    assert all(p.publish_date.month == 2 for p in posts)


# --- formats --------------------------------------------------------------------------


def test_formats_round_robin_and_default() -> None:
    default = plan_month(["A"], year=2026, month=7, count=3)
    assert {p.format_key for p in default} == {"ig_post"}

    cycled = plan_month(
        ["A"], year=2026, month=7, count=4, allowed_formats=["ig_post", "ig_story"]
    )
    assert [p.format_key for p in cycled] == ["ig_post", "ig_story", "ig_post", "ig_story"]


def test_unknown_format_fails_loud() -> None:
    with pytest.raises(ValueError):
        plan_month(["A"], year=2026, month=7, count=2, allowed_formats=["not_a_format"])


# --- determinism ----------------------------------------------------------------------


def test_same_input_same_plan() -> None:
    kwargs = dict(year=2026, month=7, count=13, allowed_formats=["ig_post", "carousel"])
    a = plan_month({"A": 0.5, "B": 0.3, "C": 0.2}, **kwargs)
    b = plan_month({"A": 0.5, "B": 0.3, "C": 0.2}, **kwargs)
    assert a == b


# --- validation edges -----------------------------------------------------------------


def test_empty_and_duplicate_pillars_rejected() -> None:
    with pytest.raises(ValueError):
        plan_month([], year=2026, month=7, count=3)
    with pytest.raises(ValueError):
        plan_month(["A", "A"], year=2026, month=7, count=3)


def test_bad_month_rejected() -> None:
    with pytest.raises(ValueError):
        plan_month(["A"], year=2026, month=13, count=3)


# --- DB wrapper (tenant-scoped) -------------------------------------------------------


@pytest_asyncio.fixture
async def sessionmaker() -> async_sessionmaker:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def test_build_month_plan_uses_clients_pillars(sessionmaker) -> None:
    async with sessionmaker() as session:
        tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
        client = await repo.create_client(session, tenant_id=tenant.id, name="Glo2Go")
        for name in ("Educational", "Promotional", "Social Proof"):
            await repo.create_pillar(
                session, tenant_id=tenant.id, client_id=client.id, name=name
            )
        await session.commit()

        principal = Principal(tenant_id=tenant.id, role="team")
        posts = await build_month_plan(
            session, principal=principal, client_id=client.id, year=2026, month=7, count=9
        )

    assert len(posts) == 9
    assert {p.pillar for p in posts} == {"Educational", "Promotional", "Social Proof"}
    assert _max_run([p.pillar for p in posts]) <= MAX_CONSECUTIVE_RUN


async def test_build_month_plan_rejects_out_of_scope_client(sessionmaker) -> None:
    async with sessionmaker() as session:
        tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
        # A client-role principal bound to a DIFFERENT client must not plan this one.
        principal = Principal(tenant_id=tenant.id, role="client", client_id="other-client")
        with pytest.raises(PermissionError):
            await build_month_plan(
                session,
                principal=principal,
                client_id="target-client",
                year=2026,
                month=7,
                count=5,
            )
