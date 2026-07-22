"""Layered SVG export stays structurally editable without a browser."""

from __future__ import annotations

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
