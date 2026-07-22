"""Layered PSD export preserves the six independently editable creative elements."""

from __future__ import annotations

import binascii
import io
import struct
import zlib
from pathlib import Path
from types import ModuleType
from xml.etree import ElementTree

import pytest


LAYER_NAMES = {"background", "panel", "headline", "subhead", "cta", "badge"}
SVG_LAYER_IDS = {
    "layer-background",
    "layer-panel",
    "layer-headline",
    "layer-subhead",
    "layer-cta",
    "layer-badge",
}
LAYER_OFFSETS = {
    "layer-background": (0, 0),
    "layer-panel": (101, 51),
    "layer-headline": (202, 102),
    "layer-subhead": (303, 153),
    "layer-cta": (404, 204),
    "layer-badge": (505, 255),
}
PSD_PANEL_ORDER = ["badge", "cta", "subhead", "headline", "panel", "background"]


class _FakePage:
    def __init__(self) -> None:
        self.html = ""
        self.screenshot_clip: dict[str, int] = {}
        self.omit_background = False

    async def set_content(self, html: str, *, wait_until: str) -> None:
        assert wait_until == "load"
        self.html = html

    async def screenshot(
        self,
        *,
        clip: dict[str, int],
        omit_background: bool,
    ) -> bytes:
        self.screenshot_clip = clip
        self.omit_background = omit_background
        return b"transparent-png"


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self.page = page
        self.closed = False

    async def new_page(
        self,
        *,
        viewport: dict[str, int],
        device_scale_factor: int,
    ) -> _FakePage:
        assert viewport == {"width": 1200, "height": 630}
        assert device_scale_factor == 1
        return self.page

    async def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.browser = browser

    async def launch(self, *, args: list[str]) -> _FakeBrowser:
        assert args == ["--no-sandbox", "--disable-dev-shm-usage"]
        return self.browser


class _FakePlaywright:
    def __init__(self, chromium: _FakeChromium) -> None:
        self.chromium = chromium


class _FakePlaywrightManager:
    def __init__(self, playwright: _FakePlaywright) -> None:
        self.playwright = playwright

    async def __aenter__(self) -> _FakePlaywright:
        return self.playwright

    async def __aexit__(
        self,
        exc_type: object | None,
        exc_value: object | None,
        traceback: object | None,
    ) -> None:
        return None


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def _rgba_png(
    width: int,
    height: int,
    *,
    visible_pixel: tuple[int, int] | None,
) -> bytes:
    empty_row = b"\x00" + b"\x00\x00\x00\x00" * width
    if visible_pixel is None:
        pixels = empty_row * height
    else:
        x, y = visible_pixel
        visible_row = (
            b"\x00"
            + b"\x00\x00\x00\x00" * x
            + b"\x22\x44\x66\xff"
            + b"\x00\x00\x00\x00" * (width - x - 1)
        )
        pixels = empty_row * y + visible_row + empty_row * (height - y - 1)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(pixels))
        + _png_chunk(b"IEND", b"")
    )


def _install_layer_rasterizer(
    monkeypatch: pytest.MonkeyPatch,
    psd_export: ModuleType,
) -> list[str]:
    rasterized_layer_ids: list[str] = []

    async def fake_rasterize_svg_to_png(svg: str, *, width: int, height: int) -> bytes:
        root = ElementTree.fromstring(svg)
        layers = [child for child in root if child.tag.endswith("}g")]
        assert len(layers) == 1
        layer = layers[0]
        layer_id = layer.attrib["id"]
        rasterized_layer_ids.append(layer_id)
        assert (width, height) == (1200, 630)
        visible_pixel = LAYER_OFFSETS[layer_id] if len(layer) else None
        return _rgba_png(width, height, visible_pixel=visible_pixel)

    monkeypatch.setattr(
        psd_export,
        "_rasterize_layer_svg_to_png",
        fake_rasterize_svg_to_png,
    )
    return rasterized_layer_ids


