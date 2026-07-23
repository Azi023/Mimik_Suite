"""Post-composition SVG layer overrides stay scoped and editable."""

from __future__ import annotations

import base64
import hashlib
import math
import struct
import zlib
from collections.abc import Mapping
from xml.etree import ElementTree

import pytest


SVG_NS = "http://www.w3.org/2000/svg"
LAYER_IDS = (
    "layer-background",
    "layer-panel",
    "layer-headline",
    "layer-subhead",
    "layer-cta",
    "layer-badge",
)
_NO_OVERRIDE_BASELINE_SHA256 = "fed97390817d27724d9ec059b07f0ab758bc9e1a495a5d9a801a0278557d8e20"


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


def _render(layer_overrides: Mapping[str, object] | None = None) -> str:
    from creative.export.svg import render_creative_svg

    return render_creative_svg(
        format_key="ig_post",
        image_ref=_solid_png_data_uri("#F4F4F4"),
        headline="Layer override baseline",
        sub="Stable supporting copy.",
        cta="Book now",
        palette_ink="#5A2A6B",
        palette_ground="#FFFFFF",
        badge_text="G2G Aesthetics",
        logo_ref=None,
        layer_overrides=layer_overrides,
    )


def _render_without_override_argument() -> str:
    from creative.export.svg import render_creative_svg

    return render_creative_svg(
        format_key="ig_post",
        image_ref=_solid_png_data_uri("#F4F4F4"),
        headline="Layer override baseline",
        sub="Stable supporting copy.",
        cta="Book now",
        palette_ink="#5A2A6B",
        palette_ground="#FFFFFF",
        badge_text="G2G Aesthetics",
        logo_ref=None,
    )


def _layers(svg: str) -> dict[str, ElementTree.Element]:
    root = ElementTree.fromstring(svg)
    return {layer.attrib["id"]: layer for layer in root.findall(f"{{{SVG_NS}}}g")}


def _fills_by_layer(
    layers: Mapping[str, ElementTree.Element],
) -> dict[str, list[str]]:
    return {
        layer_id: [node.attrib["fill"] for node in layer.iter() if "fill" in node.attrib]
        for layer_id, layer in layers.items()
    }


def _bbox_center(layer: ElementTree.Element) -> tuple[str, str, str, str]:
    x, y, width, height = (float(part) for part in layer.attrib["data-bbox"].split())
    center_x = x + width / 2
    center_y = y + height / 2
    return (
        f"{center_x:g}",
        f"{center_y:g}",
        f"{-center_x:g}",
        f"{-center_y:g}",
    )


def test_panel_translation_is_scoped_to_panel_group() -> None:
    layers = _layers(_render({"layer-panel": {"dx": 120}}))

    assert layers["layer-panel"].attrib["transform"] == "translate(120,0)"
    for layer_id in set(LAYER_IDS) - {"layer-panel"}:
        assert "transform" not in layers[layer_id].attrib


def test_hidden_badge_is_scoped_to_badge_group() -> None:
    layers = _layers(_render({"layer-badge": {"visible": False}}))

    assert layers["layer-badge"].attrib["display"] == "none"
    assert layers["layer-badge"].attrib["data-hidden"] == "true"
    for layer_id in set(LAYER_IDS) - {"layer-badge"}:
        assert "display" not in layers[layer_id].attrib
        assert "data-hidden" not in layers[layer_id].attrib


def test_fill_override_changes_only_target_layer() -> None:
    baseline_fills = _fills_by_layer(_layers(_render()))
    overridden_fills = _fills_by_layer(_layers(_render({"layer-headline": {"fill": "#00AACC"}})))

    assert overridden_fills["layer-headline"] == ["#00AACC"]
    for layer_id in set(LAYER_IDS) - {"layer-headline"}:
        assert overridden_fills[layer_id] == baseline_fills[layer_id]


def test_every_named_layer_has_editable_bbox_metadata() -> None:
    layers = _layers(_render())

    assert tuple(layers) == LAYER_IDS
    for layer in layers.values():
        assert layer.attrib["data-editable"] == "true"
        parts = layer.attrib["data-bbox"].split()
        assert len(parts) == 4
        x, y, width, height = (float(part) for part in parts)
        assert all(math.isfinite(value) for value in (x, y, width, height))
        assert width >= 0
        assert height >= 0


