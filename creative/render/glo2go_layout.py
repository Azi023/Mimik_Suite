"""Shared rubric-driven geometry and image analysis for Glo2Go hero exports."""

from __future__ import annotations

import base64
import binascii
import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
from mimik_contracts import CreativeFormat


TextRegion = Literal[
    "top",
    "bottom",
    "left",
    "right",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "center",
]
PanelAnchor = Literal["left", "center", "right"]
TextAlignment = Literal["left", "center", "right"]
BadgeTheme = Literal["plum", "light"]

DEFAULT_SUBJECT_ZOOM = 0.94
DEFAULT_PANEL_ANCHOR: PanelAnchor = "left"
DEFAULT_TEXT_ALIGNMENT: TextAlignment = "center"
_DARK_LUMINANCE_THRESHOLD = 0.35
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_REGION_AXES: dict[TextRegion, tuple[PanelAnchor, Literal["top", "center", "bottom"]]] = {
    "top": ("center", "top"),
    "bottom": ("center", "bottom"),
    "left": ("left", "center"),
    "right": ("right", "center"),
    "top_left": ("left", "top"),
    "top_right": ("right", "top"),
    "bottom_left": ("left", "bottom"),
    "bottom_right": ("right", "bottom"),
    "center": ("center", "center"),
}


@dataclass(frozen=True)
class LayoutGrid:
    """Safe-zone-derived margin and baseline grid for one output format."""

    step: int
    top: int
    right: int
    bottom: int
    left: int


@dataclass(frozen=True)
class BadgeBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class PhotoBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class HeroComposition:
    panel_x: int
    panel_y: int
    panel_width: int
    panel_height: int
    panel_padding: int
    headline_size: int
    headline_line_height: int
    body_size: int
    body_line_height: int
    cta_height: int
    panel_anchor: PanelAnchor
    text_alignment: TextAlignment
    grid: LayoutGrid
    badge: BadgeBox
    photo: PhotoBox


def _snap(value: int | float, step: int) -> int:
    return round(float(value) / step) * step


def _snap_up(value: int | float, step: int) -> int:
    return math.ceil(float(value) / step) * step


def layout_grid(fmt: CreativeFormat) -> LayoutGrid:
    """Build the L4 grid from the format safe zone, not template magic numbers."""
    safe = fmt.safe_zone
    positive_edges = [edge for edge in (safe.top, safe.right, safe.bottom, safe.left) if edge]
    safe_basis = min(positive_edges, default=round(min(fmt.width, fmt.height) * 0.06))
    step = max(4, round(safe_basis / 4))
    house_margin = round(min(fmt.width, fmt.height) * 0.06)
    return LayoutGrid(
        step=step,
        top=_snap_up(max(house_margin, safe.top), step),
        right=_snap_up(max(house_margin, safe.right), step),
        bottom=_snap_up(max(house_margin, safe.bottom), step),
        left=_snap_up(max(house_margin, safe.left), step),
    )


def badge_box(fmt: CreativeFormat, grid: LayoutGrid | None = None) -> BadgeBox:
    resolved_grid = grid or layout_grid(fmt)
    short = min(fmt.width, fmt.height)
    width = max(resolved_grid.step, _snap(round(short * 0.24), resolved_grid.step))
    height = max(resolved_grid.step, _snap(round(short * 0.055), resolved_grid.step))
    return BadgeBox(
        x=fmt.width - resolved_grid.right - width,
        y=resolved_grid.top,
        width=width,
        height=height,
    )


def photo_box(fmt: CreativeFormat, subject_zoom: float) -> PhotoBox:
    """Inset the photo symmetrically so L3 adds breathing room without changing the canvas."""
    if not 0 < subject_zoom <= 1:
        raise ValueError("subject_zoom must be greater than 0 and at most 1")
    grid = layout_grid(fmt)
    inset_x = max(0, _snap((fmt.width * (1 - subject_zoom)) / 2, grid.step))
    inset_y = max(0, _snap((fmt.height * (1 - subject_zoom)) / 2, grid.step))
    return PhotoBox(
        x=inset_x,
        y=inset_y,
        width=fmt.width - 2 * inset_x,
        height=fmt.height - 2 * inset_y,
    )


def _line_count(text: str | None, font_size: int, available_width: int, glyph: float) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) * font_size * glyph / max(1, available_width)))


