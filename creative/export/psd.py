"""Layered Photoshop export built from the SVG export's exact geometry."""

from __future__ import annotations

import io
import struct
import zlib
from dataclasses import dataclass
from xml.etree import ElementTree

import numpy as np
import numpy.typing as npt
from mimik_contracts import PRESETS
from playwright.async_api import async_playwright
from pytoshop import enums
from pytoshop.user import nested_layers

from creative.export.svg import render_creative_svg


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SVG_GROUP_TAG = "{http://www.w3.org/2000/svg}g"
_LAYER_NAMES = (
    ("layer-background", "background"),
    ("layer-panel", "panel"),
    ("layer-headline", "headline"),
    ("layer-subhead", "subhead"),
    ("layer-cta", "cta"),
    ("layer-badge", "badge"),
)


@dataclass(frozen=True)
class _CroppedLayer:
    left: int
    top: int
    pixels: npt.NDArray[np.uint8]


def _isolate_svg_layer(svg: str, layer_id: str) -> str:
    root = ElementTree.fromstring(svg)
    found = False
    for child in list(root):
        if child.tag != _SVG_GROUP_TAG:
            continue
        if child.attrib.get("id") == layer_id:
            found = True
        else:
            root.remove(child)
    if not found:
        raise ValueError(f"SVG layer not found: {layer_id}")
    return ElementTree.tostring(root, encoding="unicode", xml_declaration=True)


async def _rasterize_layer_svg_to_png(svg: str, *, width: int, height: int) -> bytes:
    """Render an isolated SVG onto a transparent exact-size canvas."""
    document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>*{margin:0;padding:0;box-sizing:border-box}"
        "html,body{margin:0;background:transparent}</style>"
        f"</head><body>{svg}</body></html>"
    )
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            await page.set_content(document, wait_until="load")
            return await page.screenshot(
                clip={"x": 0, "y": 0, "width": width, "height": height},
                omit_background=True,
            )
        finally:
            await browser.close()


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _unfilter_png_rows(
    filtered: bytes,
    *,
    width: int,
    height: int,
    bytes_per_pixel: int,
) -> bytes:
    stride = width * bytes_per_pixel
    expected_size = height * (stride + 1)
    if len(filtered) != expected_size:
        raise ValueError(f"PNG pixel data has {len(filtered)} bytes; expected {expected_size}")

    decoded = bytearray(height * stride)
    source_offset = 0
    for row in range(height):
        filter_type = filtered[source_offset]
        source_offset += 1
        if filter_type not in {0, 1, 2, 3, 4}:
            raise ValueError(f"Unsupported PNG row filter: {filter_type}")

        row_offset = row * stride
        previous_row_offset = row_offset - stride
        for column in range(stride):
            value = filtered[source_offset + column]
            left = (
                decoded[row_offset + column - bytes_per_pixel] if column >= bytes_per_pixel else 0
            )
            above = decoded[previous_row_offset + column] if row > 0 else 0
            upper_left = (
                decoded[previous_row_offset + column - bytes_per_pixel]
                if row > 0 and column >= bytes_per_pixel
                else 0
            )
            if filter_type == 1:
                value += left
            elif filter_type == 2:
                value += above
            elif filter_type == 3:
                value += (left + above) // 2
            elif filter_type == 4:
                value += _paeth_predictor(left, above, upper_left)
            decoded[row_offset + column] = value & 0xFF
        source_offset += stride
    return bytes(decoded)


