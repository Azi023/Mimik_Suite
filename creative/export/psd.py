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
from pytoshop import enums, tagged_block
from pytoshop import layers as psd_layer_records
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


def _empty_layer_record(image_layer: nested_layers.Image) -> psd_layer_records.LayerRecord:
    """Build a raw layer record for a fully-transparent (empty optional) slot.

    ``nested_layers.nested_layers_to_psd`` silently drops any layer whose alpha channel
    is entirely zero, which would erase empty optional slots (missing subhead/cta/logo).
    Building the record directly bypasses that drop so the named slot survives round-trip.
    """
    channels = {
        channel_id: psd_layer_records.ChannelImageData(
            image=pixels,
            compression=enums.Compression.raw,
        )
        for channel_id, pixels in image_layer.channels.items()
    }
    return psd_layer_records.LayerRecord(
        top=image_layer.top,
        left=image_layer.left,
        bottom=image_layer.bottom,
        right=image_layer.right,
        name=image_layer.name,
        channels=channels,
        blocks=[tagged_block.UnicodeLayerName(name=image_layer.name)],
    )


def _restore_empty_layers(
    document: object,
    ordered_layers: list[tuple[nested_layers.Image, bool]],
) -> None:
    """Rebuild the document's layer stack in ``ordered_layers`` order (bottom to top),
    re-inserting the empty named slots that pytoshop's high-level helper dropped."""
    layer_info = document.layer_and_mask_info.layer_info  # type: ignore[attr-defined]
    records = layer_info.layer_records
    group_block = document.image_resources.get_block(  # type: ignore[attr-defined]
        enums.ImageResourceID.layers_group_info
    )
    group_ids = group_block.group_ids
    record_by_name = {record.name: record for record in records}
    group_id_by_name = {
        record.name: group_id for record, group_id in zip(records, group_ids)
    }

    new_records: list[psd_layer_records.LayerRecord] = []
    new_group_ids: list[int] = []
    for image_layer, is_empty in ordered_layers:
        if is_empty:
            new_records.append(_empty_layer_record(image_layer))
            new_group_ids.append(0)
        else:
            new_records.append(record_by_name[image_layer.name])
            new_group_ids.append(group_id_by_name[image_layer.name])
    records[:] = new_records
    group_ids[:] = new_group_ids


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
    # Bottom-to-top stacking order: (image_layer, is_empty). Empty = fully transparent slot.
    ordered_layers: list[tuple[nested_layers.Image, bool]] = []
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
        is_empty = not bool(cropped.pixels[:, :, 3].any())
        ordered_layers.append((_to_pytoshop_layer(psd_layer_name, cropped), is_empty))

    # pytoshop drops any all-transparent layer, so build the document from the visible
    # layers (top-to-bottom, Photoshop panel order) then splice the empty named slots
    # back in — every semantic layer survives as a REAL, named PSD layer.
    visible_layers = [layer for layer, is_empty in ordered_layers if not is_empty]
    document = nested_layers.nested_layers_to_psd(
        list(reversed(visible_layers)),
        color_mode=enums.ColorMode.rgb,
        # pytoshop 1.2.1 ships without its compiled `packbits` module, so the default RLE
        # compressor raises NameError; `raw` avoids that codec path and writes cleanly.
        compression=enums.Compression.raw,
    )
    _restore_empty_layers(document, ordered_layers)
    output = io.BytesIO()
    document.write(output)
    return output.getvalue()
