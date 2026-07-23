"""Client portal creative revisions are scoped, bounded, quota-limited, and audited."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient

from api.core.auth import Principal, get_principal
from api.main import app
from api.services import creative_generation
from creative.qa.checks import QAReport


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_tenant(
    client: AsyncClient, *, name: str, slug: str
) -> tuple[str, str]:
    response = await client.post(
        "/tenants",
        json={"name": name, "slug": slug},
        headers=superadmin_headers(),
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["tenant"]["id"], payload["access_token"]


async def _create_creative(
    client: AsyncClient,
    *,
    token: str,
    suffix: str,
) -> tuple[str, str, str]:
    client_response = await client.post(
        "/clients",
        json={"name": f"Client {suffix}"},
        headers=_auth(token),
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
        headers=_auth(token),
    )
    assert brand_response.status_code == 201, brand_response.text

    job_response = await client.post(
        "/jobs",
        json={
            "brand_id": brand_response.json()["id"],
            "title": f"Job {suffix}",
            "format_key": "ig_post",
        },
        headers=_auth(token),
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
        headers=_auth(token),
    )
    assert creative_response.status_code == 201, creative_response.text
    return client_id, job_id, creative_response.json()["id"]


def _stub_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    async def fake_render(**kwargs: object) -> tuple[Path, Path, None, QAReport]:
        calls.append(kwargs)
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text(f"<svg data-render='{len(calls)}'/>", encoding="utf-8")
        preview_path.write_bytes(f"preview-{len(calls)}".encode())
        return svg_path, preview_path, None, QAReport(passed=True, failures=[])

    monkeypatch.setattr(creative_generation, "_render_creative_artifacts", fake_render)
    return calls


def _override_client_principal(*, tenant_id: str, client_id: str) -> None:
    async def client_principal() -> Principal:
        return Principal(
            tenant_id=tenant_id,
            role="client",
            user_id=f"portal-user-{client_id}",
            client_id=client_id,
        )

    app.dependency_overrides[get_principal] = client_principal


async def test_client_can_revise_own_creative_and_audit_is_persisted(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    tenant_id, owner_token = await _create_tenant(client, name="Mimik", slug="mimik")
    client_id, job_id, first_id = await _create_creative(
        client,
        token=owner_token,
        suffix="own",
    )
    _override_client_principal(tenant_id=tenant_id, client_id=client_id)

    try:
        revised = await client.post(
            f"/creatives/{first_id}/revise",
            json={"text_edits": {"headline": "Client revised headline"}},
        )
        history = await client.get(f"/creatives/{first_id}/versions")
    finally:
        app.dependency_overrides.pop(get_principal, None)

    assert revised.status_code == 201, revised.text
    revised_creative = revised.json()["creative"]
    assert revised_creative["job_id"] == job_id
    assert revised_creative["version"] == 2
    assert (
        revised_creative["manifest"]["copy_block"]["headline"]
        == "Client revised headline"
    )
    assert history.status_code == 200, history.text
    versions = history.json()["versions"]
    assert [version["version"] for version in versions] == [1, 2]
    assert versions[1]["creative_id"] == revised_creative["id"]
    assert versions[1]["created_by"] == {
        "id": f"portal-user-{client_id}",
        "role": "client",
        "name": None,
    }
    assert versions[1]["note"] == "headline: Client revised headline"


async def test_client_revision_quota_rejects_next_revision(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    monkeypatch.setattr(
        creative_generation,
        "get_settings",
        lambda: SimpleNamespace(client_revision_daily_quota=2),
        raising=False,
    )
    tenant_id, owner_token = await _create_tenant(client, name="Mimik", slug="mimik")
    client_id, _job_id, creative_id = await _create_creative(
        client,
        token=owner_token,
        suffix="quota",
    )
    _override_client_principal(tenant_id=tenant_id, client_id=client_id)

    try:
        first = await client.post(
            f"/creatives/{creative_id}/revise",
            json={"text_edits": {"headline": "Client revision one"}},
        )
        assert first.status_code == 201, first.text
        second = await client.post(
            f"/creatives/{first.json()['creative']['id']}/revise",
            json={"text_edits": {"headline": "Client revision two"}},
        )
        assert second.status_code == 201, second.text
        limited = await client.post(
            f"/creatives/{second.json()['creative']['id']}/revise",
            json={"text_edits": {"headline": "Client revision three"}},
        )
        history = await client.get(f"/creatives/{creative_id}/versions")
    finally:
        app.dependency_overrides.pop(get_principal, None)

    assert limited.status_code == 429, limited.text
    assert limited.json()["detail"] == "Daily revision limit reached"
    assert limited.headers["X-Revision-Quota-Remaining"] == "0"
    assert history.status_code == 200, history.text
    assert [version["version"] for version in history.json()["versions"]] == [1, 2, 3]


async def test_client_cannot_revise_another_clients_creative(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    tenant_id, owner_token = await _create_tenant(client, name="Mimik", slug="mimik")
    own_client_id, _own_job_id, _own_creative_id = await _create_creative(
        client,
        token=owner_token,
        suffix="own",
    )
    _other_client_id, _other_job_id, other_creative_id = await _create_creative(
        client,
        token=owner_token,
        suffix="other",
    )
    _override_client_principal(tenant_id=tenant_id, client_id=own_client_id)

    try:
        response = await client.post(
            f"/creatives/{other_creative_id}/revise",
            json={"text_edits": {"headline": "Out of scope"}},
        )
    finally:
        app.dependency_overrides.pop(get_principal, None)

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Creative not found"


async def test_unbound_client_principal_cannot_revise_tenant_creative(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    tenant_id, owner_token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_id, _job_id, creative_id = await _create_creative(
        client,
        token=owner_token,
        suffix="unbound",
    )

    async def unbound_client_principal() -> Principal:
        return Principal(tenant_id=tenant_id, role="client", user_id="unbound-portal-user")

    app.dependency_overrides[get_principal] = unbound_client_principal
    try:
        response = await client.post(
            f"/creatives/{creative_id}/revise",
            json={"text_edits": {"headline": "Must stay out of scope"}},
        )
    finally:
        app.dependency_overrides.pop(get_principal, None)

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Creative not found"


@pytest.mark.parametrize(
    "payload",
    [
        {"layer_ops": [{"layer_id": "layer-panel", "dx": 120}]},
        {"params": {"panel_anchor": "right"}},
    ],
    ids=["layer-ops", "render-params"],
)
async def test_client_cannot_manipulate_layers_or_render_params(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    render_calls = _stub_renderer(monkeypatch)
    tenant_id, owner_token = await _create_tenant(client, name="Mimik", slug="mimik")
    client_id, _job_id, creative_id = await _create_creative(
        client,
        token=owner_token,
        suffix="bounded",
    )
    _override_client_principal(tenant_id=tenant_id, client_id=client_id)

    try:
        response = await client.post(
            f"/creatives/{creative_id}/revise",
            json=payload,
        )
        history = await client.get(f"/creatives/{creative_id}/versions")
    finally:
        app.dependency_overrides.pop(get_principal, None)

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == (
        "Clients may only edit text or ask for changes, not manipulate layers"
    )
    assert render_calls == []
    assert history.status_code == 200, history.text
    assert [version["version"] for version in history.json()["versions"]] == [1]


async def test_owner_layer_operations_are_not_client_quota_limited(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    render_calls = _stub_renderer(monkeypatch)
    monkeypatch.setattr(
        creative_generation,
        "get_settings",
        lambda: SimpleNamespace(client_revision_daily_quota=0),
        raising=False,
    )
    _tenant_id, owner_token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_id, _job_id, creative_id = await _create_creative(
        client,
        token=owner_token,
        suffix="owner",
    )

    response = await client.post(
        f"/creatives/{creative_id}/revise",
        json={"layer_ops": [{"layer_id": "layer-panel", "dx": 120}]},
        headers=_auth(owner_token),
    )

    assert response.status_code == 201, response.text
    assert len(render_calls) == 1
    l1_params = response.json()["creative"]["manifest"]["layers"][0]["recipe"]["params"]
    assert l1_params["layer_overrides"]["layer-panel"]["dx"] == 120
