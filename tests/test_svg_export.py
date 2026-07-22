"""Layered SVG export stays structurally editable without a browser."""

from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path
from xml.etree import ElementTree

import pytest


SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
LAYER_IDS = [
    "layer-background",
    "layer-panel",
    "layer-headline",
    "layer-subhead",
    "layer-cta",
    "layer-badge",
]


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _solid_png_data_uri(hex_color: str, size: int = 8) -> str:
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes((red, green, blue)) * size
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(row * size))
        + _png_chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def test_render_creative_svg_emits_editable_named_layers(tmp_path: Path) -> None:
    from creative.export.svg import render_creative_svg

    photo = tmp_path / "clinic-photo.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\nunit-test-photo")
    headline = "Skin boosters, explained"
    sub = "Support hydration with a consultation-led plan."
    cta = "Book your consultation"

    svg = render_creative_svg(
        format_key="ig_post",
        image_ref=str(photo),
        headline=headline,
        sub=sub,
        cta=cta,
        palette_ink="#5A2A6B",
        palette_ground="#FFFFFF",
        badge_text="G2G Aesthetics",
        logo_ref=None,
    )

    root = ElementTree.fromstring(svg)
    assert root.tag == f"{{{SVG_NS}}}svg"
    assert root.attrib["width"] == "1080"
    assert root.attrib["height"] == "1080"

    layers = list(root.findall(f"{{{SVG_NS}}}g"))
    assert [layer.attrib["id"] for layer in layers] == LAYER_IDS
    for layer in layers:
        layer_id = layer.attrib["id"]
        assert layer.attrib["data-layer"] == layer_id
        assert layer.attrib["data-editable"] == "true"
        assert len(layer.attrib["data-bbox"].split()) == 4
        assert layer.attrib[f"{{{INKSCAPE_NS}}}label"] == layer_id

    text_values = [
        "".join(text.itertext()) for text in root.iterfind(f".//{{{SVG_NS}}}text")
    ]
    assert headline in text_values
    assert sub in text_values
    assert cta in text_values

    background = root.find(f"{{{SVG_NS}}}g[@id='layer-background']")
    assert background is not None
    image = background.find(f"{{{SVG_NS}}}image")
    assert image is not None
    assert image.attrib["href"].startswith("data:image/png;base64,")


def test_svg_renders_panel_anchor_and_centered_live_text() -> None:
    from creative.export.svg import render_creative_svg

    svg = render_creative_svg(
        format_key="ig_post",
        image_ref=_solid_png_data_uri("#F4F4F4"),
        headline="Centered inside a left panel",
        sub="Compact supporting copy.",
        cta="Book now",
        palette_ink="#5A2A6B",
        palette_ground="#FFFFFF",
        badge_text="G2G Aesthetics",
        logo_ref=None,
        panel_anchor="left",
        text_alignment="center",
    )
    root = ElementTree.fromstring(svg)
    panel = root.find(f"{{{SVG_NS}}}g[@id='layer-panel']")
    headline = root.find(f"{{{SVG_NS}}}g[@id='layer-headline']/{{{SVG_NS}}}text")

    assert panel is not None
    assert panel.attrib["data-panel-anchor"] == "left"
    assert panel.attrib["data-text-alignment"] == "center"
    assert headline is not None
    assert headline.attrib["text-anchor"] == "middle"
    assert "".join(headline.itertext()) == "Centered inside a left panel"


def test_svg_badge_theme_switches_for_dark_and_light_photo_stubs() -> None:
    from creative.export.svg import render_creative_svg

    def badge_fill(photo: str) -> str:
        svg = render_creative_svg(
            format_key="ig_post",
            image_ref=photo,
            headline="Badge contrast",
            sub=None,
            cta=None,
            palette_ink="#5A2A6B",
            palette_ground="#FFFFFF",
            badge_text="G2G Aesthetics",
            logo_ref=None,
        )
        root = ElementTree.fromstring(svg)
        badge = root.find(f"{{{SVG_NS}}}g[@id='layer-badge']")
        assert badge is not None
        rect = badge.find(f"{{{SVG_NS}}}rect")
        assert rect is not None
        return rect.attrib["fill"]

    assert badge_fill(_solid_png_data_uri("#F4F4F4")) == "#5A2A6B"
    assert badge_fill(_solid_png_data_uri("#111111")) == "#FFFFFF"


def test_svg_subject_zoom_changes_background_image_transform() -> None:
    from creative.export.svg import render_creative_svg

    def image_box(subject_zoom: float) -> tuple[str, str, str, str]:
        svg = render_creative_svg(
            format_key="ig_post",
            image_ref=_solid_png_data_uri("#F4F4F4"),
            headline="Zoomed subject",
            sub=None,
            cta=None,
            palette_ink="#5A2A6B",
            palette_ground="#FFFFFF",
            badge_text="G2G Aesthetics",
            logo_ref=None,
            subject_zoom=subject_zoom,
        )
        root = ElementTree.fromstring(svg)
        image = root.find(
            f"{{{SVG_NS}}}g[@id='layer-background']/{{{SVG_NS}}}image"
        )
        assert image is not None
        return tuple(image.attrib[key] for key in ("x", "y", "width", "height"))

    assert image_box(0.94) != image_box(0.86)


async def test_rasterize_svg_to_png_uses_existing_compositor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from creative.export import svg as svg_export
    from creative.export.svg import rasterize_svg_to_png

    calls: list[tuple[str, int, int, int]] = []

    async def fake_render_html_to_png(
        html: str,
        width: int,
        height: int,
        *,
        scale: int = 1,
    ) -> bytes:
        calls.append((html, width, height, scale))
        return b"png-preview"

    monkeypatch.setattr(svg_export, "render_html_to_png", fake_render_html_to_png)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" '
        'viewBox="0 0 1080 1080"></svg>'
    )

    png = await rasterize_svg_to_png(svg, "ig_post")

    assert png == b"png-preview"
    assert len(calls) == 1
    html, width, height, scale = calls[0]
    assert "<svg" in html
    assert (width, height, scale) == (1080, 1080, 1)
