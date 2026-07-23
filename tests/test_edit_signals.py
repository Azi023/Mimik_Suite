"""B-13 learning signals for creative edits, reverts, and approvals."""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient
from mimik_contracts import CopyBlock, CreativeManifest, LayerKind

from api.core.auth import Principal, get_principal
from api.core.security import create_access_token
from api.db import repo
from api.db.session import get_session
from api.main import app
from api.services import approval_flow, creative_generation
from creative.knowledge import feedback
from creative.qa.checks import QAReport


@dataclass(frozen=True)
class CreativeSetup:
    tenant_id: str
    owner_token: str
    team_token: str
    client_id: str
    job_id: str
    creative_id: str


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_setup(
    client: AsyncClient,
    *,
    tenant_name: str = "Mimik",
    tenant_slug: str = "mimik",
    suffix: str = "signal",
) -> CreativeSetup:
    tenant_response = await client.post(
        "/tenants",
        json={"name": tenant_name, "slug": tenant_slug},
        headers=superadmin_headers(),
    )
    assert tenant_response.status_code == 201, tenant_response.text
    tenant_payload = tenant_response.json()
    tenant_id = tenant_payload["tenant"]["id"]
    owner_token = tenant_payload["access_token"]

    client_response = await client.post(
        "/clients",
        json={"name": f"Client {suffix}"},
        headers=_auth(owner_token),
    )
    assert client_response.status_code == 201, client_response.text
    client_id = client_response.json()["id"]

    brand_response = await client.post(
        "/brands",
        json={
            "client_id": client_id,
            "name": f"Brand {suffix}",
            "slug": f"brand-{suffix}",
            "tokens": {
                "colors": [
                    {"name": "primary", "hex": "#112233"},
                    {"name": "ground", "hex": "#FFFFFF"},
                ]
            },
        },
        headers=_auth(owner_token),
    )
    assert brand_response.status_code == 201, brand_response.text

    job_response = await client.post(
        "/jobs",
        json={
            "brand_id": brand_response.json()["id"],
            "title": f"Job {suffix}",
            "format_key": "ig_post",
        },
        headers=_auth(owner_token),
    )
    assert job_response.status_code == 201, job_response.text
    job_id = job_response.json()["id"]

    creative_response = await client.post(
        f"/jobs/{job_id}/creatives",
        json={
            "template_key": "centered_hero",
            "copy_block": {
                "headline": f"Original {suffix}",
                "subhead": "Original subhead",
                "cta": "Original CTA",
            },
            "image_artifact": "source.png",
        },
        headers=_auth(owner_token),
    )
    assert creative_response.status_code == 201, creative_response.text

    return CreativeSetup(
        tenant_id=tenant_id,
        owner_token=owner_token,
        team_token=create_access_token(tenant_id=tenant_id, role="team"),
        client_id=client_id,
        job_id=job_id,
        creative_id=creative_response.json()["id"],
    )


def _stub_revision_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    Path("source.png").write_bytes(b"source")
    monkeypatch.delenv("REVISE_LLM", raising=False)

    async def fake_render(**kwargs: object) -> tuple[Path, Path, None, QAReport]:
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text("<svg/>", encoding="utf-8")
        preview_path.write_bytes(b"preview")
        return svg_path, preview_path, None, QAReport(passed=True, failures=[])

    monkeypatch.setattr(
        creative_generation,
        "_render_creative_artifacts",
        fake_render,
    )
    monkeypatch.setattr(
        creative_generation.copy_l0,
        "draft_copy",
        lambda *_args, **_kwargs: CopyBlock(headline="AI redraft"),
    )


def _stub_approval_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_render(_session, _tenant_id, _doc) -> bytes:
        return b"\x89PNG\r\n\x1a\nFAKE"

    monkeypatch.setattr(approval_flow, "default_render", fake_render)
    monkeypatch.setenv("ARCHIVE_BACKEND", "local")
    monkeypatch.setenv("ARCHIVE_LOCAL_ROOT", str(tmp_path / "_archive"))


@pytest.fixture
def isolated_rules_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    seed_path = Path(feedback.__file__).with_name("design_rules.json")
    rules_path = tmp_path / "design_rules.json"
    rules_path.write_bytes(seed_path.read_bytes())
    monkeypatch.setattr(feedback, "RULES_PATH", rules_path)
    return rules_path