def test_scale_uses_layer_bbox_origin_after_translation() -> None:
    layers = _layers(_render({"layer-panel": {"dx": 10, "dy": -5, "scale": 1.25}}))
    panel = layers["layer-panel"]
    x, y, _width, _height = panel.attrib["data-bbox"].split()

    assert panel.attrib["transform"] == (
        f"translate(10,-5) translate({x},{y}) scale(1.25) translate(-{x},-{y})"
    )


def test_non_uniform_scale_uses_layer_bbox_center_and_is_scoped() -> None:
    layers = _layers(
        _render({"layer-panel": {"scale_x": 1.5, "scale_y": 0.8}})
    )
    panel = layers["layer-panel"]
    center_x, center_y, negative_center_x, negative_center_y = _bbox_center(panel)

    assert panel.attrib["transform"] == (
        f"translate({center_x},{center_y}) scale(1.5,0.8) "
        f"translate({negative_center_x},{negative_center_y})"
    )
    for layer_id in set(LAYER_IDS) - {"layer-panel"}:
        assert "transform" not in layers[layer_id].attrib


def test_rotation_uses_layer_bbox_center_and_is_scoped() -> None:
    layers = _layers(_render({"layer-headline": {"rotation": 30}}))
    headline = layers["layer-headline"]
    center_x, center_y, _negative_center_x, _negative_center_y = _bbox_center(
        headline
    )

    assert headline.attrib["transform"] == f"rotate(30,{center_x},{center_y})"
    for layer_id in set(LAYER_IDS) - {"layer-headline"}:
        assert "transform" not in layers[layer_id].attrib


def test_identity_override_is_byte_identical_to_no_override() -> None:
    baseline = _render()
    identity = _render(
        {
            "layer-panel": {
                "dx": 0,
                "dy": 0,
                "scale": 1.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
                "rotation": 0.0,
            }
        }
    )

    assert identity == baseline


def test_axis_scale_and_rotation_are_clamped_to_contract_bounds() -> None:
    layers = _layers(
        _render(
            {
                "layer-panel": {
                    "scale_x": 4.5,
                    "scale_y": 0.8,
                    "rotation": 250,
                }
            }
        )
    )
    panel = layers["layer-panel"]
    center_x, center_y, negative_center_x, negative_center_y = _bbox_center(panel)

    assert panel.attrib["transform"] == (
        f"rotate(180,{center_x},{center_y}) "
        f"translate({center_x},{center_y}) scale(3,0.8) "
        f"translate({negative_center_x},{negative_center_y})"
    )


@pytest.mark.parametrize("key", ["scale_x", "scale_y"])
def test_axis_scale_must_be_greater_than_zero(key: str) -> None:
    with pytest.raises(ValueError, match=f"Layer override '{key}'"):
        _render({"layer-panel": {key: 0}})


@pytest.mark.parametrize("key", ["scale_x", "scale_y", "rotation"])
def test_transform_float_overrides_must_be_finite(key: str) -> None:
    with pytest.raises(ValueError, match=f"Layer override '{key}'"):
        _render({"layer-panel": {key: math.nan}})


async def test_no_override_matches_baseline_and_still_rasterizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from creative.export import svg as svg_export
    from creative.export.svg import rasterize_svg_to_png

    monkeypatch.setattr(svg_export, "load_rules", lambda _profile_id: ())
    calls: list[tuple[str, int, int, int]] = []

    async def fake_render_html_to_png(
        html: str,
        width: int,
        height: int,
        *,
        scale: int = 1,
    ) -> bytes:
        calls.append((html, width, height, scale))
        return b"layer-override-preview"

    monkeypatch.setattr(svg_export, "render_html_to_png", fake_render_html_to_png)
    omitted = _render_without_override_argument()
    explicit_none = _render(None)

    assert omitted == explicit_none
    assert hashlib.sha256(omitted.encode()).hexdigest() == _NO_OVERRIDE_BASELINE_SHA256
    assert await rasterize_svg_to_png(omitted, "ig_post") == b"layer-override-preview"
    assert len(calls) == 1
    html, width, height, scale = calls[0]
    assert "<svg" in html
    assert (width, height, scale) == (1080, 1080, 1)
