"""The learning loop's read side: aggregate a client's signals into a preference profile and
a heuristic taste-ranker.

Every pick/edit/rejection/approval is a `PreferenceSignal` tagged with the salient attributes
of the creative it is about (template, format, ...). We score each attribute value by its net
revealed preference — approvals/picks add, rejections subtract — and rank future variants by
the sum of their attributes' scores. The ranker only acts once a client has accumulated
`RANKER_MIN_SIGNALS`; below that there isn't enough signal, so ranking is a passthrough.

This stays entirely client-scoped. Promotion of a correction into the SHARED golden set is a
separate, human-gated path (see the promotion endpoint) — a client can never move the shared
model on their own.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from mimik_contracts import (
    RANKER_MIN_SIGNALS,
    PreferenceProfile,
    PreferenceSignal,
    PreferenceSource,
)

# How much each kind of signal moves an attribute's score. Rejection is a strong negative;
# an edit is a mild negative (kept it, but changed something); approval/pick are positives.
_SOURCE_WEIGHT: dict[PreferenceSource, float] = {
    PreferenceSource.APPROVAL: 1.0,
    PreferenceSource.PICK: 1.0,
    PreferenceSource.EDIT: -0.25,
    PreferenceSource.REJECTION: -1.0,
}


class Variant(BaseModel):
    """A candidate to rank: an opaque id plus the attributes the ranker scores against."""

    id: str
    attributes: dict[str, str] = {}


class RankedVariant(BaseModel):
    id: str
    score: float
    attributes: dict[str, str] = {}


class RankingResult(BaseModel):
    ranker_active: bool          # False -> passthrough (not enough signals yet)
    signal_count: int
    ranked: list[RankedVariant]  # best-first when active; input order when not


def attribute_scores(signals: list[PreferenceSignal]) -> dict[tuple[str, str], float]:
    """Net preference score for each (attribute-key, value) pair across the signals."""
    scores: dict[tuple[str, str], float] = {}
    for sig in signals:
        delta = _SOURCE_WEIGHT.get(sig.source, 0.0) * sig.weight
        if delta == 0.0:
            continue
        for key, value in sig.attributes.items():
            scores[(key, value)] = scores.get((key, value), 0.0) + delta
    return scores


def build_summary(signals: list[PreferenceSignal]) -> str:
    """A short, human-readable read on what this client tends to prefer."""
    if not signals:
        return "No preference signals yet."
    counts = Counter(s.source.value for s in signals)
    parts = [f"{n} {name}" for name, n in counts.most_common()]
    reasons = Counter(s.reason_tag for s in signals if s.reason_tag)
    if reasons:
        top_reason, _ = reasons.most_common(1)[0]
        parts.append(f"top rejection reason: {top_reason}")
    scores = attribute_scores(signals)
    liked = sorted(
        ((v, s) for (k, v), s in scores.items() if k == "template_key" and s > 0),
        key=lambda kv: kv[1],
        reverse=True,
    )
    if liked:
        parts.append(f"favours template {liked[0][0]}")
    return "; ".join(parts) + "."


def build_profile(
    *, tenant_id: str, client_id: str, signals: list[PreferenceSignal]
) -> PreferenceProfile:
    """Aggregate a client's signals into their preference profile (summary + the raw signals)."""
    return PreferenceProfile(
        tenant_id=tenant_id,
        client_id=client_id,
        signals=signals,
        summary=build_summary(signals),
    )


def rank_variants(
    signals: list[PreferenceSignal],
    variants: list[Variant],
    *,
    min_signals: int = RANKER_MIN_SIGNALS,
) -> RankingResult:
    """Rank variants by the client's revealed preference. Passthrough below the signal
    threshold (stable input order, all scores 0) so a thin history never mis-sorts work."""
    active = len(signals) >= min_signals
    if not active:
        ranked = [RankedVariant(id=v.id, score=0.0, attributes=v.attributes) for v in variants]
        return RankingResult(ranker_active=False, signal_count=len(signals), ranked=ranked)

    scores = attribute_scores(signals)
    scored = [
        RankedVariant(
            id=v.id,
            score=round(sum(scores.get((k, val), 0.0) for k, val in v.attributes.items()), 4),
            attributes=v.attributes,
        )
        for v in variants
    ]
    # Stable sort by score desc: ties keep input order (Python's sort is stable).
    scored.sort(key=lambda rv: rv.score, reverse=True)
    return RankingResult(ranker_active=True, signal_count=len(signals), ranked=scored)
