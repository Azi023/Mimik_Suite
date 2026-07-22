"""Art-director — the 'think like a designer' brain that was the missing seam.

Turns a brand + frozen-brief context + pillar + topic + format into ONE technically-specified
image-generation prompt. The generated image is a BACKGROUND/scene only — headline, sub, CTA
and logo are composited by code afterwards (the hybrid rule), so the art-director must:

  1. express the brand's palette + imagery style + mood as a real creative-director would,
  2. reserve calm negative space in the zone where THIS template overlays text,
  3. forbid any text/letters/words/logos/watermarks/UI inside the generated image.

It runs the free Gemini TEXT seam as the art director (reasoning over the brief), with a
deterministic fallback prompt so a text-model hiccup never blocks a generation.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from mimik_contracts import Brand, ColorRole

from creative.adapters.base import ImageRequest
from creative.knowledge.feedback import rules_as_prompt_block
from creative.prompting import default_generate, parse_json_reply

# Where each template lays its text, so the art-director keeps that zone calm for the overlay.
_TEXT_ZONE_HINT: dict[str, str] = {
    "centered_hero": "the central third of the frame — keep it calm, low-contrast and unbusy",
    "lower_band": "the lower third of the frame — keep it clean and uncluttered",
    "soft_editorial": "the upper-centre and the margins — leave generous editorial negative space",
}

# Hard negatives: this is a background plate, never a finished poster.
_NEGATIVES = (
    "NO text, no words, no letters, no numbers, no captions, no watermark, no logo, "
    "no signage, no UI, no borders, no frame, no collage, no split-screen. "
    "A single cohesive photographic or illustrated scene only."
)

_SYSTEM = (
    "You are a senior art director and brand photographer. You write ONE vivid, specific "
    "image-generation prompt for a background plate that a designer will later composite "
    "headline text and a logo onto. You think in composition, subject, styling, lighting, "
    "lens/render, colour and mood — never in generic stock-photo clichés. You commit to a "
    "single strong subject and an intentional composition with real negative space. You honour "
    "the brand palette and imagery style exactly, and you NEVER put text or logos in the image."
)


def _palette_line(colors: list[ColorRole]) -> str:
    if not colors:
        return "(no brand palette supplied — use a restrained, cohesive palette)"
    return "; ".join(f"{c.name} {c.hex} ({c.usage})" if c.usage else f"{c.name} {c.hex}" for c in colors)


def _context_block(brand: Brand, pillar_name: str, topic: str, fmt_label: str, zone: str) -> str:
    t = brand.tokens
    return "\n".join(
        [
            f"BRAND: {brand.name} — {brand.niche or 'n/a'}",
            f"AUDIENCE: {brand.target_audience or 'n/a'}",
            f"BRAND VOICE: {brand.brand_voice or 'n/a'}  |  TONE: {', '.join(brand.tone_keywords) or 'n/a'}",
            f"IMAGERY STYLE (obey this): {brand.imagery_style or 'n/a'}",
            f"PALETTE: {_palette_line(t.colors)}",
            f"DO: {', '.join(brand.dos) or 'n/a'}",
            f"AVOID: {', '.join(brand.donts) or 'n/a'}",
            f"CONTENT PILLAR: {pillar_name}",
            f"THIS POST IS ABOUT: {topic}",
            f"FORMAT: {fmt_label}",
            f"TEXT-OVERLAY ZONE TO KEEP CALM: {zone}",
        ]
    )


def _instruction(context: str, rules: str) -> str:
    return (
        f"{rules}\n\n{_SYSTEM}\n\n{context}\n\n"
        "Write the image prompt now. Requirements:\n"
        "- One paragraph, 60–110 words, concrete and directive (subject, setting, styling, "
        "camera or illustration style, lighting, colour grade tied to the palette, mood).\n"
        "- Compose intentionally with clear negative space in the stated overlay zone.\n"
        f"- End with these hard negatives verbatim: {_NEGATIVES}\n\n"
        'Reply as STRICT JSON only: {"image_prompt": "...", "art_direction_notes": "..."}'
    )


def _fallback_prompt(
    brand: Brand,
    pillar_name: str,
    topic: str,
    zone: str,
    rules: str,
) -> str:
    """Deterministic art-direction if the text model is unavailable — never blocks a run."""
    palette = _palette_line(brand.tokens.colors)
    style = brand.imagery_style or "clean editorial photography with soft natural light"
    return (
        f"{rules}\n\nA refined, on-brand background scene for {brand.name} "
        f"({brand.niche or 'brand'}) "
        f"about '{topic}', pillar: {pillar_name}. {style}. Single strong subject, intentional "
        f"composition with generous negative space in {zone}. Colour grade drawn from the brand "
        f"palette: {palette}. Soft directional light, shallow depth, premium and uncluttered mood. "
        f"{_NEGATIVES}"
    )


def build_image_request(
    brand: Brand,
    pillar_name: str,
    topic: str,
    fmt_label: str,
    width: int,
    height: int,
    *,
    template_key: str,
    generate: Callable[[str], str] | None = None,
) -> ImageRequest:
    """Art-direct one background plate → ImageRequest. Uses the free Gemini text seam as the
    art director; falls back to a deterministic prompt on any text-model failure."""
    zone = _TEXT_ZONE_HINT.get(template_key, "the centre of the frame")
    context = _context_block(brand, pillar_name, topic, fmt_label, zone)
    rules = rules_as_prompt_block(brand.slug)
    if generate is None:
        generate, _model = default_generate()

    prompt_text: str
    notes = ""
    try:
        reply = generate(_instruction(context, rules))
        data = parse_json_reply(reply)
        prompt_text = str(data.get("image_prompt") or "").strip()
        notes = str(data.get("art_direction_notes") or "").strip()
        if len(prompt_text) < 40:  # too thin to be a real brief → fall back
            raise ValueError("image_prompt too short")
    except (ValueError, KeyError, json.JSONDecodeError, RuntimeError):
        prompt_text = _fallback_prompt(brand, pillar_name, topic, zone, rules)
        notes = "deterministic fallback (text model unavailable or non-compliant)"

    return ImageRequest(
        prompt=prompt_text,
        width=width,
        height=height,
        params={"pillar": pillar_name, "topic": topic, "art_direction_notes": notes},
    )
