"""Invitations: create -> copyable accept-link -> Supabase-verified accept provisions a UserAccount.

Reuses the `supabase_env` mint fixture from test_auth_supabase (a real ES256/JWKS token, no
network) so the accept path is exercised end-to-end. The mint helper stamps email=f"{sub}@example.com",
so an invite is addressed to that email to make the identity-match check pass.
"""

from __future__ import annotations

from conftest import superadmin_headers
from httpx import AsyncClient

# Reuse the Supabase keypair/JWKS fixture verbatim.
from test_auth_supabase import supabase_env  # noqa: F401


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _tenant_owner(client: AsyncClient, *, slug: str = "mimik") -> tuple[str, str]:
    resp = await client.post(
        "/tenants", json={"name": slug, "slug": slug}, headers=superadmin_headers()
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["tenant"]["id"], data["access_token"]


async def _invite(client: AsyncClient, owner: str, email: str, *, role: str = "ops", **over) -> dict:
    body = {"email": email, "role": role, **over}
    return await client.post("/invitations", json=body, headers=_auth(owner))


# --- create / list / revoke / resend ---------------------------------------------------


async def test_create_returns_pending_invite_and_accept_url(client: AsyncClient) -> None:
    _tid, owner = await _tenant_owner(client)
    resp = await _invite(client, owner, "designer@example.com", role="designer")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["invitation"]["status"] == "pending"
    assert body["invitation"]["email"] == "designer@example.com"
    assert body["invitation"]["role"] == "designer"
    # The copyable link carries a token to the accept route.
    assert "/invite/accept?token=" in body["accept_url"]


async def test_list_is_tenant_scoped(client: AsyncClient) -> None:
    _a, owner_a = await _tenant_owner(client, slug="a")
    _b, owner_b = await _tenant_owner(client, slug="b")
    await _invite(client, owner_a, "x@example.com")

    listed_a = await client.get("/invitations", headers=_auth(owner_a))
    listed_b = await client.get("/invitations", headers=_auth(owner_b))
    assert [i["email"] for i in listed_a.json()] == ["x@example.com"]
    assert listed_b.json() == []  # B never sees A's invites


async def test_unknown_role_rejected(client: AsyncClient) -> None:
    _tid, owner = await _tenant_owner(client)
    resp = await _invite(client, owner, "x@example.com", role="wizard")
    assert resp.status_code == 422


async def test_owner_cannot_invite_super_admin(client: AsyncClient) -> None:
    _tid, owner = await _tenant_owner(client)
    resp = await _invite(client, owner, "x@example.com", role="super_admin")
    assert resp.status_code == 403  # no privilege escalation via invite


async def test_duplicate_pending_invite_rejected(client: AsyncClient) -> None:
    _tid, owner = await _tenant_owner(client)
    assert (await _invite(client, owner, "dup@example.com")).status_code == 201
    assert (await _invite(client, owner, "dup@example.com")).status_code == 409


async def test_non_admin_cannot_invite(client: AsyncClient, supabase_env) -> None:  # noqa: F811
    _tid, owner = await _tenant_owner(client)
    await client.post(
        "/admin/accounts",
        json={"auth_subject": "ops-1", "role": "ops", "email": "ops-1@example.com"},
        headers=_auth(owner),
    )
    ops_token = supabase_env("ops-1")
    resp = await _invite(client, ops_token, "x@example.com")
    assert resp.status_code == 403


async def test_revoke_then_cannot_revoke_again(client: AsyncClient) -> None:
    _tid, owner = await _tenant_owner(client)
    inv = (await _invite(client, owner, "x@example.com")).json()["invitation"]
    ok = await client.post(f"/invitations/{inv['id']}/revoke", headers=_auth(owner))
    assert ok.status_code == 200
    assert ok.json()["status"] == "revoked"
    again = await client.post(f"/invitations/{inv['id']}/revoke", headers=_auth(owner))
    assert again.status_code == 409  # not pending anymore


async def test_revoke_foreign_tenant_invite_is_404(client: AsyncClient) -> None:
    _a, owner_a = await _tenant_owner(client, slug="a")
    _b, owner_b = await _tenant_owner(client, slug="b")
    inv = (await _invite(client, owner_a, "x@example.com")).json()["invitation"]
    # Tenant B cannot revoke tenant A's invite even with the real id.
    resp = await client.post(f"/invitations/{inv['id']}/revoke", headers=_auth(owner_b))
    assert resp.status_code == 404


async def test_resend_issues_fresh_link(client: AsyncClient) -> None:
    _tid, owner = await _tenant_owner(client)
    inv = (await _invite(client, owner, "x@example.com")).json()["invitation"]
    resp = await client.post(f"/invitations/{inv['id']}/resend", headers=_auth(owner))
    assert resp.status_code == 200
    assert "/invite/accept?token=" in resp.json()["accept_url"]


# --- accept (Supabase-verified invitee) ------------------------------------------------


def _token_from_url(accept_url: str) -> str:
    return accept_url.split("token=", 1)[1]


async def test_accept_provisions_account_with_role(client: AsyncClient, supabase_env) -> None:  # noqa: F811
    tid, owner = await _tenant_owner(client)
    # Invite the identity whose Supabase email will be invitee@example.com (mint stamps it).
    created = (await _invite(client, owner, "invitee@example.com", role="ops")).json()
    token = _token_from_url(created["accept_url"])

    invitee = supabase_env("invitee")  # -> email invitee@example.com
    resp = await client.post("/invitations/accept", json={"token": token}, headers=_auth(invitee))
    assert resp.status_code == 201, resp.text
    account = resp.json()
    assert account["tenant_id"] == tid
    assert account["role"] == "ops"
    assert account["email"] == "invitee@example.com"

    # The provisioned identity can now read the tenant (auth end-to-end).
    listed = await client.get("/clients", headers=_auth(invitee))
    assert listed.status_code == 200

    # Invite is consumed -> a second accept fails.
    again = await client.post("/invitations/accept", json={"token": token}, headers=_auth(invitee))
    assert again.status_code == 409


async def test_accept_copies_client_scopes_onto_account(
    client: AsyncClient, supabase_env  # noqa: F811
) -> None:
    tid, owner = await _tenant_owner(client)
    # Invite a designer restricted to two specific clients.
    created = (
        await _invite(
            client, owner, "invitee@example.com", role="designer", client_scopes=["c1", "c2"]
        )
    ).json()
    assert created["invitation"]["client_scopes"] == ["c1", "c2"]
    token = _token_from_url(created["accept_url"])

    invitee = supabase_env("invitee")
    resp = await client.post("/invitations/accept", json={"token": token}, headers=_auth(invitee))
    assert resp.status_code == 201, resp.text
    # The provisioned account carries the invite's scopes (via the UserAccount contract).
    assert resp.json()["client_scopes"] == ["c1", "c2"]

    # And the account is listed with those scopes for the admin UI.
    listed = await client.get("/admin/accounts", headers=_auth(owner))
    accounts = {a["auth_subject"]: a for a in listed.json()}
    assert accounts["invitee"]["client_scopes"] == ["c1", "c2"]


async def test_accept_default_scope_is_all_clients(
    client: AsyncClient, supabase_env  # noqa: F811
) -> None:
    _tid, owner = await _tenant_owner(client)
    created = (await _invite(client, owner, "invitee@example.com", role="ops")).json()
    token = _token_from_url(created["accept_url"])
    invitee = supabase_env("invitee")
    resp = await client.post("/invitations/accept", json={"token": token}, headers=_auth(invitee))
    assert resp.status_code == 201, resp.text
    # No scopes on the invite -> empty list on the account == ALL clients (current behavior).
    assert resp.json()["client_scopes"] == []


async def test_accept_email_mismatch_forbidden(client: AsyncClient, supabase_env) -> None:  # noqa: F811
    _tid, owner = await _tenant_owner(client)
    created = (await _invite(client, owner, "someone-else@example.com")).json()
    token = _token_from_url(created["accept_url"])
    # Verified identity is invitee@example.com, but the invite was for someone-else@ -> 403.
    invitee = supabase_env("invitee")
    resp = await client.post("/invitations/accept", json={"token": token}, headers=_auth(invitee))
    assert resp.status_code == 403


async def test_accept_revoked_invite_conflict(client: AsyncClient, supabase_env) -> None:  # noqa: F811
    _tid, owner = await _tenant_owner(client)
    created = (await _invite(client, owner, "invitee@example.com")).json()
    token = _token_from_url(created["accept_url"])
    await client.post(
        f"/invitations/{created['invitation']['id']}/revoke", headers=_auth(owner)
    )
    invitee = supabase_env("invitee")
    resp = await client.post("/invitations/accept", json={"token": token}, headers=_auth(invitee))
    assert resp.status_code == 409  # not pending


async def test_accept_garbage_token_rejected(client: AsyncClient, supabase_env) -> None:  # noqa: F811
    await _tenant_owner(client)
    invitee = supabase_env("invitee")
    resp = await client.post(
        "/invitations/accept", json={"token": "not.a.real.token"}, headers=_auth(invitee)
    )
    assert resp.status_code == 400
