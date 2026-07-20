"""IAM increment B: the role x scope capability layer.

Covers the pure matrix (has_capability truth table), the scope helpers (empty = all clients),
`require_capability` end-to-end via a provisioned Supabase account, and the gated
`GET /admin/capabilities` read endpoint. All additive — nothing switches off require_role.
"""

from __future__ import annotations

from conftest import superadmin_headers
from fastapi import Depends
from httpx import AsyncClient

from api.core.auth import (
    Principal,
    is_client_in_scope,
    principal_client_ids,
    require_capability,
)
from api.core.capabilities import (
    Capability,
    ROLE_CAPABILITIES,
    capabilities_matrix,
    has_capability,
)

# Reuse the Supabase keypair/JWKS mint fixture verbatim.
from test_auth_supabase import supabase_env  # noqa: F401


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- has_capability truth table --------------------------------------------------------


def test_super_admin_has_every_capability() -> None:
    for cap in Capability:
        assert has_capability("super_admin", cap)


def test_owner_has_all_but_manage_tenants() -> None:
    assert not has_capability("owner", Capability.MANAGE_TENANTS)
    assert has_capability("owner", Capability.MANAGE_BILLING)
    assert has_capability("owner", Capability.MANAGE_MEMBERS)
    assert has_capability("owner", Capability.MANAGE_CLIENTS)


def test_admin_is_owner_minus_billing_and_tenants() -> None:
    assert not has_capability("admin", Capability.MANAGE_TENANTS)
    assert not has_capability("admin", Capability.MANAGE_BILLING)
    assert has_capability("admin", Capability.MANAGE_MEMBERS)
    assert has_capability("admin", Capability.MANAGE_CLIENTS)
    assert has_capability("admin", Capability.APPROVE_INTERNAL)


def test_ops_and_designer_are_scoped_work_only() -> None:
    for role in ("ops", "designer"):
        assert has_capability(role, Capability.MANAGE_CLIENTS)
        assert has_capability(role, Capability.MANAGE_CREATIVES)
        assert has_capability(role, Capability.APPROVE_INTERNAL)
        assert not has_capability(role, Capability.MANAGE_MEMBERS)
        assert not has_capability(role, Capability.MANAGE_BILLING)
        assert not has_capability(role, Capability.CLIENT_PORTAL)


def test_client_has_only_portal() -> None:
    assert has_capability("client", Capability.CLIENT_PORTAL)
    assert not has_capability("client", Capability.MANAGE_CREATIVES)
    assert not has_capability("client", Capability.MANAGE_CLIENTS)


def test_unknown_role_has_no_capabilities() -> None:
    for cap in Capability:
        assert not has_capability("wizard", cap)


def test_every_actor_role_is_in_the_matrix() -> None:
    from mimik_contracts import ActorRole

    for role in ActorRole:
        assert role.value in ROLE_CAPABILITIES


# --- scope helpers ---------------------------------------------------------------------


def _principal(role: str, *, client_id: str | None = None, scopes: list[str] | None = None) -> Principal:
    return Principal(tenant_id="t1", role=role, client_id=client_id, client_scopes=scopes or [])


def test_empty_scope_means_all_clients() -> None:
    p = _principal("ops")
    assert principal_client_ids(p) is None
    assert is_client_in_scope(p, "any-client")


def test_non_empty_scope_restricts() -> None:
    p = _principal("designer", scopes=["c1", "c2"])
    assert principal_client_ids(p) == ["c1", "c2"]
    assert is_client_in_scope(p, "c1")
    assert not is_client_in_scope(p, "c3")


def test_client_role_scoped_to_own_client() -> None:
    p = _principal("client", client_id="c-owned")
    assert principal_client_ids(p) == ["c-owned"]
    assert is_client_in_scope(p, "c-owned")
    assert not is_client_in_scope(p, "c-other")


# --- require_capability dependency (end-to-end via a provisioned account) ---------------


async def _bootstrap_tenant(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post(
        "/tenants", json={"name": "Mimik", "slug": "mimik"}, headers=superadmin_headers()
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["tenant"]["id"], data["access_token"]


def _mount_probe() -> None:
    """Attach a couple of throwaway routes guarded by require_capability, once."""
    from api.main import app

    if any(getattr(r, "path", None) == "/_cap/members" for r in app.routes):
        return

    @app.get("/_cap/members")
    async def _members(  # noqa: ANN202
        principal: Principal = Depends(require_capability(Capability.MANAGE_MEMBERS)),
    ):
        return {"ok": True}

    @app.get("/_cap/billing")
    async def _billing(  # noqa: ANN202
        principal: Principal = Depends(require_capability(Capability.MANAGE_BILLING)),
    ):
        return {"ok": True}


async def test_require_capability_passes_role_with_cap(client: AsyncClient) -> None:
    _mount_probe()
    _tid, owner = await _bootstrap_tenant(client)  # first-party token, role=owner
    # owner HAS manage_members -> 200.
    resp = await client.get("/_cap/members", headers=_auth(owner))
    assert resp.status_code == 200, resp.text


async def test_require_capability_403s_role_lacking_cap(
    client: AsyncClient, supabase_env  # noqa: F811
) -> None:
    _mount_probe()
    _tid, owner = await _bootstrap_tenant(client)
    # Provision an ops account; ops lacks manage_members and manage_billing.
    prov = await client.post(
        "/admin/accounts",
        json={"auth_subject": "ops-cap", "role": "ops", "email": "ops-cap@example.com"},
        headers=_auth(owner),
    )
    assert prov.status_code == 201, prov.text
    ops = supabase_env("ops-cap")
    assert (await client.get("/_cap/members", headers=_auth(ops))).status_code == 403
    # owner has manage_members but NOT manage_billing? owner DOES have billing; ops does not.
    assert (await client.get("/_cap/billing", headers=_auth(ops))).status_code == 403


# --- GET /admin/capabilities -----------------------------------------------------------


async def test_capabilities_endpoint_returns_matrix(client: AsyncClient) -> None:
    _tid, owner = await _bootstrap_tenant(client)  # owner is allowed
    resp = await client.get("/admin/capabilities", headers=_auth(owner))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == capabilities_matrix()
    assert Capability.MANAGE_TENANTS.value in body["super_admin"]
    assert Capability.MANAGE_TENANTS.value not in body["owner"]
    assert Capability.MANAGE_BILLING.value not in body["admin"]


async def test_capabilities_endpoint_gated_from_scoped_roles(
    client: AsyncClient, supabase_env  # noqa: F811
) -> None:
    _tid, owner = await _bootstrap_tenant(client)
    await client.post(
        "/admin/accounts",
        json={"auth_subject": "ops-mtx", "role": "ops", "email": "ops-mtx@example.com"},
        headers=_auth(owner),
    )
    ops = supabase_env("ops-mtx")
    resp = await client.get("/admin/capabilities", headers=_auth(ops))
    assert resp.status_code == 403
