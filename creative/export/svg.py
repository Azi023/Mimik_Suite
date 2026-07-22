"""Layered, editable SVG export for the Glo2Go single-photo education hero."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from mimik_contracts import PRESETS, CreativeFormat

from creative.knowledge.feedback import load_rules
from creative.render.compositor import render_html_to_png
from creative.render.glo2go_layout import (
    DEFAULT_SUBJECT_ZOOM,
    DEFAULT_TEXT_ALIGNMENT,
    PanelAnchor,
    TextAlignment,
    TextRegion,
    badge_theme,
    hero_composition,
    resolve_badge_luminance,
)


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
_GLO2GO_PROFILE_ID = "glo2go-aesthetics"

ElementTree.register_namespace("", _SVG_NS)
ElementTree.register_namespace("inkscape", _INKSCAPE_NS)


@dataclass(frozen=True)
class _Composition:
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
    grid_step: int
    panel_anchor: PanelAnchor
    text_alignment: TextAlignment
    badge_x: int
    badge_y: int
    badge_width: int
    badge_height: int
    photo_x: int
    photo_y: int
    photo_width: int
    photo_height: int
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
    text_region: TextRegion | None,
    panel_anchor: PanelAnchor | None,
    text_alignment: TextAlignment,
    subject_zoom: float,
) -> _Composition:
    dense = sum(len(value.strip()) for value in (headline, sub or "", cta or "")) > 150
    layout = hero_composition(
        fmt,
        headline=headline,
        subhead=sub,
        cta=cta,
        dense=dense,
        text_region=text_region,
        panel_anchor=panel_anchor,
        text_alignment=text_alignment,
        subject_zoom=subject_zoom,
    )
    content_width = layout.panel_width - 2 * layout.panel_padding
    headline_chars = max(1, int(content_width / (layout.headline_size * 0.56)))
    body_chars = max(1, int(content_width / (layout.body_size * 0.52)))
    headline_lines = _wrap_preserving_text(headline, headline_chars)
    subhead_lines = _wrap_preserving_text(sub, body_chars) if sub and sub.strip() else ()
    return _Composition(
        panel_x=layout.panel_x,
        panel_y=layout.panel_y,
        panel_width=layout.panel_width,
        panel_height=layout.panel_height,
        panel_padding=layout.panel_padding,
        headline_size=layout.headline_size,
        headline_line_height=layout.headline_line_height,
        body_size=layout.body_size,
        body_line_height=layout.body_line_height,
        cta_height=layout.cta_height,
        grid_step=layout.grid.step,
        panel_anchor=layout.panel_anchor,
        text_alignment=layout.text_alignment,
        badge_x=layout.badge.x,
        badge_y=layout.badge.y,
        badge_width=layout.badge.width,
        badge_height=layout.badge.height,
        photo_x=layout.photo.x,
        photo_y=layout.photo.y,
        photo_width=layout.photo.width,
        photo_height=layout.photo.height,
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
    text_alignment: TextAlignment,
) -> ElementTree.Element:
    svg_anchor = {"left": "start", "center": "middle", "right": "end"}[text_alignment]
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
            "text-anchor": svg_anchor,
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


def _content_x(comp: _Composition) -> int:
    return {
        "left": comp.panel_x + comp.panel_padding,
        "center": comp.panel_x + round(comp.panel_width / 2),
        "right": comp.panel_x + comp.panel_width - comp.panel_padding,
    }[comp.text_alignment]


def _aligned_box_x(comp: _Composition, width: int) -> int:
    return {
        "left": comp.panel_x + comp.panel_padding,
        "center": comp.panel_x + round((comp.panel_width - width) / 2),
        "right": comp.panel_x + comp.panel_width - comp.panel_padding - width,
    }[comp.text_alignment]


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
    text_region: TextRegion | None = None,
    panel_anchor: PanelAnchor | None = None,
    text_alignment: TextAlignment = DEFAULT_TEXT_ALIGNMENT,
    subject_zoom: float = DEFAULT_SUBJECT_ZOOM,
    badge_background_luminance: float | None = None,
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
        panel_anchor=panel_anchor,
        text_alignment=text_alignment,
        subject_zoom=subject_zoom,
    )
    embedded_image = _embed_local_image(image_ref)
    sampled_luminance = resolve_badge_luminance(
        embedded_image,
        fmt,
        subject_zoom=subject_zoom,
        sampled_luminance=badge_background_luminance,
    )
    resolved_badge_theme = badge_theme(sampled_luminance)
    rule_ids = " ".join(rule.id for rule in load_rules(_GLO2GO_PROFILE_ID))
    root = ElementTree.Element(
        _svg_tag("svg"),
        {
            "version": "1.1",
            "width": str(fmt.width),
            "height": str(fmt.height),
            "viewBox": f"0 0 {fmt.width} {fmt.height}",
            "data-grid-step": str(comp.grid_step),
            "data-subject-zoom": f"{subject_zoom:.2f}",
            "data-design-rule-ids": rule_ids,
        },
    )

    background = _layer(root, "layer-background")
    background.set("data-subject-zoom", f"{subject_zoom:.2f}")
    ElementTree.SubElement(
        background,
        _svg_tag("image"),
        {
            "x": str(comp.photo_x),
            "y": str(comp.photo_y),
            "width": str(comp.photo_width),
            "height": str(comp.photo_height),
            "preserveAspectRatio": "xMidYMid slice",
            "href": embedded_image,
        },
    )

    panel = _layer(root, "layer-panel")
    panel.set("data-panel-anchor", comp.panel_anchor)
    panel.set("data-text-alignment", comp.text_alignment)
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

    content_x = _content_x(comp)
    headline_baseline = comp.panel_y + comp.panel_padding + comp.headline_line_height
    headline_layer = _layer(root, "layer-headline")
    _add_wrapped_text(
        headline_layer,
        lines=comp.headline_lines,
        x=content_x,
        first_baseline=headline_baseline,
        line_height=comp.headline_line_height,
        font_size=comp.headline_size,
        font_weight=760,
        fill=palette_ink,
        text_alignment=comp.text_alignment,
    )

    subhead_layer = _layer(root, "layer-subhead")
    headline_height = len(comp.headline_lines) * comp.headline_line_height
    subhead_baseline = (
        comp.panel_y
        + comp.panel_padding
        + headline_height
        + comp.grid_step
        + comp.body_line_height
    )
    if comp.subhead_lines:
        _add_wrapped_text(
            subhead_layer,
            lines=comp.subhead_lines,
            x=content_x,
            first_baseline=subhead_baseline,
            line_height=comp.body_line_height,
            font_size=comp.body_size,
            font_weight=430,
            fill=palette_ink,
            text_alignment=comp.text_alignment,
        )

    cta_layer = _layer(root, "layer-cta")
    if cta and cta.strip():
        subhead_height = 0
        if comp.subhead_lines:
            subhead_height = comp.grid_step + len(comp.subhead_lines) * comp.body_line_height
        cta_font_size = round(comp.body_size * 0.9)
        cta_padding_x = round(comp.body_size * 0.92)
        cta_height = comp.cta_height
        cta_width = min(
            comp.panel_width - 2 * comp.panel_padding,
            round(len(cta) * cta_font_size * 0.56 + 2 * cta_padding_x),
        )
        cta_x = _aligned_box_x(comp, cta_width)
        cta_y = (
            comp.panel_y
            + comp.panel_padding
            + headline_height
            + subhead_height
            + comp.grid_step
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
                "x": str(cta_x + round(cta_width / 2)),
                "y": str(cta_y + round(cta_height / 2)),
                "fill": palette_ground,
                "font-family": _SYSTEM_FONT,
                "font-size": str(cta_font_size),
                "font-weight": "750",
                "dominant-baseline": "middle",
                "text-anchor": "middle",
            },
        )
        cta_text.text = cta

    badge_layer = _layer(root, "layer-badge")
    badge_layer.set("data-badge-theme", resolved_badge_theme)
    badge_fill = palette_ground if resolved_badge_theme == "light" else palette_ink
    badge_ink = palette_ink if resolved_badge_theme == "light" else palette_ground
    ElementTree.SubElement(
        badge_layer,
        _svg_tag("rect"),
        {
            "x": str(comp.badge_x),
            "y": str(comp.badge_y),
            "width": str(comp.badge_width),
            "height": str(comp.badge_height),
            "rx": str(round(comp.badge_height / 2)),
            "fill": badge_fill,
            "stroke": palette_ink,
            "stroke-opacity": "0.12" if resolved_badge_theme == "light" else "0",
        },
    )
    if logo_ref:
        ElementTree.SubElement(
            badge_layer,
            _svg_tag("image"),
            {
                "x": str(comp.badge_x),
                "y": str(comp.badge_y),
                "width": str(comp.badge_width),
                "height": str(comp.badge_height),
                "preserveAspectRatio": "xMidYMid meet",
                "href": _embed_local_image(logo_ref),
            },
        )
    else:
        wordmark = ElementTree.SubElement(
            badge_layer,
            _svg_tag("text"),
            {
                "x": str(comp.badge_x + round(comp.badge_width / 2)),
                "y": str(comp.badge_y + round(comp.badge_height * 0.62)),
                "fill": badge_ink,
                "font-family": _SYSTEM_FONT,
                "font-size": str(round(comp.badge_height * 0.34)),
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
