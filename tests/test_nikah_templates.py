"""Simply Nikah render family: layered vector SVG, exact-dims PNG, and structural modesty QA."""

from __future__ import annotations

import hashlib
import struct
import zlib
from xml.etree import ElementTree

import pytest

from creative.render.compositor import browser_available, png_size
from creative.render.compositor import chromium_page
from creative.render import nikah_primitives as prim
from creative.render.nikah_templates import (
    _ARCHETYPE_PARAMS,
    NikahLayoutError,
    NikahTemplateContext,
    build_nikah_svg,
    modesty_report,
    render_nikah,
    render_nikah_with_layout,
)
from mimik_contracts import get_format

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

_COPY_LENGTHS = {
    "highlighted_word_hero": (
        {
            "headline": "Choose FAMILY",
            "highlight": "FAMILY",
            "sub": "Begin together.",
            "cta": "Begin",
        },
        {
            "headline": "Involve your FAMILY from the very first step",
            "highlight": "FAMILY",
            "sub": "A thoughtful introduction keeps trust and intention clear.",
            "cta": "Start well",
        },
        {
            "headline": "Keep your FAMILY involved from the very first conversation",
            "highlight": "FAMILY",
            "sub": "Bring trusted people into each stage so every conversation stays purposeful.",
            "cta": "Start with family",
        },
    ),
    "protection_symbol_hero": (
        {
            "headline": "Privacy first",
            "sub": "Feel protected.",
            "cta": "Learn how",
        },
        {
            "headline": "Involve your family from the very first step",
            "sub": "Private conversations should still feel intentional and clear.",
            "cta": "Learn how",
        },
        {
            "headline": "Build trust through private introductions",
            "sub": "Thoughtful boundaries protect both families and keep each next step clear.",
            "cta": "Protect the journey",
        },
    ),
    "ayah_translation": (
        {
            "ayah": "وَمِنْ آيَاتِهِ",
            "translation": "And among His signs.",
            "cta": "Begin",
        },
        _AYAH_COPY,
        {
            "ayah": _AYAH_COPY["ayah"],
            "translation": (
                "He created spouses for you so that you may find tranquillity together."
            ),
            "cta": "Begin with intention",
        },
    ),
}


def _bbox_tuple(element: ElementTree.Element) -> tuple[int, int, int, int]:
    return tuple(int(round(float(value))) for value in element.attrib["data-bbox"].split())  # type: ignore[return-value]


