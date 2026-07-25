"""Brand Kit v2 — Export: the PDF/PNG endpoints are registered, team-gated, tenant-scoped, and
validate the section key. The actual Playwright render is patched to fixed bytes (mirroring how
tests/test_compositor.py skips without a browser) so the suite is green in CI with no chromium.
"""

from __future__ import annotations

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"
_PDF_BYTES = b"%PDF-1.7\nfake-pdf-body\n%%EOF"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, slug: str = "mimik") -> str:
    resp = await client.post(
        "/tenants", json={"name": slug.title(), "slug": slug}, headers=superadmin_headers()
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _new_brand(client: AsyncClient, token: str) -> str:
    cid = (await client.post("/clients", json={"name": "ACME"}, headers=_auth(token))).json()["id"]
    return (
        await client.post(
            "/brands", json={"client_id": cid, "name": "ACME", "slug": "acme"}, headers=_auth(token)
        )
    ).json()["id"]


@pytest.fixture
def patched_render(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Patch the compositor render funcs the brands router calls so no real browser is needed.
    Captures the URL each render was asked to fetch, so tests can assert on the export contract."""
    captured: dict[str, str] = {}

    async def _fake_pdf(url: str) -> bytes:
        captured["pdf_url"] = url
        return _PDF_BYTES

    async def _fake_png(url: str, selector: str, *, scale: int = 2) -> bytes:
        captured["png_url"] = url
        captured["png_selector"] = selector
        captured["png_scale"] = str(scale)
        return _PNG_BYTES

    monkeypatch.setattr("api.routers.brands.render_url_to_pdf", _fake_pdf)
    monkeypatch.setattr("api.routers.brands.render_url_element_to_png", _fake_png)
    return captured


async def test_pdf_export_returns_pdf(
    client: AsyncClient, patched_render: dict[str, str]
) -> None:
    token = await _new_tenant(client)
    bid = await _new_brand(client, token)

    resp = await client.get(f"/brands/{bid}/brand-book.pdf", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert 'filename="acme-brand-book.pdf"' in resp.headers["content-disposition"]
    assert resp.content == _PDF_BYTES
    # The exporter navigated to the INTERNAL web route in export mode.
    assert "/book/" in patched_render["pdf_url"]
    assert patched_render["pdf_url"].endswith("?export=pdf")


async def test_png_export_returns_png_and_targets_section(
    client: AsyncClient, patched_render: dict[str, str]
) -> None:
    token = await _new_tenant(client)
    bid = await _new_brand(client, token)

    resp = await client.get(f"/brands/{bid}/brand-book/discovery.png", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert 'filename="acme-discovery.png"' in resp.headers["content-disposition"]
    assert resp.content == _PNG_BYTES
    assert patched_render["png_selector"] == '[data-kit-section="discovery"]'
    assert patched_render["png_scale"] == "2"
    assert "export=png&section=discovery" in patched_render["png_url"]


async def test_png_export_rejects_unknown_section(
    client: AsyncClient, patched_render: dict[str, str]
) -> None:
    token = await _new_tenant(client)
    bid = await _new_brand(client, token)
    resp = await client.get(f"/brands/{bid}/brand-book/bogus.png", headers=_auth(token))
    assert resp.status_code == 422
    # No render was attempted for an invalid section.
    assert "png_url" not in patched_render


async def test_export_is_team_gated(client: AsyncClient, patched_render: dict[str, str]) -> None:
    from api.core.security import create_access_token

    token = await _new_tenant(client)
    bid = await _new_brand(client, token)
    client_token = create_access_token(tenant_id="mimik", role="client")

    assert (
        await client.get(f"/brands/{bid}/brand-book.pdf", headers=_auth(client_token))
    ).status_code == 403
    assert (await client.get(f"/brands/{bid}/brand-book.pdf")).status_code == 401


async def test_export_idor(client: AsyncClient, patched_render: dict[str, str]) -> None:
    token_a = await _new_tenant(client, slug="agency-a")
    token_b = await _new_tenant(client, slug="agency-b")
    a_bid = await _new_brand(client, token_a)
    # Tenant B cannot export tenant A's brand book -> 404 (data-layer scoping).
    assert (
        await client.get(f"/brands/{a_bid}/brand-book.pdf", headers=_auth(token_b))
    ).status_code == 404
    assert (
        await client.get(
            f"/brands/{a_bid}/brand-book/discovery.png", headers=_auth(token_b)
        )
    ).status_code == 404
