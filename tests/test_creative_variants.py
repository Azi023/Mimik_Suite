"""M-05 A/B variant generation + pick capture (fuel for the M-06 taste/learning loop).

These exercise the service layer directly (routes are a separate lane): two variants produced
with distinct free design levers, both persisted + tenant-scoped, the single-generate path left
unchanged (regression), QA run per variant, and record_variant_pick emitting EXACTLY ONE
preference signal via the shared signal seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient
from mimik_contracts import CopyBlock, CreativeManifest, LayerKind

from api.core.auth import Principal
from api.db import repo
from api.db.session import get_session
from api.main import app
from api.services import creative_generation
from api.services.creative_generation import GenerateCreativeRequest
from creative.qa.checks import QAReport


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True)
class _Setup:
    tenant_id: str
    owner_token: str
    client_id: str


async def _session():
    generator = app.dependency_overrides[get_session]()
    return generator, await generator.__anext__()


async def _create_setup(
    client: AsyncClient,
    *,
    tenant_slug: str = "mimik",
    brand_slug: str = "acme-generic",
    industry: str | None = None,
) -> _Setup:
    tenant = (
        await client.post(
            "/tenants",
            json={"name": tenant_slug.title(), "slug": tenant_slug},
            headers=superadmin_headers(),
        )
    ).json()
    owner_token = tenant["access_token"]
    tenant_id = tenant["tenant"]["id"]

    body: dict[str, object] = {"name": f"Client {brand_slug}"}
    if industry is not None:
        body["industry"] = industry
    client_id = (
        await client.post("/clients", json=body, headers=_auth(owner_token))
    ).json()["id"]

    brand = await client.post(
        "/brands",
        json={
            "client_id": client_id,
            "name": f"Brand {brand_slug}",
            "slug": brand_slug,
            "tokens": {
                "colors": [
                    {"name": "primary", "hex": "#112233"},
                    {"name": "ground", "hex": "#FFFFFF"},
                ]
            },
        },
        headers=_auth(owner_token),
    )
    assert brand.status_code == 201, brand.text
    return _Setup(tenant_id=tenant_id, owner_token=owner_token, client_id=client_id)


def _team_principal(tenant_id: str) -> Principal:
    return Principal(tenant_id=tenant_id, role="team", user_id="designer-1", client_id=None)


def _stub_generation(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Stub image sourcing + copy + art direction, and record the render_params each variant
    render receives so tests can assert the levers actually diverged. QAReport is returned green."""
    render_calls: list[dict] = []

    async def fake_source_image(**kwargs: object) -> tuple[Path, list[str], str]:
        destination = kwargs["destination_dir"]
        assert isinstance(destination, Path)
        source = destination / "source.svg"
        source.write_text("<svg/>", encoding="utf-8")
        return source, [], "brand_placeholder"

    class _FakeRequest:
        params: dict = {}
        prompt = "prompt"

    def fake_build_request(*_args: object, **_kwargs: object) -> _FakeRequest:
        return _FakeRequest()

    async def fake_render(**kwargs: object) -> tuple[Path, Path, None, QAReport]:
        render_calls.append(dict(kwargs["render_params"]))
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text("<svg/>", encoding="utf-8")
        preview_path.write_bytes(b"preview")
        return svg_path, preview_path, None, QAReport(passed=True, failures=[])

    monkeypatch.setattr(creative_generation, "_source_image", fake_source_image)
    monkeypatch.setattr(
        creative_generation.art_direction, "build_image_request", fake_build_request
    )
    monkeypatch.setattr(
        creative_generation.copy_l0,
        "draft_copy",
        lambda *_a, **_k: CopyBlock(headline="Protect what matters most"),
    )
    monkeypatch.setattr(creative_generation, "_render_creative_artifacts", fake_render)
    return render_calls


