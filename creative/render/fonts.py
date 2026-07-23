"""Brand-font embedding for the code-composited render path (M-10 / Lane C).

The compositor rasterizes an SVG/HTML document through Playwright (Chromium), which fully
supports ``@font-face`` with ``src: url(data:...)`` — so an uploaded brand font renders in
generated creatives without any font install on the host. This module mirrors the logo
pattern (``svg._embed_local_image``): given a font FILE (a stored ``AssetKind.FONT``
``local_path``, or a ``data:font/...`` URI), it returns a self-contained ``@font-face`` block
with the bytes inlined as a base64 data URI plus the ``font-family`` name to apply.

Optional + backward-compatible by design: callers only reach for this when a brand font is
resolved; with no font ref the render path is unchanged (byte-identical).

Supported formats match the upload gate (`api.services.brand_memory.FONT_MIMES`): ttf, otf,
woff2 (woff is also tolerated on the way in for completeness).
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path

# suffix -> (mime, CSS ``format(...)`` hint). The hint lets Chromium pick the right decoder
# without sniffing; woff2 in particular needs its own hint (it is NOT interchangeable with woff).
_FONT_BY_SUFFIX: dict[str, tuple[str, str]] = {
    ".ttf": ("font/ttf", "truetype"),
    ".otf": ("font/otf", "opentype"),
    ".woff": ("font/woff", "woff"),
    ".woff2": ("font/woff2", "woff2"),
}
# Accepted data-URI mimes -> CSS format hint. Tolerate the legacy application/* spellings a
# browser/OS might have stamped, but the family of formats stays the same allow-list.
_FORMAT_BY_MIME: dict[str, str] = {
    "font/ttf": "truetype",
    "font/otf": "opentype",
    "font/woff": "woff",
    "font/woff2": "woff2",
    "application/font-woff2": "woff2",
    "application/font-woff": "woff",
    "application/x-font-ttf": "truetype",
    "application/x-font-truetype": "truetype",
    "application/x-font-opentype": "opentype",
    "application/font-sfnt": "truetype",
    "application/vnd.ms-opentype": "opentype",
}
# The family name is interpolated straight into CSS — keep it to an internal, injection-proof
# token. Callers pass fixed constants (e.g. "MimikBrandHeading"), never client text.
_FAMILY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]{0,63}$")


class FontEmbedError(ValueError):
    """A font ref could not be embedded (missing file, unknown format, bad family name)."""


@dataclass(frozen=True)
class EmbeddedFont:
    """A brand font resolved into a drop-in ``@font-face`` block plus the family to apply.

    ``family`` is what a ``font-family`` declaration should reference; ``face_css`` is the
    complete ``@font-face{...}`` rule (self-contained — the font bytes are inlined) to drop
    into the document's ``<style>``.
    """

    family: str
    face_css: str


def _validate_family(family: str) -> str:
    if not _FAMILY_RE.match(family):
        raise FontEmbedError(
            "font family name must be an internal token (letters/digits/space/_/- , "
            f"letter-initial, <=64 chars); got {family!r}"
        )
    return family


def _resolve_data_uri(font_ref: str) -> tuple[str, str]:
    """Return (data_uri, format_hint) for a ``data:font/...;base64,...`` ref."""
    header, _, _payload = font_ref.partition(",")
    if ";base64" not in header:
        raise FontEmbedError("font data URIs must be base64 encoded")
    mime = header[len("data:") :].split(";", 1)[0].strip().lower()
    fmt = _FORMAT_BY_MIME.get(mime)
    if fmt is None:
        supported = ", ".join(sorted(_FORMAT_BY_MIME))
        raise FontEmbedError(f"unsupported font data-URI mime {mime!r}; expected one of: {supported}")
    return font_ref, fmt


def _resolve_local_path(font_ref: str) -> tuple[str, str]:
    """Return (data_uri, format_hint) for a local font file path."""
    path = Path(font_ref)
    if not path.is_file():
        raise FontEmbedError(f"font path is not a local file: {font_ref}")
    entry = _FONT_BY_SUFFIX.get(path.suffix.lower())
    if entry is None:
        supported = ", ".join(sorted(_FONT_BY_SUFFIX))
        raise FontEmbedError(f"font must use one of these extensions: {supported}")
    mime, fmt = entry
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}", fmt


def embed_font_face(font_ref: str, *, family: str) -> EmbeddedFont:
    """Embed a font file as a self-contained ``@font-face`` block under ``family``.

    ``font_ref`` is either a ``data:font/...;base64,...`` URI or a local path to a stored
    ``AssetKind.FONT`` file (``.ttf`` / ``.otf`` / ``.woff2``; ``.woff`` tolerated). The
    returned ``face_css`` inlines the bytes as a data URI, so the render stays deterministic
    and offline — exactly like the logo embedding.

    The face declares a wide ``font-weight`` range so a single static file satisfies every
    weight the templates request (headline 760, body 430, …) WITHOUT the browser synthesizing
    a faux-bold — the brand file renders as authored.
    """
    _validate_family(family)
    if font_ref.startswith("data:"):
        data_uri, fmt = _resolve_data_uri(font_ref)
    else:
        data_uri, fmt = _resolve_local_path(font_ref)
    face_css = (
        "@font-face{"
        f"font-family:'{family}';"
        "font-style:normal;"
        "font-weight:1 1000;"
        "font-display:block;"
        f"src:url({data_uri}) format('{fmt}')"
        "}"
    )
    return EmbeddedFont(family=family, face_css=face_css)


def font_family_stack(family: str, fallback: str) -> str:
    """A ``font-family`` value that prefers the brand ``family`` and falls back to ``fallback``.

    Fallback keeps text legible if the face fails to decode, and preserves metrics-similar
    rendering for the un-branded case.
    """
    return f"'{family}', {fallback}"


# ADOPTERS of embed_font_face / font_family_stack:
#   - creative/export/svg.py::render_creative_svg          (done — heading/body font refs)
#   - creative/render/glo2go_templates.py::render_glo2go   (done — heading/body font refs)
#   - creative/render/nikah_templates.py                   (TODO, owned by another lane):
#       nikah renders HTML through the same Playwright compositor, so it adopts identically —
#       add optional heading_font_ref/body_font_ref params, embed_font_face(...) each, drop the
#       face_css into the template <style>, and set font-family via font_family_stack(...) on the
#       heading/body/CTA elements. No nikah files are touched by this lane.

