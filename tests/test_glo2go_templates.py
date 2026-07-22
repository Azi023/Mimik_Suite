"""Glo2Go archetypes build editable, profile-driven HTML without a browser."""

from __future__ import annotations

from pathlib import Path

from creative.render.glo2go_templates import build_glo2go_html
from creative.style_profile import get_style_profile


IMAGE_DATA_URI = "data:image/png;base64,aGk="


def _html(archetype: str, copy: dict[str, str]) -> str:
    return build_glo2go_html(
        archetype,
        image_ref=IMAGE_DATA_URI,
        copy=copy,
        format_key="ig_post",
        profile=get_style_profile("glo2go-aesthetics"),
    )


def test_single_photo_education_hero_has_profile_driven_structure() -> None:
    html = _html(
        "single_photo_education_hero",
        {
            "headline": "Skin boosters, explained",
            "sub": "Support hydration and skin quality with a consultation-led plan.",
        },
    )

    assert 'data-archetype="single_photo_education_hero"' in html
    assert 'class="g2g-badge"' in html
    assert "G2G Aesthetics" in html
    assert "g2g-panel g2g-hero-panel" in html
    assert "#5A2A6B" in html
    assert "width:1080px" in html
    assert "height:1080px" in html


def test_myth_vs_fact_split_has_two_labeled_photo_sections_and_panels() -> None:
    html = _html(
        "myth_vs_fact_split",
        {
            "headline": "Retinol: myth vs fact",
            "myth_label": "Myth",
            "myth": "Retinol always makes sensitive skin worse.",
            "fact_label": "Fact",
            "fact": "A clinician-guided routine can introduce it gradually.",
        },
    )

    assert 'data-archetype="myth_vs_fact_split"' in html
    assert html.count('class="g2g-photo"') == 2
    assert html.count("g2g-panel g2g-split-panel") == 2
    assert ">Myth<" in html
    assert ">Fact<" in html
    assert 'class="g2g-badge"' in html
    assert "#5A2A6B" in html


def test_archetypes_and_copy_densities_produce_varied_compositions() -> None:
    compact = _html(
        "single_photo_education_hero",
        {"headline": "Hydration, refined", "sub": "A calmer route to luminous skin."},
    )
    dense = _html(
        "single_photo_education_hero",
        {
            "headline": "A consultation-led approach to improving hydration and skin quality",
            "sub": (
                "Your plan should reflect your skin, treatment history, and realistic goals "
                "before any product or procedure is recommended."
            ),
        },
    )
    split = _html(
        "myth_vs_fact_split",
        {
            "headline": "Peels: myth vs fact",
            "myth_label": "Myth",
            "myth": "Stronger always means better.",
            "fact_label": "Fact",
            "fact": "The right depth depends on your skin and goals.",
        },
    )

    assert 'data-density="compact"' in compact
    assert 'data-density="dense"' in dense
    assert compact != dense
    assert compact != split


def test_local_photo_path_is_embedded_and_copy_is_escaped(tmp_path: Path) -> None:
    photo = tmp_path / "pexels-photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0unit-test-photo")

    html = build_glo2go_html(
        "single_photo_education_hero",
        image_ref=str(photo),
        copy={"headline": "<script>alert(1)</script>", "sub": "Clinical & calm"},
        format_key="ig_post",
        profile=get_style_profile("glo2go-aesthetics"),
    )

    assert "data:image/jpeg;base64," in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Clinical &amp; calm" in html


def test_generated_stylesheet_has_balanced_rule_braces() -> None:
    html = _html(
        "single_photo_education_hero",
        {"headline": "Skin confidence", "sub": "Clear guidance, thoughtfully presented."},
    )
    stylesheet = html.split("<style>", maxsplit=1)[1].split("</style>", maxsplit=1)[0]

    assert stylesheet.count("{") == stylesheet.count("}")


def test_cta_is_a_distinct_filled_plum_pill() -> None:
    html = _html(
        "single_photo_education_hero",
        {
            "headline": "A plan made for your skin",
            "sub": "Start with a clinician-led consultation.",
            "cta": "Book your consultation",
        },
    )
    stylesheet = html.split("<style>", maxsplit=1)[1].split("</style>", maxsplit=1)[0]
    cta_rule = stylesheet.split(".g2g-cta{", maxsplit=1)[1].split("}", maxsplit=1)[0]

    assert '<span class="g2g-cta"' in html
    assert "background:var(--g2g-plum)" in cta_rule
    assert "color:var(--g2g-ground)" in cta_rule
    assert "font-weight:750" in cta_rule


def test_logo_path_renders_image_in_badge_instead_of_wordmark(tmp_path: Path) -> None:
    logo = tmp_path / "glo2go-logo.png"
    logo.write_bytes(b"\x89PNG\r\n\x1a\nunit-test-logo")

    html = build_glo2go_html(
        "single_photo_education_hero",
        image_ref=IMAGE_DATA_URI,
        copy={"headline": "Skin confidence"},
        format_key="ig_post",
        profile=get_style_profile("glo2go-aesthetics"),
        logo_ref=str(logo),
    )

    assert '<img class="g2g-logo"' in html
    assert "data:image/png;base64," in html
    assert ">G2G Aesthetics<" not in html


def test_text_region_changes_hero_panel_anchor() -> None:
    default_html = _html("single_photo_education_hero", {"headline": "Default anchor"})
    top_right_html = build_glo2go_html(
        "single_photo_education_hero",
        image_ref=IMAGE_DATA_URI,
        copy={"headline": "Safe anchor"},
        format_key="ig_post",
        profile=get_style_profile("glo2go-aesthetics"),
        text_region="top_right",
    )

    default_panel = default_html.split("<section", maxsplit=1)[1].split(">", maxsplit=1)[0]
    top_right_panel = top_right_html.split("<section", maxsplit=1)[1].split(">", maxsplit=1)[0]
    assert 'data-text-region="default"' in default_panel
    assert 'data-text-region="top_right"' in top_right_panel
    assert default_panel != top_right_panel


def test_panel_uses_higher_opacity_and_feathered_shadow() -> None:
    html = _html("single_photo_education_hero", {"headline": "Integrated panel"})
    stylesheet = html.split("<style>", maxsplit=1)[1].split("</style>", maxsplit=1)[0]
    panel_rule = stylesheet.split(".g2g-panel{", maxsplit=1)[1].split("}", maxsplit=1)[0]

    assert "background:rgba(255,255,255,0.94)" in panel_rule
    assert "box-shadow:0 18px 44px" in panel_rule
    assert "0 4px 14px" in panel_rule


def test_split_allows_default_headline_and_second_image() -> None:
    second_image = "data:image/png;base64,dHdv"
    html = build_glo2go_html(
        "myth_vs_fact_split",
        image_ref=IMAGE_DATA_URI,
        image_ref_2=second_image,
        copy={
            "myth_label": "Myth",
            "myth": "Stronger always means better.",
            "fact_label": "Fact",
            "fact": "Treatment strength should match your skin.",
        },
        format_key="ig_post",
        profile=get_style_profile("glo2go-aesthetics"),
    )

    assert ">Myth vs Fact<" in html
    assert f'src="{IMAGE_DATA_URI}"' in html
    assert f'src="{second_image}"' in html
