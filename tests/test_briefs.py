"""Brief routes: create draft, read/list, signoff->freeze, freeze invariant, and IDOR guard."""

from __future__ import annotations

from conftest import superadmin_headers
from httpx import AsyncClient


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> str:
    resp = await client.post("/tenants", json={"name": name, "slug": slug}, headers=superadmin_headers())
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_brand(client: AsyncClient, token: str) -> tuple[str, str]:
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]
    resp = await client.post(
        "/brands",
        json={"client_id": cid, "name": "ACME", "slug": "acme"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return cid, resp.json()["id"]


async def test_create_draft_brief_and_get(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid, bid = await _new_brand(client, token)

    created = await client.post("/briefs", json={"brand_id": bid}, headers=_auth(token))
    assert created.status_code == 201, created.text
    brief = created.json()
    assert brief["status"] == "draft"
    assert brief["client_id"] == cid
    assert brief["frozen_at"] is None

    fetched = await client.get(f"/briefs/{brief['id']}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["id"] == brief["id"]


async def test_list_briefs_by_client(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    cid, bid = await _new_brand(client, token)
    b1 = (await client.post("/briefs", json={"brand_id": bid}, headers=_auth(token))).json()["id"]

    listed = await client.get(f"/briefs?client_id={cid}", headers=_auth(token))
    assert listed.status_code == 200
    assert [b["id"] for b in listed.json()] == [b1]


async def test_signoff_freezes_brief(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    _, bid = await _new_brand(client, token)
    brief_id = (
        await client.post("/briefs", json={"brand_id": bid}, headers=_auth(token))
    ).json()["id"]

    signed = await client.post(
        f"/briefs/{brief_id}/signoff",
        json={"signed_off_by": "designer@mimik"},
        headers=_auth(token),
    )
    assert signed.status_code == 200, signed.text
    body = signed.json()
    assert body["status"] == "frozen"
    assert body["signed_off_by"] == "designer@mimik"
    assert body["frozen_at"] is not None

    # A second signoff on a frozen brief is rejected (non-destructive; new change = new version).
    again = await client.post(
        f"/briefs/{brief_id}/signoff",
        json={"signed_off_by": "someone_else"},
        headers=_auth(token),
    )
    assert again.status_code == 409


async def test_update_draft_sections_persists(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    _, bid = await _new_brand(client, token)
    brief_id = (
        await client.post("/briefs", json={"brand_id": bid}, headers=_auth(token))
    ).json()["id"]

    # Fill the human-authored sections (6-9) plus refine §1.
    sections = {
        "snapshot": "ACME builds artisanal widgets for makers.",
        "voice_tone": "Warm, precise, a little playful.",
        "imagery_style": "Bright product photography on paper grounds.",
        "guardrails_dos": ["Use the wordmark", "Keep 5% margins"],
        "guardrails_donts": ["No stock gradients"],
        "deliverable_formats": ["ig_post", "poster_a"],
    }
    patched = await client.patch(
        f"/briefs/{brief_id}", json=sections, headers=_auth(token)
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["sections"]["snapshot"] == sections["snapshot"]
    assert body["sections"]["guardrails_dos"] == ["Use the wordmark", "Keep 5% margins"]
    assert body["sections"]["deliverable_formats"] == ["ig_post", "poster_a"]

    # Persisted, not just echoed.
    fetched = await client.get(f"/briefs/{brief_id}", headers=_auth(token))
    assert fetched.json()["sections"]["imagery_style"] == sections["imagery_style"]


async def test_update_frozen_brief_rejected(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    _, bid = await _new_brand(client, token)
    brief_id = (
        await client.post("/briefs", json={"brand_id": bid}, headers=_auth(token))
    ).json()["id"]
    await client.post(
        f"/briefs/{brief_id}/signoff",
        json={"signed_off_by": "designer@mimik"},
        headers=_auth(token),
    )

    # A frozen brief is locked — edits must go through /revise, never in-place.
    resp = await client.patch(
        f"/briefs/{brief_id}", json={"snapshot": "sneaky edit"}, headers=_auth(token)
    )
    assert resp.status_code == 409


async def test_update_brief_idor_across_tenants(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    _, a_bid = await _new_brand(client, token_a)
    a_brief_id = (
        await client.post("/briefs", json={"brand_id": a_bid}, headers=_auth(token_a))
    ).json()["id"]

    # Tenant B cannot edit tenant A's draft -> 404 (tenant-scoped at the data layer).
    leaked = await client.patch(
        f"/briefs/{a_brief_id}", json={"snapshot": "hijack"}, headers=_auth(token_b)
    )
    assert leaked.status_code == 404, "IDOR: tenant B edited tenant A's brief!"


async def test_idor_brief_isolation_across_tenants(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "a")
    token_b = await _new_tenant(client, "Agency B", "b")
    _, a_bid = await _new_brand(client, token_a)
    a_brief_id = (
        await client.post("/briefs", json={"brand_id": a_bid}, headers=_auth(token_a))
    ).json()["id"]

    # Tenant A reads its own brief.
    assert (
        await client.get(f"/briefs/{a_brief_id}", headers=_auth(token_a))
    ).status_code == 200

    # Tenant B, valid token + correct id, must NOT read tenant A's brief -> 404.
    leaked = await client.get(f"/briefs/{a_brief_id}", headers=_auth(token_b))
    assert leaked.status_code == 404, "IDOR: tenant B read tenant A's brief!"

    # Tenant B cannot sign off tenant A's brief either.
    hijack = await client.post(
        f"/briefs/{a_brief_id}/signoff",
        json={"signed_off_by": "attacker"},
        headers=_auth(token_b),
    )
    assert hijack.status_code == 404

    # Tenant B's listing is empty.
    assert (await client.get("/briefs", headers=_auth(token_b))).json() == []


async def test_brief_create_from_url_extracts_sections(client: AsyncClient) -> None:
    """A {url} on create triggers extraction. We patch the fetch so no network is used."""
    import api.services.brief_extraction as extraction

    token = await _new_tenant(client, "Mimik", "mimik")
    _, bid = await _new_brand(client, token)

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
    # Bypass the SSRF guard for this fixture host — egress rejection is covered by
    # tests/test_ssrf_guard.py; this test only exercises URL -> extraction parsing.
    extraction._assert_public_http_url = lambda url: None
    try:
        created = await client.post(
            "/briefs",
            json={"brand_id": bid, "url": "https://acme.example"},
            headers=_auth(token),
        )
    finally:
        extraction._fetch_html = original_fetch
        extraction._assert_public_http_url = original_guard

    assert created.status_code == 201, created.text
    sections = created.json()["sections"]
    assert "ACME Co" in sections["snapshot"]
    assert sections["tokens"]["colors"][0]["hex"] == "#123456"
    assert sections["tokens"]["typography"]["heading_font"] == "Inter"


async def test_brief_create_rejects_non_http_url(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "mimik")
    _, bid = await _new_brand(client, token)
    resp = await client.post(
        "/briefs",
        json={"brand_id": bid, "url": "file:///etc/passwd"},
        headers=_auth(token),
    )
    assert resp.status_code == 422
