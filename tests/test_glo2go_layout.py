"""Shared Glo2Go layout decisions stay deterministic and rubric-traceable."""

from __future__ import annotations


def test_badge_theme_uses_luminance_threshold_and_safe_default() -> None:
    from creative.render.glo2go_layout import badge_theme

    assert badge_theme(None) == "plum"
    assert badge_theme(0.9) == "plum"
    assert badge_theme(0.1) == "light"
