"""Simply Nikah render family: layered vector SVG, exact-dims PNG, and structural modesty QA."""

from __future__ import annotations

import hashlib
import struct
import zlib
from xml.etree import ElementTree

import pytest

from creative.render.compositor import browser_available, png_size
from creative.render.nikah_templates import (
    NikahTemplateContext,
    build_nikah_svg,
    modesty_report,
    render_nikah,
)

_SVG_NS = "http://www.w3.org/2000/svg"
_LAYER_IDS = (
    "layer-background",
    "layer-motif",
    "layer-glow",
    "layer-hero",
    "layer-wordmark",
    "layer-headline",
    "layer-highlight-word",
    "layer-support",
    "layer-cta",
)

# (format_key, expected width, expected height) — the three launch formats the spec covers.
_FORMATS = (
    ("carousel", 1080, 1350),  # 4:5 reference
    ("ig_post", 1080, 1080),   # 1:1
    ("ig_story", 1080, 1920),  # 9:16
)

_HIGHLIGHT_COPY = {
    "headline": "Marry with the RIGHT intention",
    "highlight": "RIGHT",
    "sub": "A gentle, faith-led beginning for two families.",
    "cta": "Start your nikah",
}
_PROTECTION_COPY = {
    "headline": "Protected from the very first hello",
    "sub": "Your privacy is guarded at every step.",
    "cta": "Learn how",
}
_AYAH_COPY = {
    "ayah": "وَمِنْ آيَاتِهِ أَنْ خَلَقَ لَكُم مِّنْ أَنفُسِكُمْ أَزْوَاجًا",
    "translation": "And among His signs is that He created for you spouses from among yourselves.",
    "cta": "Begin with intention",
}


def _idat_distinct_bytes(png: bytes) -> int:
    """Distinct byte count of the decompressed IDAT stream — a PIL-free non-blank signal.

    A solid single-colour PNG decompresses to a near-uniform stream (~6 distinct bytes); a real
    render of text + vector shapes saturates it (hundreds).
    """
    index = 8
    idat = bytearray()
    while index < len(png):
        length = struct.unpack(">I", png[index : index + 4])[0]
        chunk_type = png[index + 4 : index + 8]
        if chunk_type == b"IDAT":
            idat += png[index + 8 : index + 8 + length]
        index += 12 + length
    return len(set(zlib.decompress(bytes(idat))))


# ---------------------------------------------------------------------------------------------
# Exact-dims, non-blank PNG (browser-gated, like the glo2go/compositor PNG tests)
# ---------------------------------------------------------------------------------------------


@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
@pytest.mark.parametrize("format_key,width,height", _FORMATS)
async def test_highlighted_word_hero_renders_nonblank_png(format_key: str, width: int, height: int) -> None:
    png = await render_nikah(
        "highlighted_word_hero", copy=_HIGHLIGHT_COPY, format_key=format_key, hero_symbol="hands_heart"
    )
    assert png_size(png) == (width, height)
    assert _idat_distinct_bytes(png) > 50  # not a blank canvas


@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
@pytest.mark.parametrize("format_key,width,height", _FORMATS)
async def test_protection_symbol_hero_renders_nonblank_png(format_key: str, width: int, height: int) -> None:
    png = await render_nikah(
        "protection_symbol_hero", copy=_PROTECTION_COPY, format_key=format_key, hero_symbol="shield_crescent"
    )
    assert png_size(png) == (width, height)
    assert _idat_distinct_bytes(png) > 50


@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
@pytest.mark.parametrize("format_key,width,height", _FORMATS)
async def test_ayah_translation_renders_nonblank_png(
    format_key: str,
    width: int,
    height: int,
) -> None:
    png = await render_nikah(
        "ayah_translation",
        copy=_AYAH_COPY,
        format_key=format_key,
        direction="rtl",
    )
    assert png_size(png) == (width, height)
    assert _idat_distinct_bytes(png) > 50


# ---------------------------------------------------------------------------------------------
# Layered SVG contract (no browser needed)
# ---------------------------------------------------------------------------------------------


