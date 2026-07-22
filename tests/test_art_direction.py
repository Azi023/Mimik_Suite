"""Art-director tests: LLM path, fallback path, and the hard 'no text/logo' negatives."""
from __future__ import annotations

from mimik_contracts import Brand, BrandTokens, ColorRole

from creative.art_direction import build_image_request, _NEGATIVES


def _brand() -> Brand:
    return Brand(
        tenant_id="t1",
        client_id="c1",
        slug="simply-nikah",
        name="Simply Nikah",
        niche="Muslim matrimony app",
        target_audience="Practising Muslim singles seeking marriage",
        brand_voice="warm, respectful, modern",
        tone_keywords=["warm", "trustworthy"],
        imagery_style="soft natural-light lifestyle photography, respectful and elegant",
        dos=["show genuine warmth"],
        donts=["no clichés"],
        tokens=BrandTokens(colors=[ColorRole(name="Simply Pink", hex="#FD62AD", usage="primary")]),
    )


def test_llm_path_uses_model_prompt() -> None:
    prompts: list[str] = []

    def fake_gen(prompt: str) -> str:
        prompts.append(prompt)
        return '{"image_prompt": "A serene sunrise over a calm couple walking, ample sky negative space for text.", "art_direction_notes": "warm"}'

    req = build_image_request(
        _brand(), "Promotional", "Find your partner the halal way", "Instagram Post (1:1)",
        1080, 1080, template_key="centered_hero", generate=fake_gen,
    )
    assert "sunrise" in req.prompt
    assert req.width == 1080 and req.height == 1080
    assert req.params["pillar"] == "Promotional"
    assert prompts[0].startswith("Design rules to obey:\n")
    assert "- L2:" in prompts[0]


def test_fallback_on_bad_reply() -> None:
    def bad_gen(_prompt: str) -> str:
        return "not json at all"

    req = build_image_request(
        _brand(), "Educational", "How matchmaking works", "Instagram Post (1:1)",
        1080, 1080, template_key="lower_band", generate=bad_gen,
    )
    assert _NEGATIVES in req.prompt  # deterministic fallback still forbids text/logos
    assert "Simply Nikah" in req.prompt
