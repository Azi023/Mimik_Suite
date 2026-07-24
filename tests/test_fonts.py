"""Brand-font embedding (M-10 / Lane C): the render path loads an uploaded font as @font-face.

Optional + backward-compatible — with no font ref the SVG/HTML output is byte-identical to the
system-font render. The helper doesn't parse font internals (Chromium does at raster time), so
these tests use tiny stand-in font files keyed by extension, which is what the format-hint logic
and the base64 data-URI embedding actually depend on.
"""

from __future__ import annotations

import base64
from pathlib import Path
from xml.etree import ElementTree

import pytest

from creative.render.fonts import (
    FontEmbedError,
    embed_font_face,
    font_family_stack,
)


SVG_NS = "http://www.w3.org/2000/svg"

# Magic bytes so the stand-ins are also valid uploads (see brand_memory.sniff_mime), though the
# embedding helper only needs the extension. woff2 = "wOF2", otf = "OTTO", ttf = sfnt 0x00010000.
_FONT_MAGIC = {
    ".ttf": b"\x00\x01\x00\x00" + b"stub-ttf-payload",
    ".otf": b"OTTO" + b"stub-otf-payload",
    ".woff2": b"wOF2" + b"stub-woff2-payload",
    ".woff": b"wOFF" + b"stub-woff-payload",
}


def _font_file(tmp_path: Path, suffix: str) -> Path:
    path = tmp_path / f"brand{suffix}"
    path.write_bytes(_FONT_MAGIC[suffix])
    return path


# ---------------------------------------------------------------------------- helper


@pytest.mark.parametrize(
    ("suffix", "mime", "fmt"),
    [
        (".ttf", "font/ttf", "truetype"),
        (".otf", "font/otf", "opentype"),
        (".woff2", "font/woff2", "woff2"),
        (".woff", "font/woff", "woff"),
    ],
)
def test_embed_font_face_emits_data_uri_and_format_hint(
    tmp_path: Path, suffix: str, mime: str, fmt: str
) -> None:
    path = _font_file(tmp_path, suffix)
    embedded = embed_font_face(str(path), family="MimikBrandHeading")

    assert embedded.family == "MimikBrandHeading"
    assert embedded.face_css.startswith("@font-face{")
    assert "font-family:'MimikBrandHeading'" in embedded.face_css
    assert f"src:url(data:{mime};base64," in embedded.face_css
    assert f"format('{fmt}')" in embedded.face_css
    # The exact bytes round-trip through the data URI.
    expected_b64 = base64.b64encode(_FONT_MAGIC[suffix]).decode("ascii")
    assert expected_b64 in embedded.face_css


def test_embed_font_face_accepts_data_uri_input() -> None:
    raw = b"wOF2stub"
    data_uri = "data:font/woff2;base64," + base64.b64encode(raw).decode("ascii")
    embedded = embed_font_face(data_uri, family="MimikBrandBody")
    assert data_uri in embedded.face_css
    assert "format('woff2')" in embedded.face_css


def test_embed_font_face_rejects_unknown_extension(tmp_path: Path) -> None:
    bad = tmp_path / "brand.svg"
    bad.write_bytes(b"<svg/>")
    with pytest.raises(FontEmbedError):
        embed_font_face(str(bad), family="MimikBrandHeading")


def test_embed_font_face_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FontEmbedError):
        embed_font_face(str(tmp_path / "nope.ttf"), family="MimikBrandHeading")


def test_embed_font_face_rejects_unsafe_family(tmp_path: Path) -> None:
    path = _font_file(tmp_path, ".ttf")
    with pytest.raises(FontEmbedError):
        embed_font_face(str(path), family="evil'} body{display:none")


def test_font_family_stack_prefers_brand_then_fallback() -> None:
    assert font_family_stack("MimikBrandHeading", "sans-serif") == "'MimikBrandHeading', sans-serif"


# --------------------------------------------------------------------- svg wiring


def _svg(**kwargs: object) -> str:
    from creative.export.svg import render_creative_svg

    base = dict(
        format_key="ig_post",
        image_ref="data:image/png;base64,aGk=",
        headline="Skin boosters, explained",
        sub="Support hydration with a consultation-led plan.",
        cta="Book your consultation",
        palette_ink="#5A2A6B",
        palette_ground="#FFFFFF",
        badge_text="G2G Aesthetics",
        logo_ref=None,
    )
    base.update(kwargs)
    return render_creative_svg(**base)  # type: ignore[arg-type]


def test_render_creative_svg_without_font_is_byte_identical() -> None:
    assert _svg() == _svg(heading_font_ref=None, body_font_ref=None)


def test_render_creative_svg_injects_font_face_and_applies_family(tmp_path: Path) -> None:
    heading = _font_file(tmp_path, ".ttf")
    body = _font_file(tmp_path, ".otf")
    svg = _svg(heading_font_ref=str(heading), body_font_ref=str(body))

    # @font-face lives in a <style> element on the SVG.
    root = ElementTree.fromstring(svg)
    style = root.find(f"{{{SVG_NS}}}style")
    assert style is not None and style.text is not None
    assert "@font-face" in style.text
    assert "MimikBrandHeading" in style.text
    assert "MimikBrandBody" in style.text
    assert "format('truetype')" in style.text
    assert "format('opentype')" in style.text

    # Headline text uses the heading family (with fallback), subhead + CTA use the body family.
    headline = root.find(f"{{{SVG_NS}}}g[@id='layer-headline']/{{{SVG_NS}}}text")
    subhead = root.find(f"{{{SVG_NS}}}g[@id='layer-subhead']/{{{SVG_NS}}}text")
    cta = root.find(f"{{{SVG_NS}}}g[@id='layer-cta']/{{{SVG_NS}}}text")
    assert headline is not None and "MimikBrandHeading" in headline.attrib["font-family"]
    assert subhead is not None and "MimikBrandBody" in subhead.attrib["font-family"]
    assert cta is not None and "MimikBrandBody" in cta.attrib["font-family"]