async def _seed_l1_params(
    *,
    tenant_id: str,
    creative_id: str,
    params: dict[str, object],
) -> None:
    session_generator = app.dependency_overrides[get_session]()
    session = await session_generator.__anext__()
    try:
        row = await repo.get_creative_doc(
            session,
            tenant_id=tenant_id,
            creative_doc_id=creative_id,
        )
        assert row is not None
        manifest = CreativeManifest.model_validate(row.manifest)
        image_layer = manifest.layer(LayerKind.L1_BASE)
        assert image_layer is not None
        image_layer.recipe.params.update(params)
        row.manifest = manifest.model_dump(mode="json")
        await session.commit()
    finally:
        await session_generator.aclose()


async def _list_signals(*, tenant_id: str, client_id: str):
    session_generator = app.dependency_overrides[get_session]()
    session = await session_generator.__anext__()
    try:
        return await repo.list_preference_signals(
            session,
            tenant_id=tenant_id,
            client_id=client_id,
        )
    finally:
        await session_generator.aclose()


def _override_client_principal(*, tenant_id: str, client_id: str) -> None:
    async def client_principal() -> Principal:
        return Principal(
            tenant_id=tenant_id,
            role="client",
            user_id=f"portal-user-{client_id}",
            client_id=client_id,
        )

    app.dependency_overrides[get_principal] = client_principal


