"""Tests for PATCH /admin/accounts/{id}"""

from __future__ import annotations

import uuid
from httpx import AsyncClient

from api.core.security import create_access_token
from conftest import superadmin_headers


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> str:
    resp = await client.post(
        "/tenants", json={"name": name, "slug": slug}, headers=superadmin_headers()
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["tenant"]["id"]


def _auth(tenant_id: str, role: str) -> dict[str, str]:
    token = create_access_token(tenant_id=tenant_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def test_owner_can_patch_account_role_and_scopes(client: AsyncClient) -> None:
    tenant_id = await _new_tenant(client, "Test Agency", "test-agency")
    headers = _auth(tenant_id, "owner")

    # Create a client to be used in client_scopes
    client_res = await client.post(
        "/clients", json={"name": "Client A"}, headers=headers
    )
    assert client_res.status_code == 201
    client_id = client_res.json()["id"]

    # Provision an account
    acc_res = await client.post(
        "/admin/accounts",
        json={"auth_subject": f"auth0|{uuid.uuid4()}", "role": "ops"},
        headers=headers,
    )
    assert acc_res.status_code == 201, acc_res.text
    account_id = acc_res.json()["id"]

    # Update role and client_scopes
    patch_res = await client.patch(
        f"/admin/accounts/{account_id}",
        json={"role": "designer", "client_scopes": [client_id]},
        headers=headers,
    )
    assert patch_res.status_code == 200, patch_res.text
    data = patch_res.json()
    assert data["role"] == "designer"
    assert data["client_scopes"] == [client_id]

    # Verify persistence
    list_res = await client.get("/admin/accounts", headers=headers)
    assert list_res.status_code == 200
    account_data = next(a for a in list_res.json() if a["id"] == account_id)
    assert account_data["role"] == "designer"
    assert account_data["client_scopes"] == [client_id]


async def test_non_owner_forbidden(client: AsyncClient) -> None:
    tenant_id = await _new_tenant(client, "Test Agency", "test-agency-2")
    owner_headers = _auth(tenant_id, "owner")
    ops_headers = _auth(tenant_id, "ops")

    acc_res = await client.post(
        "/admin/accounts",
        json={"auth_subject": f"auth0|{uuid.uuid4()}", "role": "ops"},
        headers=owner_headers,
    )
    account_id = acc_res.json()["id"]

    patch_res = await client.patch(
        f"/admin/accounts/{account_id}",
        json={"role": "admin"},
        headers=ops_headers,
    )
    assert patch_res.status_code == 403


async def test_patch_account_idor(client: AsyncClient) -> None:
    tenant_a = await _new_tenant(client, "Agency A", "agency-a")
    tenant_b = await _new_tenant(client, "Agency B", "agency-b")

    owner_a = _auth(tenant_a, "owner")
    owner_b = _auth(tenant_b, "owner")

    acc_res = await client.post(
        "/admin/accounts",
        json={"auth_subject": f"auth0|{uuid.uuid4()}", "role": "ops"},
        headers=owner_a,
    )
    account_a_id = acc_res.json()["id"]

    # Tenant B owner tries to patch Tenant A's account -> 404
    patch_res = await client.patch(
        f"/admin/accounts/{account_a_id}",
        json={"role": "admin"},
        headers=owner_b,
    )
    assert patch_res.status_code == 404


async def test_patch_account_client_scope_idor(client: AsyncClient) -> None:
    tenant_a = await _new_tenant(client, "Agency A", "agency-a-scopes")
    tenant_b = await _new_tenant(client, "Agency B", "agency-b-scopes")

    owner_a = _auth(tenant_a, "owner")
    owner_b = _auth(tenant_b, "owner")

    client_res = await client.post(
        "/clients", json={"name": "Client B"}, headers=owner_b
    )
    client_b_id = client_res.json()["id"]

    acc_res = await client.post(
        "/admin/accounts",
        json={"auth_subject": f"auth0|{uuid.uuid4()}", "role": "ops"},
        headers=owner_a,
    )
    account_a_id = acc_res.json()["id"]

    # Tenant A owner tries to give its account a client_scope from Tenant B -> 422
    patch_res = await client.patch(
        f"/admin/accounts/{account_a_id}",
        json={"client_scopes": [client_b_id]},
        headers=owner_a,
    )
    assert patch_res.status_code == 422
    assert "not found" in patch_res.text.lower()


async def test_patch_account_unknown_role(client: AsyncClient) -> None:
    tenant_id = await _new_tenant(client, "Test Agency", "test-agency-3")
    owner_headers = _auth(tenant_id, "owner")

    acc_res = await client.post(
        "/admin/accounts",
        json={"auth_subject": f"auth0|{uuid.uuid4()}", "role": "ops"},
        headers=owner_headers,
    )
    account_id = acc_res.json()["id"]

    patch_res = await client.patch(
        f"/admin/accounts/{account_id}",
        json={"role": "god_mode"},
        headers=owner_headers,
    )
    assert patch_res.status_code == 422
    assert "Unknown role" in patch_res.text