def test_render_creative_svg_heading_only_leaves_body_system(tmp_path: Path) -> None:
    heading = _font_file(tmp_path, ".woff2")
    svg = _svg(heading_font_ref=str(heading))
    root = ElementTree.fromstring(svg)
    style = root.find(f"{{{SVG_NS}}}style")
    assert style is not None and "MimikBrandHeading" in (style.text or "")
    assert "MimikBrandBody" not in (style.text or "")
    subhead = root.find(f"{{{SVG_NS}}}g[@id='layer-subhead']/{{{SVG_NS}}}text")
    assert subhead is not None
    assert "MimikBrandBody" not in subhead.attrib["font-family"]


# ------------------------------------------------------------- glo2go template wiring


def _glo2go_html(**kwargs: object) -> str:
    from creative.render.glo2go_templates import build_glo2go_html
    from creative.style_profile import get_style_profile

    return build_glo2go_html(
        "single_photo_education_hero",
        image_ref="data:image/png;base64,aGk=",
        copy={
            "headline": "Skin boosters, explained",
            "sub": "Support hydration with a consultation-led plan.",
            "cta": "Book now",
        },
        format_key="ig_post",
        profile=get_style_profile("glo2go-aesthetics"),
        **kwargs,  # type: ignore[arg-type]
    )


def test_glo2go_without_font_is_byte_identical() -> None:
    assert _glo2go_html() == _glo2go_html(heading_font_ref=None, body_font_ref=None)


def test_glo2go_injects_font_face_and_family_overrides(tmp_path: Path) -> None:
    heading = _font_file(tmp_path, ".ttf")
    body = _font_file(tmp_path, ".woff2")
    html = _glo2go_html(heading_font_ref=str(heading), body_font_ref=str(body))

    assert "@font-face" in html
    assert "format('truetype')" in html
    assert "format('woff2')" in html
    # Cascade overrides applied to the heading and body selectors.
    assert ".g2g-panel h1{font-family:'MimikBrandHeading'" in html
    assert "'MimikBrandBody'" in html


# --------------------------------------------------------- Simply Nikah template wiring
#
# SN renders HTML/SVG through the same Playwright compositor, so it adopts embed_font_face /
# font_family_stack identically (fonts.py ADOPTERS note): heading font -> headline + highlight
# word, body font -> support line + CTA. None => byte-identical system-font render.


def _nikah_svg(**kwargs: object) -> str:
    from creative.render.nikah_templates import build_nikah_svg

    return build_nikah_svg(
        "highlighted_word_hero",
        copy={
            "headline": "Marry with the RIGHT intention",
            "highlight": "RIGHT",
            "sub": "A gentle, faith-led beginning for two families.",
            "cta": "Start your nikah",
        },
        format_key="ig_post",
        **kwargs,  # type: ignore[arg-type]
    )


def _first_text_under(root: ElementTree.Element, layer_id: str) -> ElementTree.Element | None:
    layer = root.find(f"{{{SVG_NS}}}g[@id='{layer_id}']")
    if layer is None:
        return None
    return next(iter(layer.iter(f"{{{SVG_NS}}}text")), None)


def test_nikah_without_font_is_byte_identical() -> None:
    assert _nikah_svg() == _nikah_svg(heading_font_ref=None, body_font_ref=None)


def test_nikah_injects_font_face_and_applies_family(tmp_path: Path) -> None:
    heading = _font_file(tmp_path, ".ttf")
    body = _font_file(tmp_path, ".otf")
    svg = _nikah_svg(heading_font_ref=str(heading), body_font_ref=str(body))

    root = ElementTree.fromstring(svg)
    style = root.find(f"{{{SVG_NS}}}style")
    assert style is not None and style.text is not None
    assert "@font-face" in style.text
    assert "MimikBrandHeading" in style.text
    assert "MimikBrandBody" in style.text
    assert "format('truetype')" in style.text
    assert "format('opentype')" in style.text

    # Heading font drives the headline + highlight word; body font drives the support + CTA.
    headline = _first_text_under(root, "layer-headline")
    highlight = _first_text_under(root, "layer-highlight-word")
    support = _first_text_under(root, "layer-support")
    cta = _first_text_under(root, "layer-cta")
    assert headline is not None and "MimikBrandHeading" in headline.attrib["font-family"]
    assert highlight is not None and "MimikBrandHeading" in highlight.attrib["font-family"]
    assert support is not None and "MimikBrandBody" in support.attrib["font-family"]
    assert cta is not None and "MimikBrandBody" in cta.attrib["font-family"]


def test_nikah_with_font_still_passes_modesty() -> None:
    """A brand font is additive vector CSS — it must not trip the structural modesty audit."""
    from creative.render.nikah_templates import modesty_report

    svg = _nikah_svg(
        heading_font_ref="data:font/woff2;base64," + base64.b64encode(b"wOF2stub").decode("ascii"),
        body_font_ref="data:font/woff2;base64," + base64.b64encode(b"wOF2stub").decode("ascii"),
    )
    assert modesty_report(svg, source_kind="generated_vector") == []