def test_feedback_wrapper_is_bounded_and_exception_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_spec = importlib.util.find_spec("api.services.edit_signals")
    assert module_spec is not None
    edit_signals = importlib.import_module("api.services.edit_signals")
    calls: list[dict[str, object]] = []

    def capture_feedback(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(edit_signals, "record_feedback", capture_feedback)
    edit_signals.feedback_from_edit(
        verdict="accept",
        reason="   ",
        profile_id="glo2go-aesthetics",
    )
    assert calls == []

    edit_signals.feedback_from_edit(
        verdict="accept",
        reason="x" * 250,
        profile_id="glo2go-aesthetics",
    )
    assert calls == [
        {
            "verdict": "accept",
            "reason": "x" * 200,
            "profile_id": "glo2go-aesthetics",
        }
    ]

    def fail_feedback(**_kwargs: object) -> None:
        raise OSError("rules store unavailable")

    monkeypatch.setattr(edit_signals, "record_feedback", fail_feedback)
    edit_signals.feedback_from_edit(
        verdict="decline",
        reason="Keep the request path alive",
        profile_id=None,
    )


async def test_signal_failure_does_not_lose_committed_revision(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_revision_dependencies(monkeypatch)
    setup = await _create_setup(client, suffix="signal-failure")

    async def fail_signal(*_args: object, **_kwargs: object) -> None:
        raise OSError("preference store unavailable")

    monkeypatch.setattr(creative_generation, "record_signal", fail_signal)
    revised = await client.post(
        f"/creatives/{setup.creative_id}/revise",
        json={"text_edits": {"headline": "Version survives"}},
        headers=_auth(setup.team_token),
    )
    assert revised.status_code == 201, revised.text

    versions = await client.get(
        f"/creatives/{setup.creative_id}/versions",
        headers=_auth(setup.team_token),
    )
    assert versions.status_code == 200, versions.text
    assert [item["version"] for item in versions.json()["versions"]] == [1, 2]
    assert versions.json()["versions"][1]["creative_id"] == revised.json()["creative"]["id"]

    signals = await _list_signals(
        tenant_id=setup.tenant_id,
        client_id=setup.client_id,
    )
    assert signals == []


async def test_team_revise_records_client_scoped_edit_signal(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_revision_dependencies(monkeypatch)
    setup = await _create_setup(client)
    await _seed_l1_params(
        tenant_id=setup.tenant_id,
        creative_id=setup.creative_id,
        params={"style_profile_id": "glo2go-aesthetics"},
    )

    revised = await client.post(
        f"/creatives/{setup.creative_id}/revise",
        json={"text_edits": {"headline": "Team revised headline"}},
        headers=_auth(setup.team_token),
    )
    assert revised.status_code == 201, revised.text

    signals = await _list_signals(
        tenant_id=setup.tenant_id,
        client_id=setup.client_id,
    )
    assert len(signals) == 1
    signal = signals[0]
    assert signal.source == "edit"
    assert signal.tenant_id == setup.tenant_id
    assert signal.client_id == setup.client_id
    assert signal.job_id == setup.job_id
    assert signal.creative_doc_id == revised.json()["creative"]["id"]
    assert signal.actor_role == "team"
    assert signal.attributes["profile_id"] == "glo2go-aesthetics"
    assert signal.attributes["edited_by_client"] == "false"

    profile = await client.get(
        f"/clients/{setup.client_id}/preferences/profile",
        headers=_auth(setup.team_token),
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["signal_count"] == 1


async def test_ask_revise_stamps_current_ask_and_records_zone(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_revision_dependencies(monkeypatch)
    setup = await _create_setup(client, suffix="ask")
    await _seed_l1_params(
        tenant_id=setup.tenant_id,
        creative_id=setup.creative_id,
        params={"style_profile_id": "simply-nikah"},
    )
    instruction = "Move the headline left and keep the composition calm. " + ("x" * 220)

    asked = await client.post(
        f"/creatives/{setup.creative_id}/revise",
        json={"ask": {"zone": "headline", "instruction": instruction}},
        headers=_auth(setup.team_token),
    )
    assert asked.status_code == 201, asked.text
    asked_creative = asked.json()["creative"]
    asked_params = asked_creative["manifest"]["layers"][0]["recipe"]["params"]
    assert asked_params["last_ask"] == instruction[:200]

    signals = await _list_signals(
        tenant_id=setup.tenant_id,
        client_id=setup.client_id,
    )
    assert len(signals) == 1
    assert signals[0].source == "edit"
    assert signals[0].attributes["profile_id"] == "simply-nikah"
    assert signals[0].attributes["revision_zone"] == "headline"

    text_revision = await client.post(
        f"/creatives/{asked_creative['id']}/revise",
        json={"text_edits": {"headline": "Human follow-up"}},
        headers=_auth(setup.team_token),
    )
    assert text_revision.status_code == 201, text_revision.text
    current_params = text_revision.json()["creative"]["manifest"]["layers"][0]["recipe"]["params"]
    assert "last_ask" not in current_params


async def test_revert_records_rejection_for_version_being_left(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_revision_dependencies(monkeypatch)
    setup = await _create_setup(client, suffix="revert")
    await _seed_l1_params(
        tenant_id=setup.tenant_id,
        creative_id=setup.creative_id,
        params={"style_profile_id": "island-cart"},
    )

    revised = await client.post(
        f"/creatives/{setup.creative_id}/revise",
        json={"text_edits": {"headline": "Version two"}},
        headers=_auth(setup.team_token),
    )
    assert revised.status_code == 201, revised.text
    revised_id = revised.json()["creative"]["id"]

    reverted = await client.post(
        f"/creatives/{revised_id}/revert",
        json={"to_creative_id": setup.creative_id},
        headers=_auth(setup.team_token),
    )
    assert reverted.status_code == 201, reverted.text

    signals = await _list_signals(
        tenant_id=setup.tenant_id,
        client_id=setup.client_id,
    )
    rejection = next(signal for signal in signals if signal.source == "rejection")
    assert rejection.tenant_id == setup.tenant_id
    assert rejection.client_id == setup.client_id
    assert rejection.job_id == setup.job_id
    assert rejection.creative_doc_id == reverted.json()["creative"]["id"]
    assert rejection.attributes["reverted_from_version"] == "2"


async def test_approving_ask_result_records_accept_rule(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_rules_store: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_revision_dependencies(monkeypatch)
    _stub_approval_dependencies(monkeypatch, tmp_path)
    setup = await _create_setup(client, suffix="accept")
    await _seed_l1_params(
        tenant_id=setup.tenant_id,
        creative_id=setup.creative_id,
        params={"style_profile_id": "glo2go-aesthetics"},
    )
    instruction = "Keep the subject larger and the headline readable"

    asked = await client.post(
        f"/creatives/{setup.creative_id}/revise",
        json={"ask": {"zone": "layout", "instruction": instruction}},
        headers=_auth(setup.team_token),
    )
    assert asked.status_code == 201, asked.text
    asked_id = asked.json()["creative"]["id"]

    approved = await client.post(
        "/approvals",
        json={
            "job_id": setup.job_id,
            "creative_doc_id": asked_id,
            "action": "approve",
        },
        headers=_auth(setup.owner_token),
    )
    assert approved.status_code == 200, approved.text

    learned = next(rule for rule in feedback.load_rules() if rule.rule == instruction)
    assert learned.applies_to == ["glo2go-aesthetics"]
    assert "accepted" in learned.why

    signals = await _list_signals(
        tenant_id=setup.tenant_id,
        client_id=setup.client_id,
    )
    approval = next(signal for signal in signals if signal.source == "approval")
    assert approval.attributes["edited_by_client"] == "false"


async def test_reverting_ask_result_records_decline_rule(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolated_rules_store: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_revision_dependencies(monkeypatch)
    setup = await _create_setup(client, suffix="decline")
    await _seed_l1_params(
        tenant_id=setup.tenant_id,
        creative_id=setup.creative_id,
        params={"style_profile_id": "simply-nikah"},
    )
    instruction = "Move the panel right and make the subject larger"

    asked = await client.post(
        f"/creatives/{setup.creative_id}/revise",
        json={"ask": {"zone": "layout", "instruction": instruction}},
        headers=_auth(setup.team_token),
    )
    assert asked.status_code == 201, asked.text
    asked_id = asked.json()["creative"]["id"]

    reverted = await client.post(
        f"/creatives/{asked_id}/revert",
        json={"to_creative_id": setup.creative_id},
        headers=_auth(setup.team_token),
    )
    assert reverted.status_code == 201, reverted.text

    learned = next(rule for rule in feedback.load_rules() if rule.rule == instruction)
    assert learned.applies_to == ["simply-nikah"]
    assert "declined" in learned.why


async def test_client_edit_and_approval_signals_never_cross_client_or_tenant(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _stub_revision_dependencies(monkeypatch)
    _stub_approval_dependencies(monkeypatch, tmp_path)
    setup_a = await _create_setup(client, suffix="client-a")
    setup_b = await _create_setup(
        client,
        tenant_name="Other tenant",
        tenant_slug="other-tenant",
        suffix="client-b",
    )
    await _seed_l1_params(
        tenant_id=setup_a.tenant_id,
        creative_id=setup_a.creative_id,
        params={"style_profile_id": "glo2go-aesthetics"},
    )
    _override_client_principal(
        tenant_id=setup_a.tenant_id,
        client_id=setup_a.client_id,
    )
    try:
        revised = await client.post(
            f"/creatives/{setup_a.creative_id}/revise",
            json={"text_edits": {"headline": "Client-authored edit"}},
        )
    finally:
        app.dependency_overrides.pop(get_principal, None)
    assert revised.status_code == 201, revised.text
    revised_id = revised.json()["creative"]["id"]

    approved = await client.post(
        "/approvals",
        json={
            "job_id": setup_a.job_id,
            "creative_doc_id": revised_id,
            "action": "approve",
        },
        headers=_auth(setup_a.owner_token),
    )
    assert approved.status_code == 200, approved.text

    signals_a = await _list_signals(
        tenant_id=setup_a.tenant_id,
        client_id=setup_a.client_id,
    )
    assert {signal.source for signal in signals_a} == {"edit", "approval"}
    assert all(signal.tenant_id == setup_a.tenant_id for signal in signals_a)
    assert all(signal.client_id == setup_a.client_id for signal in signals_a)
    assert all(signal.job_id == setup_a.job_id for signal in signals_a)
    edit_signal = next(signal for signal in signals_a if signal.source == "edit")
    approval_signal = next(signal for signal in signals_a if signal.source == "approval")
    assert edit_signal.actor_role == "client"
    assert edit_signal.attributes["edited_by_client"] == "true"
    assert approval_signal.attributes["edited_by_client"] == "true"

    signals_b = await _list_signals(
        tenant_id=setup_b.tenant_id,
        client_id=setup_b.client_id,
    )
    assert signals_b == []
