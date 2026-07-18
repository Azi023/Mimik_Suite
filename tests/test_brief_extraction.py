"""Extraction unit tests — pure, network-free, against a FIXED HTML fixture string.

The load-bearing invariant: extraction reports only what the evidence shows and fabricates
nothing. A page with no colors/fonts must yield empty tokens, not invented ones.
"""

from __future__ import annotations

import pytest

from api.services.brief_extraction import (
    build_snapshot,
    extract_brief_sections,
    extract_brief_sections_from_html,
    extract_colors,
    extract_fonts,
)

FIXTURE = """
<html>
<head>
  <title>RCD Central — Dental Care</title>
  <meta name="description" content="A modern family dental clinic in Colombo.">
  <style>
    :root { --brand: #0A7E8C; }
    body { color: #0A7E8C; background: #FFFFFF; font-family: "Poppins", Arial, sans-serif; }
    h1 { color: #0a7e8c; font-family: 'Merriweather', serif; }
    .cta { background: #ff6600; font-family: sans-serif; }
  </style>
</head>
<body>
  <h1>Smiles, done right.</h1>
  <p style="color:#0A7E8C">Book your appointment today.</p>
</body>
</html>
"""


def test_colors_extracted_and_ranked() -> None:
    colors = extract_colors(FIXTURE)
    hexes = [c.hex for c in colors]
    # The teal appears most often -> ranked first, labeled primary. Hex is normalized lowercase 6-digit.
    assert colors[0].hex == "#0a7e8c"
    assert colors[0].name == "primary"
    assert "#ffffff" in hexes
    assert "#ff6600" in hexes


def test_fonts_extracted_skips_generics() -> None:
    typo = extract_fonts(FIXTURE)
    # First real family = heading; second = body. Generic 'sans-serif'/'serif'/'Arial-after' skipped.
    assert typo.heading_font == "Poppins"
    assert typo.body_font == "Merriweather"


def test_snapshot_from_title_meta_h1() -> None:
    snap = build_snapshot(FIXTURE)
    assert snap is not None
    assert "RCD Central" in snap
    assert "family dental clinic" in snap
    assert "Smiles, done right." in snap


def test_full_sections_no_fabrication() -> None:
    sections = extract_brief_sections_from_html(FIXTURE)
    assert sections.snapshot is not None
    assert sections.tokens.colors[0].hex == "#0a7e8c"
    assert sections.tokens.typography.heading_font == "Poppins"
    # §2 logo and §6-9 are NOT auto-fabricated — they stay empty/None for the designer.
    assert sections.logo_notes is None
    assert sections.tokens.logo.ref is None
    assert sections.imagery_style is None
    assert sections.guardrails_dos == []
    assert sections.references == []


def test_empty_page_fabricates_nothing() -> None:
    sections = extract_brief_sections_from_html("<html><body></body></html>")
    assert sections.snapshot is None
    assert sections.tokens.colors == []
    assert sections.tokens.typography.heading_font is None
    assert sections.voice_tone is None  # no snapshot -> no voice note either


async def test_extract_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError):
        await extract_brief_sections("file:///etc/passwd")