def test_svg_emits_the_nine_named_layers_for_both_archetypes() -> None:
    for archetype, copy, hero in (
        ("highlighted_word_hero", _HIGHLIGHT_COPY, "hands_heart"),
        ("protection_symbol_hero", _PROTECTION_COPY, "shield_crescent"),
    ):
        svg = build_nikah_svg(archetype, copy=copy, format_key="carousel", hero_symbol=hero)
        for layer_id in _LAYER_IDS:
            assert f'id="{layer_id}"' in svg, (archetype, layer_id)
            assert f'data-layer="{layer_id}"' in svg
            assert f'inkscape:label="{layer_id}"' in svg
        assert svg.count('inkscape:groupmode="layer"') == 9
        assert svg.count('data-editable="true"') == 9
        assert svg.count("data-bbox=") == 9


def test_nikah_ltr_default_matches_frozen_pre_rtl_serialization() -> None:
    default_svg = build_nikah_svg(
        "highlighted_word_hero",
        copy=_HIGHLIGHT_COPY,
        format_key="carousel",
    )

    assert default_svg == build_nikah_svg(
        "highlighted_word_hero",
        copy=_HIGHLIGHT_COPY,
        format_key="carousel",
        direction="ltr",
    )
    assert hashlib.sha256(default_svg.encode()).hexdigest() == (
        "32f8c826e6a7e13bf6b90ba801fbfdcc8548094221163e259082ff16959d805f"
    )


def test_ayah_translation_uses_rtl_amiri_panel_and_ltr_translation() -> None:
    svg = build_nikah_svg(
        "ayah_translation",
        copy=_AYAH_COPY,
        format_key="carousel",
        direction="rtl",
    )

    assert 'data-role="ayah-panel"' in svg
    assert _AYAH_COPY["ayah"] in svg
    assert _AYAH_COPY["translation"] in svg
    assert "MimikScriptArabic" in svg
    assert "@font-face" in svg
    headline_layer = svg.split('id="layer-headline"', 1)[1].split("</g>", 1)[0]
    support_layer = svg.split('id="layer-support"', 1)[1].split("</g>", 1)[0]
    assert 'direction="rtl"' in headline_layer
    assert 'text-anchor="end"' in headline_layer
    assert 'direction="ltr"' in support_layer
    assert 'text-anchor="middle"' in support_layer
    root = ElementTree.fromstring(svg)
    translation_lines = root.findall(
        f"{{{_SVG_NS}}}g[@id='layer-support']/{{{_SVG_NS}}}text"
    )
    assert translation_lines
    assert {line.attrib["x"] for line in translation_lines} == {"540"}
    assert modesty_report(svg, source_kind="generated_vector") == []


def test_rtl_nikah_right_aligns_arabic_headline_support_and_cta() -> None:
    svg = build_nikah_svg(
        "protection_symbol_hero",
        copy={
            "headline": "بداية تحفظ الخصوصية",
            "sub": "تعارف هادف تقوده القيم",
            "cta": "ابدأ الآن",
        },
        format_key="ig_post",
        direction="rtl",
    )
    root = ElementTree.fromstring(svg)

    for layer_id in ("layer-headline", "layer-support", "layer-cta"):
        texts = root.findall(f"{{{_SVG_NS}}}g[@id='{layer_id}']//{{{_SVG_NS}}}text")
        assert texts
        for text in texts:
            assert text.attrib["direction"] == "rtl"
            assert text.attrib["text-anchor"] == "end"
            assert "MimikScriptArabic" in text.attrib["font-family"]


def test_ayah_translation_requires_arabic_ayah_and_ltr_translation() -> None:
    with pytest.raises(ValueError, match="Arabic-script 'ayah'"):
        build_nikah_svg(
            "ayah_translation",
            copy={"ayah": "A sign of mercy", "translation": "A sign of mercy"},
            format_key="ig_post",
        )

    with pytest.raises(ValueError, match="Latin-script 'translation'"):
        build_nikah_svg(
            "ayah_translation",
            copy={"ayah": _AYAH_COPY["ayah"], "translation": "مودة ورحمة"},
            format_key="ig_post",
        )


def test_svg_dimensions_match_each_format() -> None:
    for format_key, width, height in _FORMATS:
        svg = build_nikah_svg(
            "highlighted_word_hero", copy=_HIGHLIGHT_COPY, format_key=format_key, hero_symbol="heart"
        )
        assert f'width="{width}"' in svg
        assert f'height="{height}"' in svg
        assert f'viewBox="0 0 {width} {height}"' in svg


