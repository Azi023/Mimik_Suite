"""M-06 learning loop closed: generation CONSULTS the per-client preference profile.

The ranker already existed (tests/test_preferences_ranker.py) but no generation code consulted it
— the "Ranker is steering picks" claim was a lie. These exercise the wiring in
creative_generation.generate_client_creative:

- With enough PICK signals favouring one lever, the A/B variant set is ORDERED so that lever is
  variant 0 (shown first / promoted as the active creative), AND the single-generate default lever
  is biased toward it.
- Cold start (no signals, or below the ranker threshold) → the deterministic _plan_variants order
  is preserved (no bias from nothing).
- Cross-client isolation: client B's signals never influence client A's ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient
from mimik_contracts import RANKER_MIN_SIGNALS, CopyBlock

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


def _team_principal(tenant_id: str) -> Principal:
    return Principal(tenant_id=tenant_id, role="team", user_id="designer-1", client_id=None)


async def _make_client(
    client: AsyncClient, *, owner_token: str, brand_slug: str
) -> str:
    client_id = (
        await client.post(
            "/clients", json={"name": f"Client {brand_slug}"}, headers=_auth(owner_token)
        )
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
    return client_id


async def _create_setup(client: AsyncClient, *, brand_slug: str = "acme-generic") -> _Setup:
    tenant = (
        await client.post(
            "/tenants",
            json={"name": "Mimik", "slug": "mimik"},
            headers=superadmin_headers(),
        )
    ).json()
    owner_token = tenant["access_token"]
    tenant_id = tenant["tenant"]["id"]
    client_id = await _make_client(client, owner_token=owner_token, brand_slug=brand_slug)
    return _Setup(tenant_id=tenant_id, owner_token=owner_token, client_id=client_id)


def _stub_generation(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Same stub seam as test_creative_variants: record the render_params each variant receives so
    tests can assert which lever landed first, without any paid backend or real render."""
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
        creative_generation.art_direction,
        "build_image_request",
        lambda *_a, **_k: _FakeRequest(),
    )
    monkeypatch.setattr(
        creative_generation.copy_l0,
        "draft_copy",
        lambda *_a, **_k: CopyBlock(headline="Hydration explained"),
    )
    monkeypatch.setattr(creative_generation, "_render_creative_artifacts", fake_render)
    return render_calls


async def _seed_pick_signals(
    *, tenant_id: str, client_id: str, lever_value: str, count: int
) -> None:
    """Append `count` PICK signals favouring a text_alignment lever, exactly as record_variant_pick
    would emit them (same attribute keys), so the ranker scores that lever positively."""
    generator, session = await _session()
    try:
        for _ in range(count):
            await repo.create_preference_signal(
                session,
                tenant_id=tenant_id,
                client_id=client_id,
                source="pick",
                attributes={
                    "variant_lever_key": "text_alignment",
                    "variant_lever_value": lever_value,
                },
                actor_role="team",
            )
        await session.commit()
    finally:
        await generator.aclose()


async def _generate(setup_tenant: str, client_id: str, *, variants: int) -> None:
    generator, session = await _session()
    try:
        await creative_generation.generate_client_creative(
            session,
            principal=_team_principal(setup_tenant),
            client_id=client_id,
            body=GenerateCreativeRequest(topic="hydration", pillar="Education"),
            variants=variants,
        )
    finally:
        await generator.aclose()


async def test_preferred_lever_ordered_first_in_variant_set(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Seeded picks favour `center`; the deterministic default is `left` first. After consulting
    the profile the set is reordered so `center` is variant 0 (render_calls[0])."""
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)
    await _seed_pick_signals(
        tenant_id=setup.tenant_id,
        client_id=setup.client_id,
        lever_value="center",
        count=RANKER_MIN_SIGNALS,
    )

    await _generate(setup.tenant_id, setup.client_id, variants=2)

    assert len(render_calls) == 2
    # Ranker steered: `center` is now shown first, flipping the deterministic left/center order.
    assert render_calls[0]["text_alignment"] == "center"
    assert render_calls[1]["text_alignment"] == "left"


async def test_cold_start_keeps_deterministic_variant_order(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No signals → ranker is a passthrough → the deterministic _plan_variants order stands."""
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)

    await _generate(setup.tenant_id, setup.client_id, variants=2)

    assert len(render_calls) == 2
    assert render_calls[0]["text_alignment"] == "left"
    assert render_calls[1]["text_alignment"] == "center"


async def test_below_threshold_signal_count_does_not_steer(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A thin history (below RANKER_MIN_SIGNALS) must not re-order — no acting on weak signal."""
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)
    await _seed_pick_signals(
        tenant_id=setup.tenant_id,
        client_id=setup.client_id,
        lever_value="center",
        count=RANKER_MIN_SIGNALS - 1,
    )

    await _generate(setup.tenant_id, setup.client_id, variants=2)

    assert render_calls[0]["text_alignment"] == "left"


async def test_default_single_generate_lever_biased_by_preference(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Single-generate (variants=1) with strong signal for `center` biases the default lever from
    the natural `left` to `center`."""
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)
    await _seed_pick_signals(
        tenant_id=setup.tenant_id,
        client_id=setup.client_id,
        lever_value="center",
        count=RANKER_MIN_SIGNALS,
    )

    await _generate(setup.tenant_id, setup.client_id, variants=1)

    assert len(render_calls) == 1
    assert render_calls[0]["text_alignment"] == "center"


async def test_default_single_generate_lever_unchanged_cold_start(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No signal → single-generate default lever is untouched (renderer's natural `left`)."""
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)

    await _generate(setup.tenant_id, setup.client_id, variants=1)

    assert len(render_calls) == 1
    # No text_alignment injected: the renderer's own default (`left`) applies downstream.
    assert render_calls[0].get("text_alignment") is None


async def test_cross_client_signals_do_not_leak(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Client B accumulates strong `center` preference; generating for client A (no signals of its
    own) must stay on the deterministic order — B never steers A."""
    monkeypatch.chdir(tmp_path)
    render_calls = _stub_generation(monkeypatch)
    setup = await _create_setup(client)
    client_b = await _make_client(
        client, owner_token=setup.owner_token, brand_slug="beta-generic"
    )
    await _seed_pick_signals(
        tenant_id=setup.tenant_id,
        client_id=client_b,
        lever_value="center",
        count=RANKER_MIN_SIGNALS * 2,
    )

    # Generate for client A (no signals of its own).
    await _generate(setup.tenant_id, setup.client_id, variants=2)

    assert render_calls[0]["text_alignment"] == "left"
    assert render_calls[1]["text_alignment"] == "center"
