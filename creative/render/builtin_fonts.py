"""Curated, repository-bundled fonts available for brand materialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FontCategory = Literal["sans-serif", "serif", "display"]

_BUILTIN_ROOT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "builtin"


@dataclass(frozen=True, slots=True)
class BuiltinFont:
    key: str
    family: str
    category: FontCategory
    preview_text: str
    regular_path: Path
    bold_path: Path


def _font(
    *,
    key: str,
    family: str,
    category: FontCategory,
    preview_text: str,
    regular_filename: str,
    bold_filename: str | None = None,
) -> BuiltinFont:
    family_dir = _BUILTIN_ROOT / key
    regular_path = family_dir / regular_filename
    return BuiltinFont(
        key=key,
        family=family,
        category=category,
        preview_text=preview_text,
        regular_path=regular_path,
        bold_path=family_dir / bold_filename if bold_filename else regular_path,
    )


# Google Fonts currently publishes static Regular/Bold files for Poppins and Lato.
# The other six families expose one upright variable TTF; that file supplies both paths.
_BUILTIN_FONTS: tuple[BuiltinFont, ...] = (
    _font(
        key="poppins",
        family="Poppins",
        category="sans-serif",
        preview_text="Bold ideas, clearly made.",
        regular_filename="Poppins-Regular.ttf",
        bold_filename="Poppins-Bold.ttf",
    ),
    _font(
        key="montserrat",
        family="Montserrat",
        category="sans-serif",
        preview_text="Modern brands move with purpose.",
        regular_filename="Montserrat[wght].ttf",
    ),
    _font(
        key="playfair-display",
        family="Playfair Display",
        category="serif",
        preview_text="Timeless stories deserve beautiful type.",
        regular_filename="PlayfairDisplay[wght].ttf",
    ),
    _font(
        key="inter",
        family="Inter",
        category="sans-serif",
        preview_text="Designed for clarity at every size.",
        regular_filename="Inter[opsz,wght].ttf",
    ),
    _font(
        key="lato",
        family="Lato",
        category="sans-serif",
        preview_text="Warm, confident, and easy to read.",
        regular_filename="Lato-Regular.ttf",
        bold_filename="Lato-Bold.ttf",
    ),
    _font(
        key="nunito",
        family="Nunito",
        category="sans-serif",
        preview_text="Friendly shapes for human messages.",
        regular_filename="Nunito[wght].ttf",
    ),
    _font(
        key="open-sans",
        family="Open Sans",
        category="sans-serif",
        preview_text="Open communication starts here.",
        regular_filename="OpenSans[wdth,wght].ttf",
    ),
    _font(
        key="raleway",
        family="Raleway",
        category="sans-serif",
        preview_text="Elegant details make the difference.",
        regular_filename="Raleway[wght].ttf",
    ),
)

_BUILTIN_BY_KEY = {font.key: font for font in _BUILTIN_FONTS}


def list_builtin_fonts() -> list[BuiltinFont]:
    """Return the curated library in stable display order."""
    return list(_BUILTIN_FONTS)


def get_builtin_font(key: str) -> BuiltinFont | None:
    """Resolve a built-in family by its stable slug."""
    return _BUILTIN_BY_KEY.get(key)
