"""Soft-delete CRUD for the operator's six core entities.

Each delete must preserve the row, hide it from ordinary reads, and return 404 when repeated.
The three new PATCH surfaces must persist only the explicitly supplied editable fields.
"""

from __future__ import annotations

from typing import TypedDict

import pytest
import pytest_asyncio
from conftest import superadmin_headers
from httpx import AsyncClient
from sqlalchemy import select

from api.core import config
from api.core.security import create_access_token, decode_access_token
from api.db.models import ClientRow
from api.db.session import get_session
from api.main import app

_PNG = b"\x89PNG\r\n\x1a\n fake-bytes"


class EntitySet(TypedDict):
    token: str
    client_id: str
    brand_id: str
    brief_id: str
    job_id: str
    creative_id: str
    task_id: str
    asset_id: str


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def assets_root(tmp_path, monkeypatch: pytest.MonkeyPatch):
    settings = config.Settings(assets_local_root=str(tmp_path / "assets"))
    monkeypatch.setattr(config, "_settings", settings)
    return tmp_path / "assets"


@pytest_asyncio.fixture
async def entities(client: AsyncClient, assets_root) -> EntitySet:
    tenant = await client.post(
        "/tenants",
        json={"name": "Mimik", "slug": "mimik"},
        headers=superadmin_headers(),
    )
    assert tenant.status_code == 201, tenant.text
    token = tenant.json()["access_token"]
    headers = _auth(token)

    client_response = await client.post(
        "/clients", json={"name": "Glo2Go"}, headers=headers
    )
    assert client_response.status_code == 201, client_response.text
    client_id = client_response.json()["id"]

    brand_response = await client.post(
        "/brands",
        json={"client_id": client_id, "name": "Glo2Go", "slug": "glo2go"},
        headers=headers,
    )
    assert brand_response.status_code == 201, brand_response.text
    brand_id = brand_response.json()["id"]

    brief_response = await client.post(
        "/briefs", json={"brand_id": brand_id}, headers=headers
    )
    assert brief_response.status_code == 201, brief_response.text
    brief_id = brief_response.json()["id"]

    job_response = await client.post(
        "/jobs",
        json={"brand_id": brand_id, "title": "Launch", "format_key": "ig_post"},
        headers=headers,
    )
    assert job_response.status_code == 201, job_response.text
    job_id = job_response.json()["id"]

    creative_response = await client.post(
        f"/jobs/{job_id}/creatives",
        json={
            "template_key": "centered_hero",
            "copy_block": {"headline": "Glow naturally", "cta": "Book now"},
        },
        headers=headers,
    )
    assert creative_response.status_code == 201, creative_response.text
    creative_id = creative_response.json()["id"]

    task_response = await client.post(
        "/tasks",
        json={
            "client_id": client_id,
            "type": "editor_assignment",
            "title": "Assign launch creative",
        },
        headers=headers,
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["id"]

    asset_response = await client.post(
        f"/brands/{brand_id}/assets",
        files={"file": ("logo.png", _PNG, "image/png")},
        data={"kind": "logo", "notes": "Primary mark"},
        headers=headers,
    )
    assert asset_response.status_code == 201, asset_response.text
    asset_id = asset_response.json()["id"]

    return {
        "token": token,
        "client_id": client_id,
        "brand_id": brand_id,
        "brief_id": brief_id,
        "job_id": job_id,
        "creative_id": creative_id,
        "task_id": task_id,
        "asset_id": asset_id,
    }


async def _delete_twice(
    client: AsyncClient, *, path: str, token: str
) -> None:
    first = await client.delete(path, headers=_auth(token))
    assert first.status_code == 204, first.text
    assert first.content == b""
    repeated = await client.delete(path, headers=_auth(token))
    assert repeated.status_code == 404


async def test_soft_delete_client_hides_list_and_get(
    client: AsyncClient, entities: EntitySet
) -> None:
    await _delete_twice(
        client, path=f"/clients/{entities['client_id']}", token=entities["token"]
    )
    assert (
        await client.get(
            f"/clients/{entities['client_id']}", headers=_auth(entities["token"])
        )
    ).status_code == 404
    listed = await client.get("/clients", headers=_auth(entities["token"]))
    assert entities["client_id"] not in {row["id"] for row in listed.json()}


async def test_soft_deleted_client_email_can_be_reused(client: AsyncClient) -> None:
    tenant = await client.post(
        "/tenants",
        json={"name": "Mimik", "slug": "mimik"},
        headers=superadmin_headers(),
    )
    token = tenant.json()["access_token"]
    headers = _auth(token)
    first = await client.post(
        "/clients",
        json={"name": "Former client", "contact_email": "hello@example.com"},
        headers=headers,
    )
    assert first.status_code == 201, first.text
    assert (
        await client.delete(f"/clients/{first.json()['id']}", headers=headers)
    ).status_code == 204

    replacement = await client.post(
        "/clients",
        json={"name": "New client", "contact_email": "hello@example.com"},
        headers=headers,
    )
    assert replacement.status_code == 201, replacement.text


async def test_soft_delete_records_actor_and_timestamp(client: AsyncClient) -> None:
    tenant = await client.post(
        "/tenants",
        json={"name": "Mimik", "slug": "mimik"},
        headers=superadmin_headers(),
    )
    token = tenant.json()["access_token"]
    created = await client.post(
        "/clients", json={"name": "Audited client"}, headers=_auth(token)
    )
    client_id = created.json()["id"]
    assert (
        await client.delete(f"/clients/{client_id}", headers=_auth(token))
    ).status_code == 204

    session_gen = app.dependency_overrides[get_session]()
    session = await session_gen.__anext__()
    try:
        row = (
            await session.execute(select(ClientRow).where(ClientRow.id == client_id))
        ).scalar_one()
        assert row.deleted_at is not None
        assert row.deleted_by == {
            "id": tenant.json()["tenant"]["id"],
            "role": "owner",
        }
    finally:
        await session_gen.aclose()


async def test_soft_delete_requires_owner_or_admin(
    client: AsyncClient, entities: EntitySet
) -> None:
    tenant_id = str(decode_access_token(entities["token"])["sub"])
    designer_token = create_access_token(tenant_id=tenant_id, role="designer")
    paths = (
        f"/clients/{entities['client_id']}",
        f"/brands/{entities['brand_id']}",
        f"/briefs/{entities['brief_id']}",
        f"/creatives/{entities['creative_id']}",
        f"/tasks/{entities['task_id']}",
        f"/assets/{entities['asset_id']}",
    )
    for path in paths:
        response = await client.delete(path, headers=_auth(designer_token))
        assert response.status_code == 403, f"designer deleted {path}: {response.text}"


async def test_soft_delete_brand_hides_get(
    client: AsyncClient, entities: EntitySet
) -> None:
    await _delete_twice(
        client, path=f"/brands/{entities['brand_id']}", token=entities["token"]
    )
    assert (
        await client.get(
            f"/brands/{entities['brand_id']}", headers=_auth(entities["token"])
        )
    ).status_code == 404


async def test_soft_delete_brief_hides_list_and_get(
    client: AsyncClient, entities: EntitySet
) -> None:
    await _delete_twice(
        client, path=f"/briefs/{entities['brief_id']}", token=entities["token"]
    )
    assert (
        await client.get(
            f"/briefs/{entities['brief_id']}", headers=_auth(entities["token"])
        )
    ).status_code == 404
    listed = await client.get("/briefs", headers=_auth(entities["token"]))
    assert entities["brief_id"] not in {row["id"] for row in listed.json()}


async def test_soft_delete_creative_hides_list(
    client: AsyncClient, entities: EntitySet
) -> None:
    await _delete_twice(
        client,
        path=f"/creatives/{entities['creative_id']}",
        token=entities["token"],
    )
    listed = await client.get(
        f"/jobs/{entities['job_id']}/creatives",
        headers=_auth(entities["token"]),
    )
    assert entities["creative_id"] not in {row["id"] for row in listed.json()}
    assert (
        await client.get(
            f"/creatives/{entities['creative_id']}/versions",
            headers=_auth(entities["token"]),
        )
    ).status_code == 404


async def test_soft_delete_task_hides_list_and_get(
    client: AsyncClient, entities: EntitySet
) -> None:
    await _delete_twice(
        client, path=f"/tasks/{entities['task_id']}", token=entities["token"]
    )
    assert (
        await client.get(
            f"/tasks/{entities['task_id']}", headers=_auth(entities["token"])
        )
    ).status_code == 404
    listed = await client.get("/tasks", headers=_auth(entities["token"]))
    assert entities["task_id"] not in {row["id"] for row in listed.json()}


async def test_soft_delete_asset_hides_list_and_raw(
    client: AsyncClient, entities: EntitySet
) -> None:
    await _delete_twice(
        client, path=f"/assets/{entities['asset_id']}", token=entities["token"]
    )
    listed = await client.get(
        f"/brands/{entities['brand_id']}/assets",
        headers=_auth(entities["token"]),
    )
    assert entities["asset_id"] not in {row["id"] for row in listed.json()}
    assert (
        await client.get(
            f"/assets/{entities['asset_id']}/raw",
            headers=_auth(entities["token"]),
        )
    ).status_code == 404


async def test_patch_asset_metadata_persists(
    client: AsyncClient, entities: EntitySet
) -> None:
    patched = await client.patch(
        f"/assets/{entities['asset_id']}",
        json={
            "filename": "primary-logo.png",
            "license": "Client-owned",
            "notes": "Use on light backgrounds",
        },
        headers=_auth(entities["token"]),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["filename"] == "primary-logo.png"
    assert patched.json()["license"] == "Client-owned"
    assert patched.json()["notes"] == "Use on light backgrounds"
    listed = await client.get(
        f"/brands/{entities['brand_id']}/assets",
        headers=_auth(entities["token"]),
    )
    stored = next(row for row in listed.json() if row["id"] == entities["asset_id"])
    assert stored["notes"] == "Use on light backgrounds"


async def test_patch_creative_status_and_revision_note_persists(
    client: AsyncClient, entities: EntitySet
) -> None:
    patched = await client.patch(
        f"/creatives/{entities['creative_id']}",
        json={"copy_status": "approved", "revision_note": "Metadata reviewed"},
        headers=_auth(entities["token"]),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["manifest"]["copy_block"]["status"] == "approved"
    listed = await client.get(
        f"/jobs/{entities['job_id']}/creatives",
        headers=_auth(entities["token"]),
    )
    stored = next(row for row in listed.json() if row["id"] == entities["creative_id"])
    assert stored["manifest"]["copy_block"]["status"] == "approved"


async def test_patch_task_status_and_assignee_persists(
    client: AsyncClient, entities: EntitySet
) -> None:
    patched = await client.patch(
        f"/tasks/{entities['task_id']}",
        json={"status": "in_progress", "assignee": "zaid"},
        headers=_auth(entities["token"]),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "in_progress"
    assert patched.json()["assignee"] == "zaid"
    fetched = await client.get(
        f"/tasks/{entities['task_id']}", headers=_auth(entities["token"])
    )
    assert fetched.json()["assignee"] == "zaid"