def test_highlight_word_box_lands_in_its_own_layer() -> None:
    svg = build_nikah_svg("highlighted_word_hero", copy=_HIGHLIGHT_COPY, format_key="carousel")
    highlight_layer = svg.split('id="layer-highlight-word"', 1)[1].split("</g>", 1)[0]
    assert 'data-role="highlight-word"' in highlight_layer
    assert ">RIGHT<" in svg  # reversed-out uppercase key word


def test_figure_primitive_stamps_faceless_and_figure_attrs() -> None:
    svg = build_nikah_svg(
        "highlighted_word_hero", copy=_HIGHLIGHT_COPY, format_key="carousel", hero_symbol="hands_heart"
    )
    assert 'data-figure="true"' in svg
    assert 'data-faceless="true"' in svg
    hero_layer = svg.split('id="layer-hero"', 1)[1].split('id="layer-wordmark"', 1)[0]
    assert 'data-figure="true"' in hero_layer  # the figure lives inside the hero group


# ---------------------------------------------------------------------------------------------
# Modesty QA (§4)
# ---------------------------------------------------------------------------------------------


def test_modesty_passes_for_generated_vector() -> None:
    for archetype, copy, hero in (
        ("highlighted_word_hero", _HIGHLIGHT_COPY, "hands_heart"),
        ("protection_symbol_hero", _PROTECTION_COPY, "heart_shield"),
        ("ayah_translation", _AYAH_COPY, "crescent"),
    ):
        svg = build_nikah_svg(archetype, copy=copy, format_key="carousel", hero_symbol=hero)
        assert modesty_report(svg, source_kind="generated_vector") == []


def test_modesty_fails_on_raster_image_outside_wordmark_group() -> None:
    svg = build_nikah_svg("highlighted_word_hero", copy=_HIGHLIGHT_COPY, format_key="carousel")
    # Inject a raster <image> at the document root (outside any data-role="wordmark" group).
    tainted = svg.replace(
        "</svg>",
        '<image href="data:image/png;base64,aGk=" x="0" y="0" width="10" height="10"/></svg>',
        1,
    )
    failures = modesty_report(tainted, source_kind="generated_vector")
    assert failures
    assert any("raster <image>" in f for f in failures)


def test_modesty_allows_a_logo_image_inside_the_wordmark_group() -> None:
    svg = build_nikah_svg(
        "highlighted_word_hero",
        copy=_HIGHLIGHT_COPY,
        format_key="carousel",
        logo_ref="data:image/png;base64,aGk=",
    )
    assert "<image" in svg  # the logo raster is present ...
    assert modesty_report(svg, source_kind="generated_vector") == []  # ... but approved


def test_modesty_fails_closed_on_ai_illustration_and_other_sources() -> None:
    svg = build_nikah_svg("protection_symbol_hero", copy=_PROTECTION_COPY, format_key="carousel")
    assert modesty_report(svg, source_kind="ai_illustration")  # profile source #2 fails closed
    assert modesty_report(svg, source_kind="licensed_stock")
    assert modesty_report(svg, source_kind="ai_realistic")


# ---------------------------------------------------------------------------------------------
# Copy discipline + never-a-photo guardrail
# ---------------------------------------------------------------------------------------------


def test_missing_highlight_fails_loud_for_highlighted_word_hero() -> None:
    with pytest.raises(ValueError):
        build_nikah_svg("highlighted_word_hero", copy={"headline": "No key word here"}, format_key="carousel")


def test_highlight_must_be_a_substring_of_the_headline() -> None:
    with pytest.raises(ValueError):
        build_nikah_svg(
            "highlighted_word_hero",
            copy={"headline": "Marry with the right intention", "highlight": "PROTECTED"},
            format_key="carousel",
        )


def test_unknown_archetype_and_format_fail_loud() -> None:
    with pytest.raises(ValueError):
        build_nikah_svg("nope", copy=_HIGHLIGHT_COPY, format_key="carousel")
    # get_format is fail-loud via KeyError (the established format-registry behaviour).
    with pytest.raises(KeyError):
        build_nikah_svg("highlighted_word_hero", copy=_HIGHLIGHT_COPY, format_key="not_a_format")


def test_photo_copy_key_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_nikah_svg(
            "protection_symbol_hero",
            copy={"headline": "Trust first", "image_ref": "/tmp/couple.jpg"},
            format_key="carousel",
        )


def test_context_rejects_a_photo_image_ref() -> None:
    with pytest.raises(ValueError):
        NikahTemplateContext(format_key="carousel", headline="Trust first", image_ref="/tmp/x.jpg")
