"""Creative document lineage and tenant-scoped version history."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from conftest import superadmin_headers
from httpx import AsyncClient
from mimik_contracts import CopyBlock
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import api.db.models  # noqa: F401  (register tables on Base.metadata)
from api.core.auth import Principal, get_principal
from api.db import repo
from api.db.base import Base
from api.main import app
from api.services import creative_generation


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db_session:
        yield db_session
    await engine.dispose()


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

    async def fake_render(**kwargs: object) -> tuple[Path, Path, None]:
        calls.append(kwargs)
        artifact_dir = kwargs["artifact_dir"]
        assert isinstance(artifact_dir, Path)
        svg_path = artifact_dir / "creative.svg"
        preview_path = artifact_dir / "preview.png"
        svg_path.write_text(f"<svg data-render='{len(calls)}'/>", encoding="utf-8")
        preview_path.write_bytes(f"preview-{len(calls)}".encode())
        return svg_path, preview_path, None

    monkeypatch.setattr(creative_generation, "_render_creative_artifacts", fake_render)
    return calls


async def test_create_creative_doc_builds_and_persists_lineage_chain(
    session: AsyncSession,
) -> None:
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")
    first = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id="job-1",
        manifest={"headline": "First"},
    )
    actor = {"id": "designer-1", "role": "designer", "name": "Nadia"}
    second = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id="job-1",
        manifest={"headline": "Second"},
        parent_id=first.id,
        created_by=actor,
        revision_note="Tighten the headline",
    )
    third = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id="job-1",
        manifest={"headline": "Third"},
        parent_id=second.id,
        created_by={"id": "designer-2", "role": "creative_head"},
        revision_note="Final polish",
    )
    await session.commit()

    stored_second = await repo.get_creative_doc(
        session,
        tenant_id=tenant.id,
        creative_doc_id=second.id,
    )
    stored_third = await repo.get_creative_doc(
        session,
        tenant_id=tenant.id,
        creative_doc_id=third.id,
    )

    assert stored_second is not None
    assert stored_second.version == 2
    assert stored_second.parent_id == first.id
    assert stored_second.created_by == actor
    assert stored_second.revision_note == "Tighten the headline"
    assert stored_third is not None
    assert stored_third.version == 3
    assert stored_third.parent_id == second.id


async def test_list_creative_versions_is_ordered_and_tenant_scoped(
    session: AsyncSession,
) -> None:
    tenant_a = await repo.create_tenant(session, name="Agency A", slug="agency-a")
    tenant_b = await repo.create_tenant(session, name="Agency B", slug="agency-b")

    first = await repo.create_creative_doc(
        session, tenant_id=tenant_a.id, job_id="shared-job", manifest={}
    )
    second = await repo.create_creative_doc(
        session,
        tenant_id=tenant_a.id,
        job_id="shared-job",
        manifest={},
        parent_id=first.id,
    )
    third = await repo.create_creative_doc(
        session,
        tenant_id=tenant_a.id,
        job_id="shared-job",
        manifest={},
        parent_id=second.id,
    )
    await repo.create_creative_doc(
        session, tenant_id=tenant_b.id, job_id="shared-job", manifest={}
    )

    versions = await repo.list_creative_versions(
        session, tenant_id=tenant_a.id, job_id="shared-job"
    )

    assert [row.id for row in versions] == [first.id, second.id, third.id]
    assert [row.version for row in versions] == [1, 2, 3]
    assert all(row.tenant_id == tenant_a.id for row in versions)


async def test_create_creative_doc_rejects_cross_tenant_parent(
    session: AsyncSession,
) -> None:
    tenant_a = await repo.create_tenant(session, name="Agency A", slug="agency-a")
    tenant_b = await repo.create_tenant(session, name="Agency B", slug="agency-b")
    foreign_parent = await repo.create_creative_doc(
        session, tenant_id=tenant_a.id, job_id="job-a", manifest={}
    )

    with pytest.raises(
        ValueError,
        match=r"Parent creative document .* was not found in tenant",
    ):
        await repo.create_creative_doc(
            session,
            tenant_id=tenant_b.id,
            job_id="job-b",
            manifest={},
            parent_id=foreign_parent.id,
        )


async def test_create_creative_doc_without_lineage_keeps_default_version(
    session: AsyncSession,
) -> None:
    tenant = await repo.create_tenant(session, name="Mimik", slug="mimik")

    creative = await repo.create_creative_doc(
        session,
        tenant_id=tenant.id,
        job_id="job-1",
        manifest={"headline": "Original"},
    )

    assert creative.version == 1
    assert creative.parent_id is None
    assert creative.created_by is None
    assert creative.revision_note is None


async def test_revise_persists_parent_actor_note_and_incremented_version(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    monkeypatch.setattr(
        creative_generation.copy_l0,
        "draft_copy",
        lambda *_args, **_kwargs: CopyBlock(headline="AI draft"),
    )
    tenant_id, token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_id, job_id, first_id = await _create_creative(
        client,
        token=token,
        suffix="lineage",
    )

    revised = await client.post(
        f"/creatives/{first_id}/revise",
        json={
            "edits": {"headline": "Revised headline"},
            "instruction": "Tighten the headline",
        },
        headers=_auth(token),
    )

    assert revised.status_code == 201, revised.text
    revised_creative = revised.json()["creative"]
    assert revised_creative["job_id"] == job_id
    assert revised_creative["version"] == 2
    history = await client.get(
        f"/creatives/{first_id}/versions",
        headers=_auth(token),
    )
    assert history.status_code == 200, history.text
    assert history.json()["versions"][1] == {
        "creative_id": revised_creative["id"],
        "version": 2,
        "parent_id": first_id,
        "created_at": history.json()["versions"][1]["created_at"],
        "created_by": {"id": tenant_id, "role": "owner", "name": None},
        "note": "Tighten the headline",
        "preview_url": f"/creatives/{revised_creative['id']}/preview",
        "svg_url": f"/exports/svg?creative_id={revised_creative['id']}",
    }


async def test_versions_are_ordered_tenant_scoped_and_client_scoped(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    tenant_id, token = await _create_tenant(client, name="Agency A", slug="agency-a")
    in_scope_client_id, job_id, first_id = await _create_creative(
        client,
        token=token,
        suffix="in-scope",
    )
    _other_client_id, _other_job_id, out_of_scope_id = await _create_creative(
        client,
        token=token,
        suffix="out-of-scope",
    )
    revised = await client.post(
        f"/creatives/{first_id}/revise",
        json={"edits": {"headline": "Version two"}},
        headers=_auth(token),
    )
    assert revised.status_code == 201, revised.text
    second_id = revised.json()["creative"]["id"]

    history = await client.get(
        f"/creatives/{second_id}/versions",
        headers=_auth(token),
    )
    assert history.status_code == 200, history.text
    payload = history.json()
    assert payload["job_id"] == job_id
    assert [version["creative_id"] for version in payload["versions"]] == [
        first_id,
        second_id,
    ]
    assert [version["version"] for version in payload["versions"]] == [1, 2]
    assert payload["versions"][0]["preview_url"] == f"/creatives/{first_id}/preview"
    assert payload["versions"][1]["svg_url"] == (
        f"/exports/svg?creative_id={second_id}"
    )
    assert payload["versions"][1]["note"] == "headline: Version two"

    _tenant_b_id, token_b = await _create_tenant(
        client,
        name="Agency B",
        slug="agency-b",
    )
    cross_tenant = await client.get(
        f"/creatives/{first_id}/versions",
        headers=_auth(token_b),
    )
    assert cross_tenant.status_code == 404

    async def client_principal() -> Principal:
        return Principal(
            tenant_id=tenant_id,
            role="client",
            client_id=in_scope_client_id,
        )

    app.dependency_overrides[get_principal] = client_principal
    try:
        own_history = await client.get(f"/creatives/{first_id}/versions")
        hidden_history = await client.get(f"/creatives/{out_of_scope_id}/versions")
    finally:
        app.dependency_overrides.pop(get_principal, None)

    assert own_history.status_code == 200, own_history.text
    assert hidden_history.status_code == 404


async def test_revert_creates_new_head_rerenders_and_keeps_existing_versions(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    render_calls = _stub_renderer(monkeypatch)
    _tenant_id, token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_id, job_id, first_id = await _create_creative(
        client,
        token=token,
        suffix="revert",
    )
    revised = await client.post(
        f"/creatives/{first_id}/revise",
        json={"edits": {"headline": "Version two"}},
        headers=_auth(token),
    )
    assert revised.status_code == 201, revised.text
    second_id = revised.json()["creative"]["id"]
    second_preview = Path("var/creatives") / second_id / "preview.png"
    second_preview_before = second_preview.read_bytes()
    render_calls.clear()

    reverted = await client.post(
        f"/creatives/{second_id}/revert",
        json={"to_creative_id": first_id},
        headers=_auth(token),
    )

    assert reverted.status_code == 201, reverted.text
    reverted_creative = reverted.json()["creative"]
    assert reverted_creative["job_id"] == job_id
    assert reverted_creative["version"] == 3
    assert reverted_creative["manifest"]["copy_block"]["headline"] == "Original revert"
    assert len(render_calls) == 1
    assert render_calls[0]["image_path"] == Path("source.png")
    new_preview = Path("var/creatives") / reverted_creative["id"] / "preview.png"
    assert new_preview.is_file()
    assert second_preview.read_bytes() == second_preview_before

    history = await client.get(
        f"/creatives/{reverted_creative['id']}/versions",
        headers=_auth(token),
    )
    assert history.status_code == 200, history.text
    versions = history.json()["versions"]
    assert [version["creative_id"] for version in versions] == [
        first_id,
        second_id,
        reverted_creative["id"],
    ]
    assert versions[-1]["parent_id"] == second_id
    assert versions[-1]["note"] == "revert to v1"


async def test_revert_rejects_target_from_different_job(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    render_calls = _stub_renderer(monkeypatch)
    _tenant_id, token = await _create_tenant(client, name="Mimik", slug="mimik")
    _client_a, _job_a, creative_a = await _create_creative(
        client,
        token=token,
        suffix="job-a",
    )
    _client_b, _job_b, creative_b = await _create_creative(
        client,
        token=token,
        suffix="job-b",
    )

    response = await client.post(
        f"/creatives/{creative_a}/revert",
        json={"to_creative_id": creative_b},
        headers=_auth(token),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Creative versions must belong to the same job"
    assert render_calls == []


async def test_revert_rejects_out_of_scope_id_as_unprocessable(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("source.png").write_bytes(b"source")
    _stub_renderer(monkeypatch)
    _tenant_a_id, token_a = await _create_tenant(client, name="Agency A", slug="agency-a")
    _client_a, _job_a, creative_a = await _create_creative(
        client,
        token=token_a,
        suffix="tenant-a",
    )
    _tenant_b_id, token_b = await _create_tenant(client, name="Agency B", slug="agency-b")
    _client_b, _job_b, creative_b = await _create_creative(
        client,
        token=token_b,
        suffix="tenant-b",
    )

    # Body param `to_creative_id` out of scope → 422 (request-body validation).
    response = await client.post(
        f"/creatives/{creative_a}/revert",
        json={"to_creative_id": creative_b},
        headers=_auth(token_a),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "to_creative_id must exist within the caller's tenant and scope"
    )

    # URL-path resource out of scope → 404 (IDOR convention, never leak existence):
    # tenant A reverting tenant B's creative in the path.
    cross = await client.post(
        f"/creatives/{creative_b}/revert",
        json={"to_creative_id": creative_a},
        headers=_auth(token_a),
    )
    assert cross.status_code == 404
