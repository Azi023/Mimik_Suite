"""Validated loader for bundled Simply Nikah SVG vector fragments."""

from __future__ import annotations

import math
import re
from pathlib import Path
from xml.etree import ElementTree

_VECTOR_DIR = Path(__file__).resolve().parents[2] / "assets" / "vectors" / "nikah"
_LICENSE_COMMENT = (
    "Hand-authored placeholder — REPLACE with a curated CC0 asset at this path."
)
_SAFE_NAME = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*\Z")
_FACIAL_MARKER = re.compile(
    r"(?:^|[-_:\s])(face|facial|eye|eyes|eyebrow|eyebrows|iris|mouth|nose|"
    r"lip|lips|pupil|pupils)(?:$|[-_:\s])",
    re.IGNORECASE,
)
_UNSAFE_ELEMENTS = frozenset({"foreignobject", "image", "script"})
_SVG_NS = "http://www.w3.org/2000/svg"

ElementTree.register_namespace("", _SVG_NS)


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1].lower()


def _number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _asset_path(name: str) -> Path:
    if not _SAFE_NAME.fullmatch(name):
        raise ValueError(f"Invalid Nikah vector name: {name!r}")
    path = _VECTOR_DIR / f"{name}.svg"
    if not path.is_file():
        choices = ", ".join(list_vectors()) or "(none)"
        raise KeyError(f"Unknown Nikah vector {name!r}; choose from: {choices}")
    return path


def _parse_asset(path: Path) -> tuple[ElementTree.Element, tuple[float, float, float, float]]:
    source = path.read_text(encoding="utf-8")
    if _LICENSE_COMMENT not in source:
        raise ValueError(f"Nikah vector {path.name!r} is missing its license comment")

    parser = ElementTree.XMLParser(target=ElementTree.TreeBuilder(insert_comments=True))
    try:
        root = ElementTree.fromstring(source, parser=parser)
    except ElementTree.ParseError as exc:
        raise ValueError(f"Nikah vector {path.name!r} is not valid SVG XML: {exc}") from exc
    if _local_name(root.tag) != "svg":
        raise ValueError(f"Nikah vector {path.name!r} must have an <svg> root")

    raw_view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
    if len(raw_view_box) != 4:
        raise ValueError(f"Nikah vector {path.name!r} must declare a four-number viewBox")
    try:
        view_box = tuple(float(part) for part in raw_view_box)
    except ValueError as exc:
        raise ValueError(f"Nikah vector {path.name!r} has a non-numeric viewBox") from exc
    if not all(math.isfinite(part) for part in view_box):
        raise ValueError(f"Nikah vector {path.name!r} has a non-finite viewBox")
    if view_box[2] <= 0 or view_box[3] <= 0:
        raise ValueError(f"Nikah vector {path.name!r} must have a positive viewBox size")

    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        tag = _local_name(element.tag)
        if tag in _UNSAFE_ELEMENTS:
            raise ValueError(f"Nikah vector {path.name!r} contains unsafe SVG element <{tag}>")
        if element.attrib.get("data-figure") == "true":
            if element.attrib.get("data-faceless") != "true":
                raise ValueError(
                    f"Nikah vector {path.name!r} has a figure missing data-faceless='true'"
                )
        for attribute, value in element.attrib.items():
            attribute_name = _local_name(attribute)
            if attribute_name.startswith("on"):
                raise ValueError(
                    f"Nikah vector {path.name!r} contains unsafe event attribute "
                    f"{attribute_name!r}"
                )
            if attribute_name == "data-faceless":
                continue
            if _FACIAL_MARKER.search(attribute_name) or _FACIAL_MARKER.search(value):
                raise ValueError(
                    f"Nikah vector {path.name!r} contains a facial-feature marker"
                )
        if element.text and _FACIAL_MARKER.search(element.text):
            raise ValueError(f"Nikah vector {path.name!r} contains a facial-feature marker")

    return root, view_box


def list_vectors() -> tuple[str, ...]:
    """Return the names of all bundled Nikah SVG assets."""
    if not _VECTOR_DIR.is_dir():
        return ()
    return tuple(sorted(path.stem for path in _VECTOR_DIR.glob("*.svg") if path.is_file()))


def get_vector(
    name: str,
    *,
    x: float = 0.0,
    y: float = 0.0,
    scale: float = 1.0,
    fill: str | None = None,
) -> str:
    """Load, validate, and compose a bundled SVG as a normalized ``<g>`` fragment."""
    if not all(math.isfinite(value) for value in (x, y, scale)):
        raise ValueError("Nikah vector transform values must be finite")
    if scale <= 0:
        raise ValueError("Nikah vector scale must be positive")

    path = _asset_path(name)
    root, (min_x, min_y, _width, _height) = _parse_asset(path)
    transform = f"translate({_number(x)} {_number(y)}) scale({_number(scale)})"
    if min_x or min_y:
        transform += f" translate({_number(-min_x)} {_number(-min_y)})"

    attributes = {"data-vector": name, "transform": transform}
    if fill is not None:
        attributes["fill"] = fill
    for marker in ("data-figure", "data-faceless"):
        if marker in root.attrib:
            attributes[marker] = root.attrib[marker]

    group = ElementTree.Element(f"{{{_SVG_NS}}}g", attributes)
    for child in root:
        if isinstance(child.tag, str):
            group.append(child)
    return ElementTree.tostring(group, encoding="unicode", short_empty_elements=True)