async def test_variants_produce_two_distinct_levers_persisted_and_scoped(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)

    generator, session = await _session()
    try:
        result = await creative_generation.generate_client_creative_variants(
            session,
            principal=_team_principal(setup.tenant_id),
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="hydration", pillar="Education"),
        )
    finally:
        await generator.aclose()

    creative_id = result.creative.id

    # Two renders, distinct free levers (generic profile → headline alignment).
    assert len(render_calls) == 2
    assert render_calls[0]["text_alignment"] == "left"
    assert render_calls[1]["text_alignment"] == "center"

    # Reload the persisted doc: both variants recorded on the manifest, tenant-scoped, none picked.
    generator, session = await _session()
    try:
        row = await repo.get_creative_doc(
            session, tenant_id=setup.tenant_id, creative_doc_id=creative_id
        )
        assert row is not None
        assert row.tenant_id == setup.tenant_id
        manifest = CreativeManifest.model_validate(row.manifest)

        # A different tenant cannot see the variant-set creative (locked #2).
        assert (
            await repo.get_creative_doc(
                session, tenant_id="someone-else", creative_doc_id=creative_id
            )
            is None
        )
    finally:
        await generator.aclose()

    assert len(manifest.variants) == 2
    levers = {(v.lever_key, v.lever_value) for v in manifest.variants}
    assert levers == {("text_alignment", "left"), ("text_alignment", "center")}
    assert manifest.variant_selected_id is None
    assert all(not v.selected for v in manifest.variants)
    assert all(v.qa_passed for v in manifest.variants)
    # Each variant recorded how it was produced + its own rendered artifacts (both persisted).
    for variant in manifest.variants:
        assert variant.preview_ref and Path(variant.preview_ref).is_file()
        assert variant.svg_ref and Path(variant.svg_ref).is_file()


async def test_simply_nikah_variants_use_two_archetypes(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation(monkeypatch)
    setup = await _create_setup(
        client,
        tenant_slug="nikah-agency",
        brand_slug="simply-nikah",
        industry="matrimonial",
    )

    generator, session = await _session()
    try:
        result = await creative_generation.generate_client_creative_variants(
            session,
            principal=_team_principal(setup.tenant_id),
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="trust", pillar="Awareness"),
        )
    finally:
        await generator.aclose()

    generator, session = await _session()
    try:
        row = await repo.get_creative_doc(
            session, tenant_id=setup.tenant_id, creative_doc_id=result.creative.id
        )
        manifest = CreativeManifest.model_validate(row.manifest)
    finally:
        await generator.aclose()

    values = {v.lever_value for v in manifest.variants}
    assert values == {"highlighted_word_hero", "protection_symbol_hero"}
    assert all(v.lever_key == "nikah_archetype" for v in manifest.variants)


