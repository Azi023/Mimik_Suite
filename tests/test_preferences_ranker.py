"""The taste-ranker: scores attributes by revealed preference, and only re-orders variants
once a client has accumulated enough signals."""

from __future__ import annotations

from api.services.preferences import (
    Variant,
    attribute_scores,
    build_profile,
    build_summary,
    rank_variants,
)
from mimik_contracts import PreferenceSignal, PreferenceSource


def _sig(source: PreferenceSource, template: str, *, reason_tag=None, weight=1.0) -> PreferenceSignal:
    return PreferenceSignal(
        source=source, attributes={"template_key": template}, reason_tag=reason_tag, weight=weight
    )


def test_attribute_scores_add_and_subtract() -> None:
    signals = [
        _sig(PreferenceSource.APPROVAL, "lower_band"),
        _sig(PreferenceSource.APPROVAL, "lower_band"),
        _sig(PreferenceSource.REJECTION, "centered_hero"),
    ]
    scores = attribute_scores(signals)
    assert scores[("template_key", "lower_band")] == 2.0
    assert scores[("template_key", "centered_hero")] == -1.0


def test_rank_is_passthrough_below_threshold() -> None:
    # 3 signals << 20: not enough to trust — keep input order, score 0, inactive.
    signals = [_sig(PreferenceSource.APPROVAL, "lower_band")] * 3
    variants = [Variant(id="a", attributes={"template_key": "centered_hero"}),
                Variant(id="b", attributes={"template_key": "lower_band"})]
    result = rank_variants(signals, variants)
    assert not result.ranker_active
    assert [v.id for v in result.ranked] == ["a", "b"]  # unchanged order
    assert all(v.score == 0.0 for v in result.ranked)


def test_rank_reorders_once_active() -> None:
    # 20+ signals: lower_band strongly approved, centered_hero rejected.
    signals = (
        [_sig(PreferenceSource.APPROVAL, "lower_band")] * 15
        + [_sig(PreferenceSource.REJECTION, "centered_hero", reason_tag="too_busy")] * 6
    )
    assert len(signals) >= 20
    variants = [Variant(id="hero", attributes={"template_key": "centered_hero"}),
                Variant(id="band", attributes={"template_key": "lower_band"})]
    result = rank_variants(signals, variants)
    assert result.ranker_active
    assert result.signal_count == 21
    # The learned favourite is ranked first despite being second in input order.
    assert [v.id for v in result.ranked] == ["band", "hero"]
    assert result.ranked[0].score > result.ranked[1].score


def test_ties_keep_input_order() -> None:
    signals = [_sig(PreferenceSource.APPROVAL, "lower_band")] * 20
    # Neither variant has any scored attribute -> tie -> stable input order.
    variants = [Variant(id="x", attributes={"format_key": "ig_post"}),
                Variant(id="y", attributes={"format_key": "ig_story"})]
    result = rank_variants(signals, variants)
    assert [v.id for v in result.ranked] == ["x", "y"]


def test_profile_summary_reflects_signals() -> None:
    signals = [
        _sig(PreferenceSource.APPROVAL, "lower_band"),
        _sig(PreferenceSource.REJECTION, "centered_hero", reason_tag="logo_small"),
    ]
    profile = build_profile(tenant_id="t1", client_id="c1", signals=signals)
    assert profile.signal_count == 2
    assert not profile.ranker_active()
    assert "logo_small" in build_summary(signals)
