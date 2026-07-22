"""Ordered image-source routing without network access or paid image spend."""

from __future__ import annotations

from pathlib import Path

import pytest
from mimik_contracts import Brand, BrandTokens, ImageBackend

from api.services import creative_generation
from creative.adapters import ImageRequest, ImageResult, PaidImageSpendNotApproved
from creative.art_direction import _NEGATIVES, build_image_request
from creative.references.gather import ReferenceCandidate
from creative.style_profile import get_style_profile
from creative.vision.text_region import TextRegion


def _brand(*, slug: str, name: str, niche: str) -> Brand:
    return Brand(
        tenant_id="tenant-1",
        client_id="client-1",
        slug=slug,
        name=name,
        niche=niche,
        tokens=BrandTokens(),
    )


def _image_request(*_args: object, **_kwargs: object) -> ImageRequest:
    return ImageRequest(
        prompt="A deterministic test-only image prompt with no external model call.",
        width=1080,
        height=1080,
    )


async def test_island_cart_skips_product_cutout_and_uses_licensed_stock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stock_url = "https://images.pexels.com/photos/123/pexels-photo-123.png"

    async def fake_gather(
        query: str,
        *,
        limit: int,
        source: str,
    ) -> list[ReferenceCandidate]:
        assert "marketplace" in query.casefold()
        assert "desk setup" in query.casefold()
        assert (limit, source) == (1, "pexels")
        return [
            ReferenceCandidate(
                title="Desk lifestyle",
                url=stock_url,
                thumbnail=None,
                source="pexels",
                tags=[],
                license="Pexels License",
                width=1080,
                height=1080,
            )
        ]

    def fake_download(url: str, destination_dir: Path) -> Path:
        assert url == stock_url
        destination = destination_dir / "source.png"
        destination.write_bytes(b"stock-image")
        return destination

    monkeypatch.setattr(creative_generation.reference_gather, "gather_references", fake_gather)
    monkeypatch.setattr(creative_generation, "_download_pexels_photo", fake_download)

    image_path, reference_urls, source_kind = await creative_generation._source_image(
        brand=_brand(slug="island-cart", name="Island Cart", niche="Sri Lankan marketplace"),
        industry="E-commerce",
        pillar="Product education",
        topic="Desk setup",
        format_key="ig_post",
        profile=get_style_profile("island-cart"),
        destination_dir=tmp_path,
    )

    assert source_kind == "licensed_stock"
    assert reference_urls == [stock_url]
    assert image_path.read_bytes() == b"stock-image"


async def test_simply_nikah_paid_gate_falls_back_to_brand_placeholder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def deny_paid_generation(
        _request: ImageRequest,
        purpose: str,
    ) -> ImageResult | None:
        assert purpose == "hero"
        raise PaidImageSpendNotApproved("operator gate is closed")

    monkeypatch.setattr(creative_generation.art_direction, "build_image_request", _image_request)
    monkeypatch.setattr(creative_generation, "generate_with_fallback", deny_paid_generation)

    image_path, reference_urls, source_kind = await creative_generation._source_image(
        brand=_brand(slug="simply-nikah", name="Simply Nikah", niche="Muslim matrimony"),
        industry="Matrimonial service",
        pillar="Trust and safety",
        topic="Protected introductions",
        format_key="ig_post",
        profile=get_style_profile("simply-nikah"),
        destination_dir=tmp_path,
    )

    assert source_kind == "brand_placeholder"
    assert reference_urls == []
    assert image_path.name == "source.svg"