async def test_qa_runs_per_variant(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Don't stub _render_creative_artifacts: stub only the render/rasterize/QA leaves, so the
    real orchestration invokes run_live_qa once per variant."""
    monkeypatch.chdir(tmp_path)
    setup = await _create_setup(client)

    qa_calls: list[str] = []

    async def fake_source_image(**kwargs: object) -> tuple[Path, list[str], str]:
        destination = kwargs["destination_dir"]
        source = destination / "source.svg"
        source.write_text("<svg/>", encoding="utf-8")
        return source, [], "brand_placeholder"

    class _FakeRequest:
        params: dict = {}
        prompt = "prompt"

    async def fake_qa(*_args: object, **kwargs: object) -> QAReport:
        qa_calls.append(str(kwargs.get("source_kind")))
        return QAReport(passed=True, failures=[])

    async def fake_rasterize(_svg: str, _fmt: str) -> bytes:
        return b"preview"

    monkeypatch.setattr(creative_generation, "_source_image", fake_source_image)
    monkeypatch.setattr(
        creative_generation.art_direction,
        "build_image_request",
        lambda *_a, **_k: _FakeRequest(),
    )
    monkeypatch.setattr(
        creative_generation.copy_l0,
        "draft_copy",
        lambda *_a, **_k: CopyBlock(headline="Hydration explained"),
    )
    monkeypatch.setattr(
        creative_generation.svg_export, "render_creative_svg", lambda **_k: "<svg/>"
    )
    monkeypatch.setattr(creative_generation.svg_export, "rasterize_svg_to_png", fake_rasterize)
    monkeypatch.setattr(creative_generation, "run_live_qa", fake_qa)

    generator, session = await _session()
    try:
        await creative_generation.generate_client_creative_variants(
            session,
            principal=_team_principal(setup.tenant_id),
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="hydration"),
        )
    finally:
        await generator.aclose()

    assert len(qa_calls) == 2


async def test_single_generate_path_unchanged_no_variants(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)

    generator, session = await _session()
    try:
        result = await creative_generation.generate_client_creative(
            session,
            principal=_team_principal(setup.tenant_id),
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="hydration"),
        )
    finally:
        await generator.aclose()

    # One render, natural lever (no override), empty variant set.
    assert len(render_calls) == 1
    assert "nikah_archetype" not in render_calls[0]

    generator, session = await _session()
    try:
        row = await repo.get_creative_doc(
            session, tenant_id=setup.tenant_id, creative_doc_id=result.creative.id
        )
        manifest = CreativeManifest.model_validate(row.manifest)
    finally:
        await generator.aclose()

    assert manifest.variants == []
    assert manifest.variant_selected_id is None
    assert manifest.layer(LayerKind.L5_FINISH) is not None


async def test_format_variants_reuse_copy_source_and_profile_as_audited_siblings(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation(monkeypatch)
    setup = await _create_setup(client)
    principal = _team_principal(setup.tenant_id)

    generator, session = await _session()
    try:
        original = await creative_generation.generate_client_creative(
            session,
            principal=principal,
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="hydration"),
        )
    finally:
        await generator.aclose()

    render_calls: list[dict[str, object]] = []

    async def capture_render(**kwargs: object) -> tuple[Path, Path, None, QAReport]:
        render_calls.append(kwargs)
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text("<svg/>", encoding="utf-8")
        preview_path.write_bytes(b"preview")
        return svg_path, preview_path, None, QAReport(passed=True, failures=[])

    monkeypatch.setattr(
        creative_generation, "_render_creative_artifacts", capture_render
    )

    generator, session = await _session()
    try:
        variants = await creative_generation.generate_format_variants(
            session,
            principal=principal,
            creative_id=original.creative.id,
            format_keys=["ig_story", "fb_post"],
        )
    finally:
        await generator.aclose()

    assert [item.creative.manifest.format_key for item in variants] == [
        "ig_story",
        "fb_post",
    ]
    assert [call["format_key"] for call in render_calls] == ["ig_story", "fb_post"]
    assert all(
        call["copy_block"] == original.creative.manifest.copy_block
        for call in render_calls
    )
    assert len({str(call["image_path"]) for call in render_calls}) == 1

    generator, session = await _session()
    try:
        original_row = await repo.get_creative_doc(
            session,
            tenant_id=setup.tenant_id,
            creative_doc_id=original.creative.id,
        )
        assert original_row is not None
        for generated in variants:
            row = await repo.get_creative_doc(
                session,
                tenant_id=setup.tenant_id,
                creative_doc_id=generated.creative.id,
            )
            assert row is not None
            assert row.job_id == original_row.job_id
            assert row.parent_id == original.creative.id
            assert row.created_by == {"id": "designer-1", "role": "team"}
            manifest = CreativeManifest.model_validate(row.manifest)
            image_layer = manifest.layer(LayerKind.L1_BASE)
            assert image_layer is not None
            assert image_layer.artifact_ref == (
                original.creative.manifest.layer(LayerKind.L1_BASE).artifact_ref
            )
            assert image_layer.recipe.params["derived_from"] == original.creative.id
            assert image_layer.recipe.params["format_variant"] is True
            assert (
                image_layer.recipe.params["style_profile_id"]
                == original.creative.manifest.layer(
                    LayerKind.L1_BASE
                ).recipe.params["style_profile_id"]
            )
    finally:
        await generator.aclose()


async def test_format_variants_are_idor_safe(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)

    generator, session = await _session()
    try:
        original = await creative_generation.generate_client_creative(
            session,
            principal=_team_principal(setup.tenant_id),
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="hydration"),
        )
    finally:
        await generator.aclose()

    renders_before = len(render_calls)
    generator, session = await _session()
    try:
        with pytest.raises(Exception) as exc_info:
            await creative_generation.generate_format_variants(
                session,
                principal=_team_principal("intruder-tenant"),
                creative_id=original.creative.id,
                format_keys=["ig_story"],
            )
        assert getattr(exc_info.value, "status_code", None) == 404
    finally:
        await generator.aclose()

    assert len(render_calls) == renders_before


async def test_three_slide_carousel_is_one_consistent_set_with_distinct_copy(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation(monkeypatch)
    setup = await _create_setup(client)
    principal = _team_principal(setup.tenant_id)

    generator, session = await _session()
    try:
        original = await creative_generation.generate_client_creative(
            session,
            principal=principal,
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="hydration"),
        )
    finally:
        await generator.aclose()

    render_calls: list[dict[str, object]] = []

    async def capture_render(**kwargs: object) -> tuple[Path, Path, None, QAReport]:
        render_calls.append(kwargs)
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text("<svg/>", encoding="utf-8")
        preview_path.write_bytes(b"preview")
        return svg_path, preview_path, None, QAReport(passed=True, failures=[])

    monkeypatch.setattr(
        creative_generation, "_render_creative_artifacts", capture_render
    )
    slide_copy = [
        CopyBlock(headline="Why hydration matters", subhead="Start with the basics"),
        CopyBlock(headline="What dry skin signals", subhead="Notice the early signs"),
        CopyBlock(headline="Build a better routine", cta="Book a consultation"),
    ]

    generator, session = await _session()
    try:
        slides = await creative_generation.generate_carousel_slides(
            session,
            principal=principal,
            creative_id=original.creative.id,
            copy_blocks=slide_copy,
        )
    finally:
        await generator.aclose()

    assert len(slides) == 3
    assert [call["format_key"] for call in render_calls] == ["carousel"] * 3
    assert [call["copy_block"] for call in render_calls] == slide_copy
    assert len({str(call["image_path"]) for call in render_calls}) == 1
    assert len({str(call["profile_id"]) for call in render_calls}) == 1
    assert len({str(call["heading_font_ref"]) for call in render_calls}) == 1
    assert len({str(call["body_font_ref"]) for call in render_calls}) == 1

    manifests = [item.creative.manifest for item in slides]
    image_params = [
        manifest.layer(LayerKind.L1_BASE).recipe.params for manifest in manifests
    ]
    set_ids = {str(params["carousel_set_id"]) for params in image_params}
    assert len(set_ids) == 1
    assert [params["carousel_slide_index"] for params in image_params] == [1, 2, 3]
    assert all(params["carousel_slide_count"] == 3 for params in image_params)
    assert all(
        params["carousel_system"] == image_params[0]["carousel_system"]
        for params in image_params
    )
    assert image_params[0]["carousel_system"]["width"] == 1080
    assert image_params[0]["carousel_system"]["height"] == 1350
    assert [manifest.copy_block for manifest in manifests] == slide_copy
    assert all(manifest.format_key == "carousel" for manifest in manifests)
    assert all(
        Path(manifest.layer(LayerKind.L5_FINISH).recipe.params["svg_ref"]).is_file()
        and Path(
            manifest.layer(LayerKind.L5_FINISH).recipe.params["preview_ref"]
        ).is_file()
        for manifest in manifests
    )


async def test_carousel_freezes_copy_driven_nikah_archetype_across_slides(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation(monkeypatch)
    setup = await _create_setup(
        client,
        tenant_slug="nikah-carousel",
        brand_slug="simply-nikah",
        industry="matrimonial",
    )
    principal = _team_principal(setup.tenant_id)

    generator, session = await _session()
    try:
        original = await creative_generation.generate_client_creative(
            session,
            principal=principal,
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="trust"),
        )
    finally:
        await generator.aclose()

    render_params: list[dict[str, object]] = []

    async def capture_render(**kwargs: object) -> tuple[Path, Path, None, QAReport]:
        render_params.append(dict(kwargs["render_params"]))
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text("<svg/>", encoding="utf-8")
        preview_path.write_bytes(b"preview")
        return svg_path, preview_path, None, QAReport(passed=True, failures=[])

    monkeypatch.setattr(
        creative_generation, "_render_creative_artifacts", capture_render
    )

    generator, session = await _session()
    try:
        await creative_generation.generate_carousel_slides(
            session,
            principal=principal,
            creative_id=original.creative.id,
            copy_blocks=[
                CopyBlock(headline="A gentle path to marriage"),
                CopyBlock(headline="Protect your privacy"),
                CopyBlock(headline="Meet with clear intention"),
            ],
        )
    finally:
        await generator.aclose()

    assert [params["nikah_archetype"] for params in render_params] == [
        "protection_symbol_hero",
        "protection_symbol_hero",
        "protection_symbol_hero",
    ]


async def _list_signals(*, tenant_id: str, client_id: str):
    generator, session = await _session()
    try:
        return await repo.list_preference_signals(
            session, tenant_id=tenant_id, client_id=client_id
        )
    finally:
        await generator.aclose()


async def test_record_variant_pick_marks_and_emits_one_signal(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation(monkeypatch)
    setup = await _create_setup(client)
    principal = _team_principal(setup.tenant_id)

    generator, session = await _session()
    try:
        generated = await creative_generation.generate_client_creative_variants(
            session,
            principal=principal,
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="hydration"),
        )
    finally:
        await generator.aclose()
    set_id = generated.creative.id

    generator, session = await _session()
    try:
        row = await repo.get_creative_doc(
            session, tenant_id=setup.tenant_id, creative_doc_id=set_id
        )
        manifest = CreativeManifest.model_validate(row.manifest)
        chosen = manifest.variants[1]
    finally:
        await generator.aclose()

    generator, session = await _session()
    try:
        picked = await creative_generation.record_variant_pick(
            session,
            principal=principal,
            creative_id=set_id,
            variant_id=chosen.variant_id,
        )
    finally:
        await generator.aclose()

    # A new (audited) version was created; the picked variant is flagged selected on it.
    assert picked.creative.id != set_id
    picked_manifest = picked.creative.manifest
    assert picked_manifest.variant_selected_id == chosen.variant_id
    selected = [v for v in picked_manifest.variants if v.selected]
    assert len(selected) == 1
    assert selected[0].variant_id == chosen.variant_id

    # Exactly ONE preference signal, source=pick, no double-count, carrying the winning lever.
    signals = await _list_signals(tenant_id=setup.tenant_id, client_id=setup.client_id)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.source == "pick"
    assert signal.tenant_id == setup.tenant_id
    assert signal.client_id == setup.client_id
    assert signal.creative_doc_id == picked.creative.id
    assert signal.attributes["variant_lever_key"] == chosen.lever_key
    assert signal.attributes["variant_lever_value"] == chosen.lever_value
    assert signal.actor_role == "team"


async def test_record_variant_pick_is_tenant_scoped(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_generation(monkeypatch)
    setup = await _create_setup(client)

    generator, session = await _session()
    try:
        generated = await creative_generation.generate_client_creative_variants(
            session,
            principal=_team_principal(setup.tenant_id),
            client_id=setup.client_id,
            body=GenerateCreativeRequest(topic="hydration"),
        )
    finally:
        await generator.aclose()

    generator, session = await _session()
    try:
        row = await repo.get_creative_doc(
            session, tenant_id=setup.tenant_id, creative_doc_id=generated.creative.id
        )
        variant_id = CreativeManifest.model_validate(row.manifest).variants[0].variant_id
    finally:
        await generator.aclose()

    # A principal from another tenant cannot pick against this creative (404, no existence leak).
    generator, session = await _session()
    try:
        with pytest.raises(Exception) as exc_info:
            await creative_generation.record_variant_pick(
                session,
                principal=_team_principal("intruder-tenant"),
                creative_id=generated.creative.id,
                variant_id=variant_id,
            )
        assert getattr(exc_info.value, "status_code", None) == 404
    finally:
        await generator.aclose()

    # No stray signal was written for the intruder tenant.
    assert await _list_signals(tenant_id="intruder-tenant", client_id=setup.client_id) == []