def hero_composition(
    fmt: CreativeFormat,
    *,
    headline: str,
    subhead: str | None,
    cta: str | None,
    dense: bool,
    text_region: TextRegion | None,
    panel_anchor: PanelAnchor | None,
    text_alignment: TextAlignment,
    subject_zoom: float,
) -> HeroComposition:
    """Resolve the compact L2 panel and snap every L4 edge/baseline to one grid."""
    if text_alignment not in {"left", "center", "right"}:
        raise ValueError(f"Unknown text alignment: {text_alignment!r}")
    grid = layout_grid(fmt)
    badge = badge_box(fmt, grid)
    photo = photo_box(fmt, subject_zoom)

    # L2: deliberately narrower than the legacy 54/66% panel while retaining readable type.
    panel_width = _snap(fmt.width * (0.58 if dense else 0.48), grid.step)
    max_panel_width = fmt.width - grid.left - grid.right
    panel_width = min(max_panel_width, max(grid.step * 12, panel_width))
    panel_padding = max(grid.step * 2, _snap_up(fmt.width * 0.026, grid.step))
    headline_size = round(fmt.width * (0.050 if dense else 0.060))
    body_size = round(fmt.width * (0.022 if dense else 0.025))
    headline_line_height = _snap_up(headline_size * 1.08, grid.step)
    body_line_height = _snap_up(body_size * 1.35, grid.step)
    content_width = panel_width - 2 * panel_padding
    headline_lines = _line_count(headline, headline_size, content_width, 0.56)
    body_lines = _line_count(subhead, body_size, content_width, 0.52)
    cta_height = _snap_up(body_size * 2.0, grid.step) if cta else 0
    panel_height = 2 * panel_padding + headline_lines * headline_line_height
    if body_lines:
        panel_height += grid.step + body_lines * body_line_height
    if cta:
        panel_height += grid.step + cta_height
    panel_height = _snap_up(panel_height, grid.step)

    region_horizontal, vertical = (
        _REGION_AXES[text_region] if text_region is not None else (DEFAULT_PANEL_ANCHOR, "center")
    )
    horizontal = panel_anchor or region_horizontal
    x = {
        "left": grid.left,
        "center": _snap((fmt.width - panel_width) / 2, grid.step),
        "right": fmt.width - grid.right - panel_width,
    }[horizontal]
    y = {
        "top": grid.top,
        "center": _snap((fmt.height - panel_height) / 2, grid.step),
        "bottom": fmt.height - grid.bottom - panel_height,
    }[vertical]

    # L4: top-right content advances by whole grid steps until it clears the badge box.
    if vertical == "top" and x + panel_width > badge.x:
        y = _snap_up(badge.y + badge.height + grid.step, grid.step)
    panel_x = max(grid.left, min(x, fmt.width - grid.right - panel_width))
    panel_y = max(grid.top, min(y, fmt.height - grid.bottom - panel_height))
    return HeroComposition(
        panel_x=panel_x,
        panel_y=panel_y,
        panel_width=panel_width,
        panel_height=panel_height,
        panel_padding=panel_padding,
        headline_size=headline_size,
        headline_line_height=headline_line_height,
        body_size=body_size,
        body_line_height=body_line_height,
        cta_height=cta_height,
        panel_anchor=horizontal,
        text_alignment=text_alignment,
        grid=grid,
        badge=badge,
        photo=photo,
    )


def badge_theme(background_luminance: float | None) -> BadgeTheme:
    """Apply L1: dark photo ground gets a light/reversed badge; unknown/light stays plum."""
    if background_luminance is None:
        return "plum"
    if not 0 <= background_luminance <= 1:
        raise ValueError("badge background luminance must be between 0 and 1")
    return "light" if background_luminance < _DARK_LUMINANCE_THRESHOLD else "plum"


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distances = (
        (abs(estimate - left), left),
        (abs(estimate - above), above),
        (abs(estimate - upper_left), upper_left),
    )
    return min(distances, key=lambda item: item[0])[1]


