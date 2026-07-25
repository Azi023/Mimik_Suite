"""POST /tenants is gated to super_admin — closes the unauthenticated tenant-creation hole
(anyone could previously create a tenant and mint an owner token)."""

from __future__ import annotations

from httpx import AsyncClient

from api.core.security import create_access_token, decode_access_token
from conftest import superadmin_headers


async def test_create_tenant_rejects_anonymous(client: AsyncClient) -> None:
    resp = await client.post("/tenants", json={"name": "Mimik", "slug": "mimik"})
    assert resp.status_code in (401, 403)  # no bearer -> not authenticated


async def test_create_tenant_forbidden_for_non_superadmin(client: AsyncClient) -> None:
    owner = create_access_token(tenant_id="t-x", role="owner")
    resp = await client.post(
        "/tenants",
        json={"name": "Mimik", "slug": "mimik"},
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert resp.status_code == 403  # authenticated, but not a platform operator


async def test_create_tenant_allowed_for_superadmin(client: AsyncClient) -> None:
    resp = await client.post(
        "/tenants", json={"name": "Mimik", "slug": "mimik"}, headers=superadmin_headers()
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["tenant"]["slug"] == "mimik"
    # The founding principal of the new tenant is its OWNER (not a super_admin).
    assert decode_access_token(body["access_token"])["role"] == "owner"


async def test_tenant_list_and_suspend_reject_non_superadmin(
    client: AsyncClient,
) -> None:
    created = await client.post(
        "/tenants",
        json={"name": "Mimik", "slug": "mimik"},
        headers=superadmin_headers(),
    )
    tenant_id = created.json()["tenant"]["id"]
    owner_headers = {
        "Authorization": f"Bearer {created.json()['access_token']}"
    }

    assert (await client.get("/tenants", headers=owner_headers)).status_code == 403
    assert (
        await client.patch(
            f"/tenants/{tenant_id}",
            json={"suspended": True},
            headers=owner_headers,
        )
    ).status_code == 403


async def test_superadmin_can_list_suspend_and_reactivate_tenant(
    client: AsyncClient,
) -> None:
    created = await client.post(
        "/tenants",
        json={"name": "Mimik", "slug": "mimik"},
        headers=superadmin_headers(),
    )
    tenant_id = created.json()["tenant"]["id"]

    listed = await client.get("/tenants", headers=superadmin_headers())
    assert listed.status_code == 200, listed.text
    assert tenant_id in {tenant["id"] for tenant in listed.json()}

    suspended = await client.patch(
        f"/tenants/{tenant_id}",
        json={"suspended": True},
        headers=superadmin_headers(),
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["suspended_at"] is not None

    reactivated = await client.patch(
        f"/tenants/{tenant_id}",
        json={"suspended": False},
        headers=superadmin_headers(),
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["suspended_at"] is None
