"""Layered, editable SVG export for the Glo2Go single-photo education hero."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from mimik_contracts import PRESETS, CreativeFormat

from creative.render.compositor import render_html_to_png


_SVG_NS = "http://www.w3.org/2000/svg"
_INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_IMAGE_MIME_BY_SUFFIX = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}
_SYSTEM_FONT = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
_DEFAULT_BADGE_TEXT = "G2G Aesthetics"
_REGION_AXES = {
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

ElementTree.register_namespace("", _SVG_NS)
ElementTree.register_namespace("inkscape", _INKSCAPE_NS)


@dataclass(frozen=True)
class _Frame:
    top: int
    right: int
    bottom: int
    left: int
    badge_width: int
    badge_height: int


@dataclass(frozen=True)
class _Composition:
    panel_x: int
    panel_y: int
    panel_width: int
    panel_height: int
    panel_padding: int
    headline_size: int
    body_size: int
    headline_lines: tuple[str, ...]
    subhead_lines: tuple[str, ...]


def _svg_tag(local_name: str) -> str:
    return f"{{{_SVG_NS}}}{local_name}"


def _format_for(format_key: str) -> CreativeFormat:
    try:
        return PRESETS[format_key]
    except KeyError as exc:
        choices = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown creative format {format_key!r}; choose from: {choices}") from exc


def _embed_local_image(image_ref: str) -> str:
    if image_ref.startswith("data:image/"):
        if ";base64," not in image_ref:
            raise ValueError("Image data URIs must be base64 encoded")
        return image_ref

    path = Path(image_ref)
    if not path.is_file():
        raise FileNotFoundError(f"Creative image path is not a local file: {image_ref}")
    mime = _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower())
    if mime is None:
        supported = ", ".join(sorted(_IMAGE_MIME_BY_SUFFIX))
        raise ValueError(f"Creative image must use one of these extensions: {supported}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _frame(fmt: CreativeFormat) -> _Frame:
    short = min(fmt.width, fmt.height)
    house = round(short * 0.06)
    return _Frame(
        top=max(house, fmt.safe_zone.top),
        right=max(house, fmt.safe_zone.right),
        bottom=max(house, fmt.safe_zone.bottom),
        left=max(house, fmt.safe_zone.left),
        badge_width=round(short * 0.24),
        badge_height=round(short * 0.055),
    )


def _wrap_preserving_text(text: str, max_chars: int) -> tuple[str, ...]:
    """Wrap at whitespace while keeping concatenated tspan content byte-for-byte equal."""
    if not text:
        return ()

    lines: list[str] = []
    cursor = 0
    while len(text) - cursor > max_chars:
        window_end = cursor + max_chars
        break_at = max(
            (index + 1 for index in range(cursor, window_end) if text[index].isspace()),
            default=window_end,
        )
        if break_at <= cursor:
            break_at = window_end
        lines.append(text[cursor:break_at])
        cursor = break_at
    lines.append(text[cursor:])
    return tuple(lines)


def _composition(
    fmt: CreativeFormat,
    *,
    headline: str,
    sub: str | None,
    cta: str | None,
    text_region: str,
) -> _Composition:
    if text_region not in _REGION_AXES:
        choices = ", ".join(_REGION_AXES)
        raise ValueError(f"Unknown text region {text_region!r}; choose from: {choices}")

    dense = sum(len(value.strip()) for value in (headline, sub or "", cta or "")) > 150
    panel_width = round(fmt.width * (0.66 if dense else 0.54))
    panel_padding = round(fmt.width * (0.034 if dense else 0.040))
    headline_size = round(fmt.width * (0.052 if dense else 0.064))
    body_size = round(fmt.width * (0.023 if dense else 0.026))
    content_width = panel_width - 2 * panel_padding
    headline_chars = max(1, int(content_width / (headline_size * 0.56)))
    body_chars = max(1, int(content_width / (body_size * 0.52)))
    headline_lines = _wrap_preserving_text(headline, headline_chars)
    subhead_lines = _wrap_preserving_text(sub, body_chars) if sub and sub.strip() else ()

    headline_height = round(len(headline_lines) * headline_size * 1.08)
    subhead_height = 0
    if subhead_lines:
        subhead_height = round(body_size * 0.72 + len(subhead_lines) * body_size * 1.45)
    cta_height = round(body_size * 2.55) if cta and cta.strip() else 0
    panel_height = 2 * panel_padding + headline_height + subhead_height + cta_height

    frame = _frame(fmt)
    horizontal, vertical = _REGION_AXES[text_region]
    x = {
        "left": frame.left,
        "center": round((fmt.width - panel_width) / 2),
        "right": fmt.width - frame.right - panel_width,
    }[horizontal]
    y = {
        "top": frame.top,
        "center": round((fmt.height - panel_height) / 2),
        "bottom": fmt.height - frame.bottom - panel_height,
    }[vertical]

    badge_left = fmt.width - frame.right - frame.badge_width
    if vertical == "top" and x + panel_width > badge_left:
        y = frame.top + frame.badge_height + round(frame.badge_height * 0.35)
    panel_x = max(frame.left, min(x, fmt.width - frame.right - panel_width))
    panel_y = max(frame.top, min(y, fmt.height - frame.bottom - panel_height))
    return _Composition(
        panel_x=panel_x,
        panel_y=panel_y,
        panel_width=panel_width,
        panel_height=panel_height,
        panel_padding=panel_padding,
        headline_size=headline_size,
        body_size=body_size,
        headline_lines=headline_lines,
        subhead_lines=subhead_lines,
    )


def _layer(root: ElementTree.Element, layer_id: str) -> ElementTree.Element:
    return ElementTree.SubElement(
        root,
        _svg_tag("g"),
        {
            "id": layer_id,
            "data-layer": layer_id,
            f"{{{_INKSCAPE_NS}}}label": layer_id,
            f"{{{_INKSCAPE_NS}}}groupmode": "layer",
        },
    )


def _add_wrapped_text(
    layer: ElementTree.Element,
    *,
    lines: tuple[str, ...],
    x: int,
    first_baseline: int,
    line_height: int,
    font_size: int,
    font_weight: int,
    fill: str,
) -> ElementTree.Element:
    text = ElementTree.SubElement(
        layer,
        _svg_tag("text"),
        {
            "x": str(x),
            "y": str(first_baseline),
            "fill": fill,
            "font-family": _SYSTEM_FONT,
            "font-size": str(font_size),
            "font-weight": str(font_weight),
            f"{{{_XML_NS}}}space": "preserve",
        },
    )
    for index, line in enumerate(lines):
        tspan = ElementTree.SubElement(
            text,
            _svg_tag("tspan"),
            {
                "x": str(x),
                "y": str(first_baseline + index * line_height),
            },
        )
        tspan.text = line
    return text


def render_creative_svg(
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
) -> str:
    """Return the Glo2Go hero as a complete SVG with named, editable layers."""
    if not headline.strip():
        raise ValueError("Creative headline must not be blank")

    fmt = _format_for(format_key)
    comp = _composition(
        fmt,
        headline=headline,
        sub=sub,
        cta=cta,
        text_region=text_region,
    )
    root = ElementTree.Element(
        _svg_tag("svg"),
        {
            "version": "1.1",
            "width": str(fmt.width),
            "height": str(fmt.height),
            "viewBox": f"0 0 {fmt.width} {fmt.height}",
        },
    )

    background = _layer(root, "layer-background")
    ElementTree.SubElement(
        background,
        _svg_tag("image"),
        {
            "x": "0",
            "y": "0",
            "width": str(fmt.width),
            "height": str(fmt.height),
            "preserveAspectRatio": "xMidYMid slice",
            "href": _embed_local_image(image_ref),
        },
    )

    panel = _layer(root, "layer-panel")
    ElementTree.SubElement(
        panel,
        _svg_tag("rect"),
        {
            "x": str(comp.panel_x),
            "y": str(comp.panel_y),
            "width": str(comp.panel_width),
            "height": str(comp.panel_height),
            "rx": "26",
            "fill": palette_ground,
            "fill-opacity": "0.94",
            "stroke": palette_ink,
            "stroke-opacity": "0.10",
        },
    )

    content_x = comp.panel_x + comp.panel_padding
    headline_baseline = comp.panel_y + comp.panel_padding + comp.headline_size
    headline_layer = _layer(root, "layer-headline")
    _add_wrapped_text(
        headline_layer,
        lines=comp.headline_lines,
        x=content_x,
        first_baseline=headline_baseline,
        line_height=round(comp.headline_size * 1.08),
        font_size=comp.headline_size,
        font_weight=760,
        fill=palette_ink,
    )

    subhead_layer = _layer(root, "layer-subhead")
    headline_height = round(len(comp.headline_lines) * comp.headline_size * 1.08)
    subhead_baseline = (
        comp.panel_y
        + comp.panel_padding
        + headline_height
        + round(comp.body_size * 0.72)
        + comp.body_size
    )
    if comp.subhead_lines:
        _add_wrapped_text(
            subhead_layer,
            lines=comp.subhead_lines,
            x=content_x,
            first_baseline=subhead_baseline,
            line_height=round(comp.body_size * 1.45),
            font_size=comp.body_size,
            font_weight=430,
            fill=palette_ink,
        )

    cta_layer = _layer(root, "layer-cta")
    if cta and cta.strip():
        subhead_height = 0
        if comp.subhead_lines:
            subhead_height = round(
                comp.body_size * 0.72 + len(comp.subhead_lines) * comp.body_size * 1.45
            )
        cta_font_size = round(comp.body_size * 0.9)
        cta_padding_x = round(comp.body_size * 0.92)
        cta_padding_y = round(comp.body_size * 0.55)
        cta_height = cta_font_size + 2 * cta_padding_y
        cta_width = min(
            comp.panel_width - 2 * comp.panel_padding,
            round(len(cta) * cta_font_size * 0.56 + 2 * cta_padding_x),
        )
        cta_x = content_x
        cta_y = (
            comp.panel_y
            + comp.panel_padding
            + headline_height
            + subhead_height
            + round(comp.body_size * 0.82)
        )
        ElementTree.SubElement(
            cta_layer,
            _svg_tag("rect"),
            {
                "x": str(cta_x),
                "y": str(cta_y),
                "width": str(cta_width),
                "height": str(cta_height),
                "rx": str(round(cta_height / 2)),
                "fill": palette_ink,
            },
        )
        cta_text = ElementTree.SubElement(
            cta_layer,
            _svg_tag("text"),
            {
                "x": str(cta_x + cta_padding_x),
                "y": str(cta_y + cta_padding_y + cta_font_size),
                "fill": palette_ground,
                "font-family": _SYSTEM_FONT,
                "font-size": str(cta_font_size),
                "font-weight": "750",
            },
        )
        cta_text.text = cta

    badge_layer = _layer(root, "layer-badge")
    frame = _frame(fmt)
    badge_x = fmt.width - frame.right - frame.badge_width
    if logo_ref:
        ElementTree.SubElement(
            badge_layer,
            _svg_tag("image"),
            {
                "x": str(badge_x),
                "y": str(frame.top),
                "width": str(frame.badge_width),
                "height": str(frame.badge_height),
                "preserveAspectRatio": "xMidYMid meet",
                "href": _embed_local_image(logo_ref),
            },
        )
    else:
        ElementTree.SubElement(
            badge_layer,
            _svg_tag("rect"),
            {
                "x": str(badge_x),
                "y": str(frame.top),
                "width": str(frame.badge_width),
                "height": str(frame.badge_height),
                "rx": str(round(frame.badge_height / 2)),
                "fill": palette_ink,
            },
        )
        wordmark = ElementTree.SubElement(
            badge_layer,
            _svg_tag("text"),
            {
                "x": str(badge_x + round(frame.badge_width / 2)),
                "y": str(frame.top + round(frame.badge_height * 0.62)),
                "fill": palette_ground,
                "font-family": _SYSTEM_FONT,
                "font-size": str(round(frame.badge_height * 0.34)),
                "font-weight": "700",
                "text-anchor": "middle",
            },
        )
        wordmark.text = badge_text or _DEFAULT_BADGE_TEXT

    return ElementTree.tostring(root, encoding="unicode", xml_declaration=True)


async def rasterize_svg_to_png(svg: str, format_key: str) -> bytes:
    """Rasterize a generated SVG through the established Playwright compositor."""
    fmt = _format_for(format_key)
    root = ElementTree.fromstring(svg)
    if root.tag != _svg_tag("svg"):
        raise ValueError("Expected a namespaced SVG document")
    if root.attrib.get("width") != str(fmt.width) or root.attrib.get("height") != str(fmt.height):
        raise ValueError(
            f"SVG dimensions must match {format_key!r}: {fmt.width}x{fmt.height}"
        )

    svg_fragment = ElementTree.tostring(root, encoding="unicode")
    html = (
        f'<div style="width:{fmt.width}px;height:{fmt.height}px;overflow:hidden">'
        f"{svg_fragment}</div>"
    )
    return await render_html_to_png(html, fmt.width, fmt.height, scale=1)
