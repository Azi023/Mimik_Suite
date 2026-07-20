"""Storefront intake: the public claim form captures a prospect + starts a draft brief (no
outbound fetch); the authenticated cold-bootstrap does the SSRF-guarded extraction."""

from __future__ import annotations

from conftest import superadmin_headers
import pytest
from httpx import AsyncClient

from mimik_contracts import BriefSections, BrandTokens, ColorRole


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _storefront(client: AsyncClient) -> tuple[str, str]:
    """Create a storefront tenant; return (slug, owner_token)."""
    resp = await client.post("/tenants", json={"name": "Mimik", "slug": "mimik-store"}, headers=superadmin_headers())
    return "mimik-store", resp.json()["access_token"]


async def test_claim_creates_prospect_and_draft_brief(client: AsyncClient) -> None:
    slug, _owner = await _storefront(client)
    resp = await client.post(
        "/intake/claim",
        json={
            "tenant_slug": slug,
            "name": "Rivera Dental",
            "email": "hi@riveradental.com",
            "brand_name": "Rivera Dental Care",
            "website_url": "https://riveradental.com",
            "instagram": "@riveradental",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] is True
    assert body["client"]["contact_email"] == "hi@riveradental.com"
    assert "Prospect via claim form" in body["client"]["notes"]
    assert body["brief"]["status"] == "draft"  # a brief is started


async def test_claim_is_idempotent_by_email(client: AsyncClient) -> None:
    slug, _owner = await _storefront(client)
    payload = {"tenant_slug": slug, "name": "Rivera", "email": "hi@rivera.com"}
    first = await client.post("/intake/claim", json=payload)
    second = await client.post("/intake/claim", json=payload)
    assert first.json()["created"] is True
    assert second.json()["created"] is False  # resubmit returns the same prospect
    assert second.json()["client"]["id"] == first.json()["client"]["id"]


async def test_claim_unknown_storefront_is_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/intake/claim", json={"tenant_slug": "nope", "name": "X", "email": "x@x.com"}
    )
    assert resp.status_code == 404


async def test_claim_rejects_non_http_url(client: AsyncClient) -> None:
    slug, _owner = await _storefront(client)
    resp = await client.post(
        "/intake/claim",
        json={"tenant_slug": slug, "name": "X", "email": "x@x.com", "website_url": "ftp://x"},
    )
    assert resp.status_code == 422


async def test_claim_does_not_fetch(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # The public endpoint must never trigger an outbound fetch (SSRF/DoS amplifier).
    import api.services.brief_extraction as be

    async def _boom(url: str):
        raise AssertionError("public claim endpoint must not fetch")

    monkeypatch.setattr(be, "extract_brief_sections", _boom)
    slug, _owner = await _storefront(client)
    resp = await client.post(
        "/intake/claim",
        json={"tenant_slug": slug, "name": "X", "email": "x@x.com",
              "website_url": "https://example.com"},
    )
    assert resp.status_code == 201


async def test_cold_bootstrap_extracts_behind_auth(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug, owner = await _storefront(client)
    made = await client.post(
        "/intake/claim",
        json={"tenant_slug": slug, "name": "Rivera", "email": "hi@rivera.com",
              "website_url": "https://rivera.example"},
    )
    client_id = made.json()["client"]["id"]

    # Stub the extraction (no network): the bootstrap wires the URL through the SSRF-guarded seam.
    async def _fake_extract(url: str) -> BriefSections:
        assert url == "https://rivera.example"
        return BriefSections(
            snapshot="Rivera Dental — gentle family dentistry",
            tokens=BrandTokens(colors=[ColorRole(name="primary", hex="#0a7d5a")]),
        )

    monkeypatch.setattr("api.routers.intake.extract_brief_sections", _fake_extract)
    resp = await client.post(f"/clients/{client_id}/bootstrap", headers=_auth(owner))
    assert resp.status_code == 200, resp.text
    assert resp.json()["sections"]["snapshot"].startswith("Rivera Dental")


async def test_cold_bootstrap_requires_auth(client: AsyncClient) -> None:
    slug, owner = await _storefront(client)
    made = await client.post(
        "/intake/claim",
        json={"tenant_slug": slug, "name": "X", "email": "x@x.com",
              "website_url": "https://x.example"},
    )
    client_id = made.json()["client"]["id"]
    # No token -> 401/403 (never anonymous fetch).
    resp = await client.post(f"/clients/{client_id}/bootstrap")
    assert resp.status_code in (401, 403)


async def test_cold_bootstrap_without_url_is_422(client: AsyncClient) -> None:
    slug, owner = await _storefront(client)
    made = await client.post(
        "/intake/claim", json={"tenant_slug": slug, "name": "X", "email": "x@x.com"}
    )
    client_id = made.json()["client"]["id"]
    resp = await client.post(f"/clients/{client_id}/bootstrap", headers=_auth(owner))
    assert resp.status_code == 422


async def test_claim_caps_oversized_public_input(client: AsyncClient) -> None:
    slug, _owner = await _storefront(client)
    resp = await client.post(
        "/intake/claim",
        json={"tenant_slug": slug, "name": "X", "email": "x@x.com", "notes": "A" * 5000},
    )
    assert resp.status_code == 422  # notes exceeds the 4000-char cap
