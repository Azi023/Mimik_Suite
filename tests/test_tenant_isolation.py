"""P0 acceptance: tenant isolation. These are the guard tests for the #1 security invariant.

If any of these regress, cross-tenant data leakage is possible — treat a failure as a
release blocker.
"""

from __future__ import annotations

from conftest import superadmin_headers
from httpx import AsyncClient
from sqlalchemy import select

from api.db.models import JobRow
from api.db.session import get_session
from api.main import app


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> tuple[dict, str]:
    resp = await client.post("/tenants", json={"name": name, "slug": slug}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["tenant"], data["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_client_crud_happy_path(client: AsyncClient) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    created = await client.post("/clients", json={"name": "RCD Central", "industry": "healthcare"}, headers=_auth(token))
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    listed = await client.get("/clients", headers=_auth(token))
    assert listed.status_code == 200
    assert [c["id"] for c in listed.json()] == [cid]

    fetched = await client.get(f"/clients/{cid}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "RCD Central"


async def test_patch_client_returns_updated_fields(client: AsyncClient) -> None:
    _, token = await _new_tenant(client, "Mimik", "mimik")
    created = await client.post(
        "/clients",
        json={"name": "RCD Central", "industry": "healthcare"},
        headers=_auth(token),
    )
    client_id = created.json()["id"]

    updated = await client.patch(
        f"/clients/{client_id}",
        json={
            "name": "RCD Studio",
            "industry": "Healthcare and wellness",
            "contact_email": "team@rcd.example",
        },
        headers=_auth(token),
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "RCD Studio"
    assert updated.json()["industry"] == "Healthcare and wellness"
    assert updated.json()["contact_email"] == "team@rcd.example"
    fetched = await client.get(f"/clients/{client_id}", headers=_auth(token))
    assert fetched.json()["name"] == "RCD Studio"


async def test_idor_client_read_blocked_across_tenants(client: AsyncClient) -> None:
    _, token_a = await _new_tenant(client, "Agency A", "a")
    _, token_b = await _new_tenant(client, "Agency B", "b")

    created = await client.post("/clients", json={"name": "A's client"}, headers=_auth(token_a))
    a_client_id = created.json()["id"]

    # Tenant A can read its own client.
    assert (await client.get(f"/clients/{a_client_id}", headers=_auth(token_a))).status_code == 200

    # Tenant B, with a VALID token and the correct id, must NOT read tenant A's client -> 404.
    leaked = await client.get(f"/clients/{a_client_id}", headers=_auth(token_b))
    assert leaked.status_code == 404, "IDOR: tenant B read tenant A's client!"

    # Tenant B's listing must not include tenant A's data.
    b_list = await client.get("/clients", headers=_auth(token_b))
    assert b_list.json() == []


async def test_idor_client_patch_blocked_across_tenants(client: AsyncClient) -> None:
    _, token_a = await _new_tenant(client, "Agency A", "a")
    _, token_b = await _new_tenant(client, "Agency B", "b")
    created = await client.post(
        "/clients", json={"name": "A's client"}, headers=_auth(token_a)
    )
    client_id = created.json()["id"]

    leaked = await client.patch(
        f"/clients/{client_id}",
        json={"name": "Tenant B took over"},
        headers=_auth(token_b),
    )

    assert leaked.status_code == 404, "IDOR: tenant B edited tenant A's client!"
    fetched = await client.get(f"/clients/{client_id}", headers=_auth(token_a))
    assert fetched.json()["name"] == "A's client"


async def test_idor_core_entity_patch_and_delete_blocked_across_tenants(
    client: AsyncClient,
) -> None:
    """Every mutable core route resolves the real id inside the caller's tenant."""
    _, token_a = await _new_tenant(client, "Agency A", "a")
    _, token_b = await _new_tenant(client, "Agency B", "b")
    headers_a = _auth(token_a)
    headers_b = _auth(token_b)

    client_id = (
        await client.post("/clients", json={"name": "A client"}, headers=headers_a)
    ).json()["id"]
    brand_id = (
        await client.post(
            "/brands",
            json={"client_id": client_id, "name": "A brand", "slug": "a-brand"},
            headers=headers_a,
        )
    ).json()["id"]
    brief_id = (
        await client.post("/briefs", json={"brand_id": brand_id}, headers=headers_a)
    ).json()["id"]
    job_id = (
        await client.post(
            "/jobs",
            json={"brand_id": brand_id, "title": "A job", "format_key": "ig_post"},
            headers=headers_a,
        )
    ).json()["id"]
    creative_id = (
        await client.post(
            f"/jobs/{job_id}/creatives",
            json={
                "template_key": "centered_hero",
                "copy_block": {"headline": "Tenant A only"},
            },
            headers=headers_a,
        )
    ).json()["id"]
    task_id = (
        await client.post(
            "/tasks",
            json={"client_id": client_id, "type": "comment", "title": "A task"},
            headers=headers_a,
        )
    ).json()["id"]
    asset_id = (
        await client.post(
            f"/brands/{brand_id}/assets/register",
            json={
                "kind": "logo",
                "drive_file_id": "drive-a-logo",
                "filename": "a-logo.png",
                "mime": "image/png",
            },
            headers=headers_a,
        )
    ).json()["id"]

    patches = {
        f"/clients/{client_id}": {"name": "Taken client"},
        f"/brands/{brand_id}": {"brand_voice": "Taken voice"},
        f"/briefs/{brief_id}": {"snapshot": "Taken brief"},
        f"/jobs/{job_id}": {"title": "Taken job"},
        f"/creatives/{creative_id}": {"copy_status": "approved"},
        f"/tasks/{task_id}": {"status": "done", "assignee": "tenant-b"},
        f"/assets/{asset_id}": {"notes": "Taken asset"},
    }
    for path, payload in patches.items():
        response = await client.patch(path, json=payload, headers=headers_b)
        assert response.status_code == 404, f"IDOR PATCH succeeded for {path}: {response.text}"

    for path in patches:
        response = await client.delete(path, headers=headers_b)
        assert response.status_code == 404, f"IDOR DELETE succeeded for {path}: {response.text}"

    assert (
        await client.get(f"/clients/{client_id}", headers=headers_a)
    ).json()["name"] == "A client"
    assert (
        await client.get(f"/brands/{brand_id}", headers=headers_a)
    ).json()["brand_voice"] is None
    assert (
        await client.get(f"/briefs/{brief_id}", headers=headers_a)
    ).json()["sections"]["snapshot"] is None
    session_gen = app.dependency_overrides[get_session]()
    session = await session_gen.__anext__()
    try:
        stored_job = (
            await session.execute(select(JobRow).where(JobRow.id == job_id))
        ).scalar_one()
        assert stored_job.tenant_id == (
            await client.get(f"/jobs/{job_id}", headers=headers_a)
        ).json()["tenant_id"]
        assert stored_job.title == "A job"
        assert stored_job.deleted_at is None
    finally:
        await session_gen.aclose()
    creative = await client.get(
        f"/jobs/{job_id}/creatives", headers=headers_a
    )
    assert creative.json()[0]["manifest"]["copy_block"]["status"] == "draft"
    assert (
        await client.get(f"/tasks/{task_id}", headers=headers_a)
    ).json()["assignee"] is None
    assets = await client.get(f"/brands/{brand_id}/assets", headers=headers_a)
    assert assets.json()[0]["notes"] is None


async def test_brand_cannot_attach_to_another_tenants_client(client: AsyncClient) -> None:
    _, token_a = await _new_tenant(client, "Agency A", "a")
    _, token_b = await _new_tenant(client, "Agency B", "b")

    a_client_id = (await client.post("/clients", json={"name": "A's client"}, headers=_auth(token_a))).json()["id"]

    # Tenant B tries to create a brand attached to tenant A's client -> 404 (cross-tenant attach blocked).
    resp = await client.post(
        "/brands",
        json={"client_id": a_client_id, "name": "Hijack", "slug": "hijack"},
        headers=_auth(token_b),
    )
    assert resp.status_code == 404


async def test_unauthenticated_access_rejected(client: AsyncClient) -> None:
    # Missing credentials and a bad token are both rejected (401 Unauthorized).
    assert (await client.get("/clients")).status_code == 401
    assert (await client.get("/clients", headers=_auth("garbage.token.value"))).status_code == 401
