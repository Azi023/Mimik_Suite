"""Brief versioning: /revise mints the next version as a fresh DRAFT (non-destructive), seeded
from the source's sections, leaving the source unchanged. Covers the frozen source (the normal
case), a draft source, and the cross-tenant IDOR guard.
"""

from __future__ import annotations

from httpx import AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> str:
    resp = await client.post("/tenants", json={"name": name, "slug": slug})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _new_brand(client: AsyncClient, token: str) -> tuple[str, str]:
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]
    resp = await client.post(
        "/brands",
        json={"client_id": cid, "name": "ACME", "slug": "acme"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return cid, resp.json()["id"]


async def _brief_from_url(client: AsyncClient, token: str, brand_id: str) -> dict:
    """Create a brief with populated sections (patched extraction, no network) so we can prove
    the sections are preserved across a revise."""
    import api.services.brief_extraction as extraction

    fixture_html = (
        "<html><head><title>ACME Co</title>"
        "<style>body{color:#123456;font-family:'Inter',sans-serif}</style>"
        "</head><body><h1>We build widgets</h1></body></html>"
    )

    async def _fake_fetch(url: str) -> str:
        return fixture_html

    original_fetch = extraction._fetch_html
    original_guard = extraction._assert_public_http_url
    extraction._fetch_html = _fake_fetch
    extraction._assert_public_http_url = lambda url: None
    try:
        created = await client.post(
            "/briefs",
            json={"brand_id": brand_id, "url": "https://acme.example"},
            headers=_auth(token),
        )
    finally:
        extraction._fetch_html = original_fetch
        extraction._assert_public_http_url = original_guard
    assert created.status_code == 201, created.text
    return created.json()


async def test_revise_frozen_brief_mints_new_draft_version(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    _cid, bid = await _new_brand(client, token)
    source = await _brief_from_url(client, token, bid)
    source_id = source["id"]

    # Sign it off -> freeze (the normal case: revise a locked brief).
    signed = await client.post(
        f"/briefs/{source_id}/signoff",
        json={"signed_off_by": "designer@mimik"},
        headers=_auth(token),
    )
    assert signed.status_code == 200, signed.text
    assert signed.json()["status"] == "frozen"

    # Revise -> a NEW brief, version 2, draft, not frozen, sections carried forward.
    revised = await client.post(f"/briefs/{source_id}/revise", headers=_auth(token))
    assert revised.status_code == 201, revised.text
    new_brief = revised.json()
    assert new_brief["id"] != source_id
    assert new_brief["version"] == 2
    assert new_brief["status"] == "draft"
    assert new_brief["frozen_at"] is None
    assert new_brief["signed_off_by"] is None
    assert new_brief["client_id"] == source["client_id"]
    assert new_brief["brand_id"] == source["brand_id"]
    # Sections preserved from the frozen source (the editor starts from the frozen content).
    assert new_brief["sections"]["snapshot"] == source["sections"]["snapshot"]
    assert new_brief["sections"]["tokens"]["colors"][0]["hex"] == "#123456"

    # Non-destructive: the OLD brief is untouched — still frozen, still version 1.
    old = (await client.get(f"/briefs/{source_id}", headers=_auth(token))).json()
    assert old["status"] == "frozen"
    assert old["version"] == 1
    assert old["frozen_at"] is not None


async def test_revise_draft_brief_bumps_version(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    _cid, bid = await _new_brand(client, token)
    source = (
        await client.post("/briefs", json={"brand_id": bid}, headers=_auth(token))
    ).json()
    assert source["version"] == 1
    assert source["status"] == "draft"

    revised = await client.post(f"/briefs/{source['id']}/revise", headers=_auth(token))
    assert revised.status_code == 201, revised.text
    new_brief = revised.json()
    assert new_brief["id"] != source["id"]
    assert new_brief["version"] == 2
    assert new_brief["status"] == "draft"

    # Source draft is unchanged.
    old = (await client.get(f"/briefs/{source['id']}", headers=_auth(token))).json()
    assert old["version"] == 1


async def test_revise_foreign_brief_is_404(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    _cid, a_bid = await _new_brand(client, token_a)
    a_brief = (
        await client.post("/briefs", json={"brand_id": a_bid}, headers=_auth(token_a))
    ).json()["id"]

    # Tenant B cannot revise tenant A's brief even with the real id (IDOR guard).
    resp = await client.post(f"/briefs/{a_brief}/revise", headers=_auth(token_b))
    assert resp.status_code == 404, "IDOR: tenant B revised tenant A's brief!"
