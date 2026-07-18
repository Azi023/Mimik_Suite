"""Layout-template library: renders clean HTML at exact format size, escapes copy, and only
scrims on request."""

from __future__ import annotations

import pytest

from creative.render.templates import (
    TemplateContext,
    available_templates,
    get_template,
)


def _ctx(**over: object) -> TemplateContext:
    base = dict(
        format_key="ig_post",
        headline="Skin boosters, explained",
        cta="Book a consult",
        image_ref="https://assets.example/base.png",
        logo_ref="https://assets.example/logo.svg",
    )
    base.update(over)
    return TemplateContext(**base)  # type: ignore[arg-type]


def test_registry_has_both_templates() -> None:
    keys = {t["key"] for t in available_templates()}
    assert {"centered_hero", "lower_band"} <= keys


def test_unknown_template_raises() -> None:
    with pytest.raises(KeyError):
        get_template("nope")


def test_render_at_exact_format_size() -> None:
    html = get_template("centered_hero").render(_ctx())
    # ig_post is 1080x1080 — the canvas must be exactly that.
    assert "width:1080px" in html and "height:1080px" in html


def test_headline_and_cta_present_and_logo_embedded() -> None:
    html = get_template("centered_hero").render(_ctx())
    assert "Skin boosters, explained" in html
    assert "Book a consult" in html
    assert "logo.svg" in html


def test_copy_is_html_escaped() -> None:
    # Copy is AI/human text — it must never inject markup into the canvas.
    html = get_template("centered_hero").render(_ctx(headline="<script>x</script> & co"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp; co" in html


def test_scrim_only_when_requested() -> None:
    without = get_template("centered_hero").render(_ctx(scrim=False))
    withs = get_template("centered_hero").render(_ctx(scrim=True))
    assert "linear-gradient" not in without
    assert "linear-gradient" in withs


def test_lower_band_keeps_text_off_imagery() -> None:
    # The band is a separate solid region below the image — legibility by construction.
    html = get_template("lower_band").render(_ctx(primary="#2E5BFF"))
    assert "#2E5BFF" in html  # brand band color used
    assert "Skin boosters, explained" in html


def test_no_image_falls_back_to_brand_ground() -> None:
    # Without imagery the hero must still be renderable (uses the brand primary as ground).
    html = get_template("centered_hero").render(_ctx(image_ref=None, primary="#2E5BFF"))
    assert "#2E5BFF" in html
    assert "url(" not in html  # no broken image url when none supplied