def _unfilter_png_rows(
    filtered: bytes,
    *,
    width: int,
    height: int,
    bytes_per_pixel: int,
) -> bytes:
    stride = width * bytes_per_pixel
    if len(filtered) != height * (stride + 1):
        raise ValueError("PNG pixel payload does not match its declared dimensions")
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
            left = decoded[row_offset + column - bytes_per_pixel] if column >= bytes_per_pixel else 0
            above = decoded[previous_row_offset + column] if row else 0
            upper_left = (
                decoded[previous_row_offset + column - bytes_per_pixel]
                if row and column >= bytes_per_pixel
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


def _decode_png(image_ref: str) -> npt.NDArray[np.uint8] | None:
    if image_ref.startswith("data:image/png;base64,"):
        encoded = image_ref.partition(",")[2]
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            return None
    else:
        path = Path(image_ref)
        if path.suffix.lower() != ".png" or not path.is_file():
            return None
        payload = path.read_bytes()
    if not payload.startswith(_PNG_SIGNATURE):
        return None

    width: int | None = None
    height: int | None = None
    color_type: int | None = None
    compressed_parts: list[bytes] = []
    offset = len(_PNG_SIGNATURE)
    while offset + 12 <= len(payload):
        chunk_length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + chunk_length
        if data_end + 4 > len(payload):
            return None
        chunk_data = payload[data_start:data_end]
        offset = data_end + 4
        if chunk_type == b"IHDR":
            if len(chunk_data) != 13:
                return None
            width, height, bit_depth, color_type, compression, filter_method, interlace = (
                struct.unpack(">IIBBBBB", chunk_data)
            )
            if (
                width <= 0
                or height <= 0
                or bit_depth != 8
                or color_type not in {2, 6}
                or compression != 0
                or filter_method != 0
                or interlace != 0
            ):
                return None
        elif chunk_type == b"IDAT":
            compressed_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None or color_type is None or not compressed_parts:
        return None
    try:
        filtered = zlib.decompress(b"".join(compressed_parts))
        bytes_per_pixel = 4 if color_type == 6 else 3
        decoded = _unfilter_png_rows(
            filtered,
            width=width,
            height=height,
            bytes_per_pixel=bytes_per_pixel,
        )
    except (ValueError, zlib.error):
        return None
    return np.frombuffer(decoded, dtype=np.uint8).reshape(height, width, bytes_per_pixel)


def mean_badge_luminance(
    image_ref: str,
    fmt: CreativeFormat,
    *,
    subject_zoom: float,
) -> float | None:
    """Sample the mean relative luminance mapped under the badge for local/data-URI PNGs."""
    pixels = _decode_png(image_ref)
    if pixels is None:
        return None
    source_height, source_width = pixels.shape[:2]
    photo = photo_box(fmt, subject_zoom)
    badge = badge_box(fmt)
    left = max(photo.x, badge.x)
    top = max(photo.y, badge.y)
    right = min(photo.x + photo.width, badge.x + badge.width)
    bottom = min(photo.y + photo.height, badge.y + badge.height)
    if right <= left or bottom <= top:
        return None

    scale = max(photo.width / source_width, photo.height / source_height)
    rendered_width = source_width * scale
    rendered_height = source_height * scale
    rendered_x = photo.x + (photo.width - rendered_width) / 2
    rendered_y = photo.y + (photo.height - rendered_height) / 2
    source_left = max(0, math.floor((left - rendered_x) / scale))
    source_top = max(0, math.floor((top - rendered_y) / scale))
    source_right = min(source_width, math.ceil((right - rendered_x) / scale))
    source_bottom = min(source_height, math.ceil((bottom - rendered_y) / scale))
    sample = pixels[source_top:source_bottom, source_left:source_right, :3]
    if sample.size == 0:
        return None
    srgb = sample.astype(np.float64) / 255.0
    linear = np.where(
        srgb <= 0.04045,
        srgb / 12.92,
        ((srgb + 0.055) / 1.055) ** 2.4,
    )
    luminance = 0.2126 * linear[:, :, 0] + 0.7152 * linear[:, :, 1] + 0.0722 * linear[:, :, 2]
    return float(luminance.mean())


def resolve_badge_luminance(
    image_ref: str,
    fmt: CreativeFormat,
    *,
    subject_zoom: float,
    sampled_luminance: float | None,
) -> float | None:
    """Use a caller sample when provided; otherwise sample the embedded PNG deterministically."""
    if sampled_luminance is not None:
        if not 0 <= sampled_luminance <= 1:
            raise ValueError("badge_background_luminance must be between 0 and 1")
        return sampled_luminance
    return mean_badge_luminance(image_ref, fmt, subject_zoom=subject_zoom)