async def test_simply_nikah_ai_illustration_is_copied_into_creative_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generated_path = tmp_path / "artifacts" / "generated.png"
    generated_path.parent.mkdir()
    generated_path.write_bytes(b"generated-illustration")
    destination_dir = tmp_path / "creative"
    destination_dir.mkdir()

    async def fake_generate(
        request: ImageRequest,
        purpose: str,
    ) -> ImageResult | None:
        assert request.prompt.startswith("A deterministic")
        assert purpose == "hero"
        return ImageResult(
            backend=ImageBackend.OPENROUTER,
            artifact_ref=str(generated_path),
            prompt=request.prompt,
            model="test-model",
        )

    monkeypatch.setattr(creative_generation.art_direction, "build_image_request", _image_request)
    monkeypatch.setattr(creative_generation, "generate_with_fallback", fake_generate)

    image_path, reference_urls, source_kind = await creative_generation._source_image(
        brand=_brand(slug="simply-nikah", name="Simply Nikah", niche="Muslim matrimony"),
        industry="Matrimonial service",
        pillar="Trust and safety",
        topic="Protected introductions",
        format_key="ig_post",
        profile=get_style_profile("simply-nikah"),
        destination_dir=destination_dir,
    )

    assert source_kind == "ai_illustration"
    assert reference_urls == []
    assert image_path == destination_dir / "source.png"
    assert image_path.read_bytes() == b"generated-illustration"


async def test_ai_source_uses_supplied_request_without_rebuilding_prompt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generated_path = tmp_path / "artifacts" / "generated.png"
    generated_path.parent.mkdir()
    generated_path.write_bytes(b"generated-illustration")
    destination_dir = tmp_path / "creative"
    destination_dir.mkdir()
    request = _image_request()

    def unexpected_rebuild(*_args: object, **_kwargs: object) -> ImageRequest:
        pytest.fail("a supplied image request must be the prompt-DNA source of truth")

    async def fake_generate(
        received_request: ImageRequest,
        purpose: str,
    ) -> ImageResult | None:
        assert received_request is request
        assert purpose == "hero"
        return ImageResult(
            backend=ImageBackend.OPENROUTER,
            artifact_ref=str(generated_path),
            prompt=received_request.prompt,
            model="test-model",
        )

    monkeypatch.setattr(
        creative_generation.art_direction,
        "build_image_request",
        unexpected_rebuild,
    )
    monkeypatch.setattr(creative_generation, "generate_with_fallback", fake_generate)

    image_path, _, source_kind = await creative_generation._source_image(
        brand=_brand(slug="simply-nikah", name="Simply Nikah", niche="Muslim matrimony"),
        industry="Matrimonial service",
        pillar="Trust and safety",
        topic="Protected introductions",
        format_key="ig_post",
        image_request=request,
        profile=get_style_profile("simply-nikah"),
        destination_dir=destination_dir,
    )

    assert source_kind == "ai_illustration"
    assert image_path.read_bytes() == b"generated-illustration"


async def test_safe_text_region_runs_for_ai_realistic_but_not_ai_illustration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    async def fake_region(image_ref: str) -> TextRegion:
        calls.append(image_ref)
        return TextRegion(region="top_left", reason="clear negative space")

    monkeypatch.setattr(creative_generation.vision_text_region, "find_text_region", fake_region)
    image_path = tmp_path / "source.png"
    image_path.write_bytes(b"image")

    realistic_region = await creative_generation._safe_text_region(
        image_path,
        source_kind="ai_realistic",
    )
    illustration_region = await creative_generation._safe_text_region(
        image_path,
        source_kind="ai_illustration",
    )

    assert realistic_region == "top_left"
    assert illustration_region is None
    assert calls == [str(image_path)]


def test_simply_nikah_prompt_enforces_medium_and_modesty_guardrails() -> None:
    brand = _brand(slug="simply-nikah", name="Simply Nikah", niche="Muslim matrimony")

    def fake_generate(_prompt: str) -> str:
        return (
            '{"image_prompt":"A calm matrimonial introduction scene with generous central '
            'negative space and a restrained pink and plum palette.",'
            '"art_direction_notes":"test"}'
        )

    request = build_image_request(
        brand,
        "Trust and safety",
        "Protected introductions",
        "Instagram Post (1:1)",
        1080,
        1080,
        template_key="centered_hero",
        profile_id="simply-nikah",
        generate=fake_generate,
    )
    prompt = request.prompt.casefold()

    assert "flat vector illustration" in prompt
    assert "faceless or a silhouette" in prompt
    assert "never use real photographs of people" in prompt
    assert "modesty and haya" in prompt
    assert request.prompt.endswith(_NEGATIVES)