async def test_layer_rasterizer_preserves_transparency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("pytoshop")
    from creative.export import psd as psd_export

    page = _FakePage()
    browser = _FakeBrowser(page)
    playwright = _FakePlaywright(_FakeChromium(browser))
    manager = _FakePlaywrightManager(playwright)
    monkeypatch.setattr(psd_export, "async_playwright", lambda: manager)

    output = await psd_export._rasterize_layer_svg_to_png(
        '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        width=1200,
        height=630,
    )

    assert output == b"transparent-png"
    assert "<svg" in page.html
    assert page.screenshot_clip == {"x": 0, "y": 0, "width": 1200, "height": 630}
    assert page.omit_background is True
    assert browser.closed is True


async def test_render_creative_psd_emits_six_named_layers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytoshop = pytest.importorskip("pytoshop")
    from pytoshop.user import nested_layers

    from creative.export import psd as psd_export

    png = _rgba_png(1200, 630, visible_pixel=(0, 0))
    rasterized_layer_ids = _install_layer_rasterizer(monkeypatch, psd_export)
    photo = tmp_path / "clinic-photo.png"
    photo.write_bytes(png)

    output = await psd_export.render_creative_psd(
        format_key="fb_post",
        image_ref=str(photo),
        headline="Skin boosters, explained",
        sub="Support hydration with a consultation-led plan.",
        cta="Book your consultation",
        palette_ink="#5A2A6B",
        palette_ground="#FFFFFF",
        badge_text="G2G Aesthetics",
        logo_ref=None,
    )

    assert output.startswith(b"8BPS")
    document = pytoshop.read(io.BytesIO(output))
    assert (document.width, document.height) == (1200, 630)
    layers = nested_layers.psd_to_nested_layers(document)
    assert len(layers) == 6
    assert {layer.name for layer in layers} == LAYER_NAMES
    assert [layer.name for layer in layers] == PSD_PANEL_ORDER
    layers_by_name = {layer.name: layer for layer in layers}
    assert (
        layers_by_name["background"].left,
        layers_by_name["background"].top,
        layers_by_name["background"].right,
        layers_by_name["background"].bottom,
    ) == (0, 0, 1200, 630)
    for svg_layer_id, (left, top) in LAYER_OFFSETS.items():
        layer_name = svg_layer_id.removeprefix("layer-")
        if layer_name == "background":
            continue
        layer = layers_by_name[layer_name]
        assert (layer.left, layer.top, layer.right, layer.bottom) == (
            left,
            top,
            left + 1,
            top + 1,
        )
        assert int(layer.channels[-1].max()) == 255
    assert set(rasterized_layer_ids) == SVG_LAYER_IDS


async def test_render_creative_psd_keeps_empty_optional_layers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytoshop = pytest.importorskip("pytoshop")
    from pytoshop.user import nested_layers

    from creative.export import psd as psd_export

    png = _rgba_png(1200, 630, visible_pixel=(0, 0))
    _install_layer_rasterizer(monkeypatch, psd_export)
    photo = tmp_path / "clinic-photo.png"
    photo.write_bytes(png)

    output = await psd_export.render_creative_psd(
        format_key="fb_post",
        image_ref=str(photo),
        headline="Skin boosters, explained",
        sub=None,
        cta=None,
        palette_ink="#5A2A6B",
        palette_ground="#FFFFFF",
        badge_text="G2G Aesthetics",
        logo_ref=None,
    )

    document = pytoshop.read(io.BytesIO(output))
    layers = nested_layers.psd_to_nested_layers(document)
    layers_by_name = {layer.name: layer for layer in layers}
    assert {layer.name for layer in layers} == LAYER_NAMES
    assert int(layers_by_name["subhead"].channels[-1].max()) == 0
    assert int(layers_by_name["cta"].channels[-1].max()) == 0