def _decode_png_rgba(png: bytes) -> npt.NDArray[np.uint8]:
    """Decode the non-interlaced 8-bit RGB/RGBA PNG emitted by Playwright."""
    if not png.startswith(_PNG_SIGNATURE):
        raise ValueError("Rasterized SVG did not produce a PNG")

    width: int | None = None
    height: int | None = None
    color_type: int | None = None
    compressed_parts: list[bytes] = []
    offset = len(_PNG_SIGNATURE)
    while offset < len(png):
        if offset + 12 > len(png):
            raise ValueError("PNG contains a truncated chunk")
        chunk_length = struct.unpack(">I", png[offset : offset + 4])[0]
        chunk_type = png[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + chunk_length
        chunk_end = data_end + 4
        if chunk_end > len(png):
            raise ValueError("PNG contains a truncated chunk payload")
        chunk_data = png[data_start:data_end]
        offset = chunk_end

        if chunk_type == b"IHDR":
            if len(chunk_data) != 13:
                raise ValueError("PNG IHDR must contain 13 bytes")
            width, height, bit_depth, color_type, compression, filter_method, interlace = (
                struct.unpack(">IIBBBBB", chunk_data)
            )
            if width <= 0 or height <= 0:
                raise ValueError("PNG dimensions must be positive")
            if bit_depth != 8 or color_type not in {2, 6}:
                raise ValueError("PSD export supports only 8-bit RGB or RGBA compositor PNGs")
            if compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError("PSD export requires a non-interlaced standard PNG")
        elif chunk_type == b"IDAT":
            compressed_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or color_type is None or not compressed_parts:
        raise ValueError("PNG is missing IHDR or IDAT data")

    try:
        filtered = zlib.decompress(b"".join(compressed_parts))
    except zlib.error as exc:
        raise ValueError("PNG IDAT data could not be decompressed") from exc
    bytes_per_pixel = 4 if color_type == 6 else 3
    decoded = _unfilter_png_rows(
        filtered,
        width=width,
        height=height,
        bytes_per_pixel=bytes_per_pixel,
    )
    pixels = np.frombuffer(decoded, dtype=np.uint8).reshape(height, width, bytes_per_pixel)
    if color_type == 6:
        return pixels.copy()

    alpha = np.full((height, width, 1), 255, dtype=np.uint8)
    return np.concatenate((pixels, alpha), axis=2)


def _crop_visible_pixels(
    pixels: npt.NDArray[np.uint8],
    *,
    keep_canvas: bool,
) -> _CroppedLayer:
    if keep_canvas:
        return _CroppedLayer(left=0, top=0, pixels=pixels)

    visible_y, visible_x = np.nonzero(pixels[:, :, 3])
    if visible_y.size == 0:
        transparent_pixel = np.zeros((1, 1, 4), dtype=np.uint8)
        return _CroppedLayer(left=0, top=0, pixels=transparent_pixel)

    top = int(visible_y.min())
    bottom = int(visible_y.max()) + 1
    left = int(visible_x.min())
    right = int(visible_x.max()) + 1
    return _CroppedLayer(
        left=left,
        top=top,
        pixels=np.ascontiguousarray(pixels[top:bottom, left:right]),
    )


def _to_pytoshop_layer(name: str, cropped: _CroppedLayer) -> nested_layers.Image:
    height, width, _ = cropped.pixels.shape
    channels = {
        0: cropped.pixels[:, :, 0].copy(),
        1: cropped.pixels[:, :, 1].copy(),
        2: cropped.pixels[:, :, 2].copy(),
        -1: cropped.pixels[:, :, 3].copy(),
    }
    return nested_layers.Image(
        name=name,
        top=cropped.top,
        left=cropped.left,
        bottom=cropped.top + height,
        right=cropped.left + width,
        channels=channels,
    )


async def render_creative_psd(
    *,
    format_key: str,
    image_ref: str,
    headline: str,
    sub: str | None,
    cta: str | None,
    palette_ink: str,
    palette_ground: str,
    badge_text: str | None,
    logo_ref: str | None,
    text_region: str = "bottom_right",
) -> bytes:
    """Return an exact-format PSD containing six independently movable raster layers.

    Text is rasterized rather than stored as live Photoshop type in v1, so editors can move,
    mask, or replace each text element but cannot edit its characters in place. This uses
    pytoshop's documented user API: ``nested_layers.Image`` receives RGBA channel arrays,
    ``nested_layers_to_psd`` builds the document, and ``PsdFile.write`` serializes it.
    """
    svg = render_creative_svg(
        format_key=format_key,
        image_ref=image_ref,
        headline=headline,
        sub=sub,
        cta=cta,
        palette_ink=palette_ink,
        palette_ground=palette_ground,
        badge_text=badge_text,
        logo_ref=logo_ref,
        text_region=text_region,
    )
    fmt = PRESETS[format_key]
    psd_layers: list[nested_layers.Image] = []
    for svg_layer_id, psd_layer_name in _LAYER_NAMES:
        layer_svg = _isolate_svg_layer(svg, svg_layer_id)
        layer_png = await _rasterize_layer_svg_to_png(
            layer_svg,
            width=fmt.width,
            height=fmt.height,
        )
        pixels = _decode_png_rgba(layer_png)
        if pixels.shape[:2] != (fmt.height, fmt.width):
            actual_height, actual_width = pixels.shape[:2]
            raise ValueError(
                "Rasterized layer dimensions must match "
                f"{format_key!r}: expected {fmt.width}x{fmt.height}, "
                f"got {actual_width}x{actual_height}"
            )
        cropped = _crop_visible_pixels(
            pixels,
            keep_canvas=psd_layer_name == "background",
        )
        psd_layers.append(_to_pytoshop_layer(psd_layer_name, cropped))

    # pytoshop's nested-layer list follows Photoshop's panel order (top to bottom).
    document = nested_layers.nested_layers_to_psd(
        list(reversed(psd_layers)),
        color_mode=enums.ColorMode.rgb,
        # pytoshop 1.2.1 ships without its compiled `packbits` module, so the default RLE
        # compressor raises NameError; `raw` avoids that codec path and writes cleanly.
        compression=enums.Compression.raw,
    )
    output = io.BytesIO()
    document.write(output)
    return output.getvalue()