def _intersects(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _assert_inside(
    bbox: tuple[int, int, int, int],
    safe: tuple[int, int, int, int],
) -> None:
    x, y, width, height = bbox
    sx, sy, sw, sh = safe
    assert x >= sx
    assert y >= sy
    assert x + width <= sx + sw
    assert y + height <= sy + sh


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
async def test_measured_render_exposes_real_line_geometry() -> None:
    """Catches regression to average-glyph wrapping or a separate measure-browser launch."""
    from creative.render import nikah_templates

    render_with_layout = getattr(nikah_templates, "render_nikah_with_layout", None)
    assert callable(render_with_layout), "Nikah needs a measured render result, not PNG-only output"

    result = await render_with_layout(
        "protection_symbol_hero",
        copy=_PROTECTION_COPY,
        format_key="ig_post",
        hero_symbol="shield_crescent",
    )
    assert result.message.lines
    assert 'data-text-metrics="chromium"' in result.svg
    assert all(line.bbox.width > 0 and line.bbox.height > 0 for line in result.message.lines)
    assert png_size(result.png) == (1080, 1080)
    repeated = await render_with_layout(
        "protection_symbol_hero",
        copy=_PROTECTION_COPY,
        format_key="ig_post",
        hero_symbol="shield_crescent",
    )
    assert repeated.svg == result.svg
    assert repeated.png == result.png


@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
async def test_layer_override_is_reflected_in_final_chromium_geometry() -> None:
    baseline = await render_nikah_with_layout(
        "protection_symbol_hero",
        copy=_PROTECTION_COPY,
        format_key="ig_post",
    )
    shifted = await render_nikah_with_layout(
        "protection_symbol_hero",
        copy=_PROTECTION_COPY,
        format_key="ig_post",
        layer_overrides={"layer-headline": {"dx": 12}},
    )
    baseline_headline = next(
        line for line in baseline.message.lines if line.role == "headline"
    )
    shifted_headline = next(
        line for line in shifted.message.lines if line.role == "headline"
    )
    assert shifted_headline.bbox.x == baseline_headline.bbox.x + 12


@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
async def test_layer_override_that_breaks_layout_fails_loud() -> None:
    with pytest.raises(NikahLayoutError, match="safe margins"):
        await render_nikah_with_layout(
            "protection_symbol_hero",
            copy=_PROTECTION_COPY,
            format_key="ig_post",
            layer_overrides={"layer-headline": {"dx": 700}},
        )


@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
async def test_wordmark_override_cannot_intersect_hero() -> None:
    with pytest.raises(NikahLayoutError, match=r"wordmark intersects layer-(?:hero|glow)"):
        await render_nikah_with_layout(
            "protection_symbol_hero",
            copy=_PROTECTION_COPY,
            format_key="ig_post",
            layer_overrides={"layer-wordmark": {"dy": 384}},
        )


@pytest.mark.parametrize("archetype", tuple(_ARCHETYPE_PARAMS))
@pytest.mark.parametrize("format_key", tuple(key for key, _width, _height in _FORMATS))
@pytest.mark.parametrize("length_index", (0, 1, 2), ids=("short", "medium", "long"))
@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
async def test_layout_matrix_keeps_content_inside_safe_area_without_occlusion(
    archetype: str,
    format_key: str,
    length_index: int,
) -> None:
    """Catches fixed-fraction hero placement and unbounded content stacks."""
    result = await render_nikah_with_layout(
        archetype,
        copy=_COPY_LENGTHS[archetype][length_index],
        format_key=format_key,
        direction="rtl" if archetype == "ayah_translation" else "ltr",
    )
    svg = result.svg
    root = ElementTree.fromstring(svg)
    fmt = get_format(format_key)
    safe = (
        fmt.safe_zone.left,
        fmt.safe_zone.top,
        fmt.width - fmt.safe_zone.left - fmt.safe_zone.right,
        fmt.height - fmt.safe_zone.top - fmt.safe_zone.bottom,
    )
    text_boxes = [
        _bbox_tuple(element)
        for element in root.findall(f".//{{{_SVG_NS}}}text[@data-bbox]")
    ]
    decoration_boxes = [
        _bbox_tuple(element)
        for element in root.findall(
            f".//{{{_SVG_NS}}}g[@data-occluding='true'][@data-bbox]"
        )
    ]
    assert text_boxes, (archetype, format_key, length_index)
    assert decoration_boxes or archetype == "ayah_translation"
    for bbox in (*text_boxes, *decoration_boxes):
        _assert_inside(bbox, safe)
    for text_bbox in text_boxes:
        assert not any(_intersects(text_bbox, decoration) for decoration in decoration_boxes)


@pytest.mark.parametrize("archetype", tuple(_ARCHETYPE_PARAMS))
@pytest.mark.parametrize("format_key", tuple(key for key, _width, _height in _FORMATS))
async def test_overlong_copy_fails_loud(archetype: str, format_key: str) -> None:
    """Catches silent overflow when even the permitted font shrink range cannot fit."""
    if archetype == "ayah_translation":
        copy = {
            "ayah": " ".join(["وَمِنْ آيَاتِهِ"] * 80),
            "translation": " ".join(["A deliberately overlong translation"] * 80),
            "cta": "Begin",
        }
    else:
        headline = " ".join(["deliberately overlong headline"] * 80)
        copy = {
            "headline": f"{headline} FAMILY" if archetype == "highlighted_word_hero" else headline,
            "sub": " ".join(["deliberately overlong support copy"] * 80),
            "cta": "Begin",
        }
        if archetype == "highlighted_word_hero":
            copy["highlight"] = "FAMILY"

    with pytest.raises(ValueError, match="does not fit"):
        await render_nikah_with_layout(
            archetype,
            copy=copy,
            format_key=format_key,
            direction="rtl" if archetype == "ayah_translation" else "ltr",
        )


@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
async def test_wrap_avoids_single_short_final_word_when_a_balanced_break_exists() -> None:
    """Catches the verified 'very' orphan caused by average-character wrapping."""
    result = await render_nikah_with_layout(
        "protection_symbol_hero",
        copy={
            "headline": "Involve your family from the very first step",
            "sub": "Keep both families part of the journey.",
        },
        format_key="ig_post",
    )
    svg = result.svg
    root = ElementTree.fromstring(svg)
    lines = [
        (element.text or "").strip()
        for element in root.findall(
            f".//{{{_SVG_NS}}}g[@id='layer-headline']/{{{_SVG_NS}}}text"
        )
    ]
    assert len(lines) >= 2
    assert len(lines[-1].split()) > 1, lines


@pytest.mark.skipif(not browser_available(), reason="playwright not installed")
async def test_rtl_actual_chromium_ink_stays_inside_safe_area() -> None:
    """Catches SVG direction/text-anchor combinations whose metadata lies about actual ink."""
    result = await render_nikah_with_layout(
        "protection_symbol_hero",
        copy={
            "headline": "بداية تحفظ الخصوصية",
            "sub": "تعارف هادف تقوده القيم",
            "cta": "ابدأ الآن",
        },
        format_key="ig_post",
        direction="rtl",
    )
    fmt = get_format("ig_post")
    async with chromium_page(fmt.width, fmt.height) as page:
        await page.set_content(result.svg, wait_until="load")
        await page.evaluate("document.fonts.ready")
        boxes = await page.eval_on_selector_all(
            "text[data-bbox]",
            """elements => elements.map(element => {
              const box = element.getBBox();
              const declared = element.dataset.bbox.split(" ").map(Number);
              return {
                x: box.x, y: box.y, width: box.width, height: box.height,
                declaredX: declared[0], declaredY: declared[1],
                declaredWidth: declared[2], declaredHeight: declared[3],
              };
            })""",
        )
    assert boxes
    for box in boxes:
        assert box["x"] >= fmt.safe_zone.left
        assert box["y"] >= fmt.safe_zone.top
        assert box["x"] + box["width"] <= fmt.width - fmt.safe_zone.right
        assert box["y"] + box["height"] <= fmt.height - fmt.safe_zone.bottom
        assert abs(box["x"] - box["declaredX"]) <= 2
        assert abs(box["y"] - box["declaredY"]) <= 2
        assert abs(box["width"] - box["declaredWidth"]) <= 2
        assert abs(box["height"] - box["declaredHeight"]) <= 2


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
        root = ElementTree.fromstring(svg)
        assert sum(
            "data-bbox" in group.attrib
            for group in root.findall(f".//{{{_SVG_NS}}}g[@data-layer]")
        ) == 9
        assert root.findall(f".//{{{_SVG_NS}}}text[@data-bbox]")


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
        "52895bd2a41e01d978dcdf210b5c23cc13b6ab7ebc6cf36296c4a74c4243fae9"
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
    assert 'text-anchor="start"' in headline_layer
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
            assert text.attrib["text-anchor"] == "start"
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


@pytest.mark.parametrize(
    "fragment",
    (
        prim.hands_forming_heart(
            100,
            100,
            120,
            fill="#FD62AD",
            sleeve_fill="#2B0A2E",
        ),
        prim.shield_crescent(
            100,
            100,
            120,
            fill="#FD62AD",
            shield_fill="#F9C6DE",
            stroke="#2B0A2E",
        ),
    ),
)
def test_fixed_figure_primitives_are_nonblank_and_faceless(fragment: str) -> None:
    root = ElementTree.fromstring(fragment)
    assert root.attrib["data-figure"] == "true"
    assert root.attrib["data-faceless"] == "true"
    assert len(list(root.iter())) >= 4
    assert fragment.count("<path") >= 2


def test_hero_resolution_prefers_bundled_vectors_then_falls_back_to_primitive() -> None:
    hands = build_nikah_svg(
        "highlighted_word_hero",
        copy=_HIGHLIGHT_COPY,
        format_key="carousel",
        hero_symbol="hands_heart",
    )
    shield = build_nikah_svg(
        "protection_symbol_hero",
        copy=_PROTECTION_COPY,
        format_key="carousel",
        hero_symbol="shield_crescent",
    )

    assert 'data-vector="dua_hands"' in hands
    assert 'data-role="shield-crescent"' in shield
    assert modesty_report(hands, source_kind="generated_vector") == []
    assert modesty_report(shield, source_kind="generated_vector") == []


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
