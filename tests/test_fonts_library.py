"""Built-in font library, brand materialization, and tenant-safe raw asset serving."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient

from api.core import config
from api.core.security import create_access_token
from mimik_contracts import BrandAsset

_BUILTIN_ROOT = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "builtin"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> tuple[str, str]:
    response = await client.post(
        "/tenants",
        json={"name": name, "slug": slug},
        headers=superadmin_headers(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["tenant"]["id"], body["access_token"]


async def _new_brand(client: AsyncClient, token: str, slug: str) -> str:
    client_response = await client.post(
        "/clients",
        json={"name": f"{slug.title()} Client"},
        headers=_auth(token),
    )
    assert client_response.status_code == 201, client_response.text
    brand_response = await client.post(
        "/brands",
        json={
            "client_id": client_response.json()["id"],
            "name": f"{slug.title()} Brand",
            "slug": slug,
        },
        headers=_auth(token),
    )
    assert brand_response.status_code == 201, brand_response.text
    return brand_response.json()["id"]


@pytest.fixture
def assets_root(tmp_path: Path):
    config._settings = config.Settings(assets_local_root=str(tmp_path / "assets"))
    yield tmp_path / "assets"
    config._settings = None


async def test_font_library_is_team_gated(client: AsyncClient) -> None:
    tenant_id, owner_token = await _new_tenant(client, "Mimik", "mimik-fonts")
    client_token = create_access_token(tenant_id=tenant_id, role="client")

    forbidden = await client.get("/fonts/library", headers=_auth(client_token))
    assert forbidden.status_code == 403

    response = await client.get("/fonts/library", headers=_auth(owner_token))
    assert response.status_code == 200, response.text
    library = response.json()
    assert [font["key"] for font in library] == [
        "poppins",
        "montserrat",
        "playfair-display",
        "inter",
        "lato",
        "nunito",
        "open-sans",
        "raleway",
        "amiri",
    ]
    assert all(
        set(font) == {"key", "family", "category", "preview_text"} for font in library
    )


def test_amiri_builtin_is_a_valid_arabic_truetype_font() -> None:
    from creative.render.builtin_fonts import get_builtin_font

    amiri = get_builtin_font("amiri")

    assert amiri is not None
    assert amiri.family == "Amiri"
    assert amiri.category == "arabic"
    assert amiri.preview_text == "وَمِنْ آيَاتِهِ أَنْ خَلَقَ لَكُم"
    assert amiri.regular_path == _BUILTIN_ROOT / "amiri" / "Amiri-Regular.ttf"
    assert amiri.bold_path == _BUILTIN_ROOT / "amiri" / "Amiri-Bold.ttf"
    expected_sha256 = {
        "Amiri-Regular.ttf": "ab391c4147d054c48976e98322ad0eefe1427aa0e0502a12a4c75d80a70cfcd7",
        "Amiri-Bold.ttf": "cfccb794268e7d573d857e6d6a67f89cf8a053e8ffd85dfa0c8ec1bb36fc4827",
    }
    required_tables = {b"cmap", b"GDEF", b"GSUB", b"GPOS", b"name"}
    for path in (amiri.regular_path, amiri.bold_path):
        data = path.read_bytes()
        assert data[:4] == b"\x00\x01\x00\x00"
        assert len(data) > 100_000
        table_count = int.from_bytes(data[4:6], "big")
        table_tags = {
            data[offset : offset + 4]
            for offset in range(12, 12 + table_count * 16, 16)
        }
        assert required_tables <= table_tags
        assert "Amiri".encode("utf-16-be") in data
        assert hashlib.sha256(data).hexdigest() == expected_sha256[path.name]

    license_text = (_BUILTIN_ROOT / "amiri" / "OFL.txt").read_text()
    assert "SIL OPEN FONT LICENSE Version 1.1" in license_text
    assert "The Amiri Project Authors" in license_text


async def test_materialize_builtin_font_creates_approved_tenant_scoped_asset(
    client: AsyncClient,
    assets_root: Path,
) -> None:
    tenant_a, token_a = await _new_tenant(client, "Agency A", "font-agency-a")
    _, token_b = await _new_tenant(client, "Agency B", "font-agency-b")
    brand_a = await _new_brand(client, token_a, "brand-a")

    response = await client.post(
        f"/brands/{brand_a}/fonts/poppins",
        headers=_auth(token_a),
    )
    assert response.status_code == 201, response.text
    asset = BrandAsset.model_validate(response.json())
    assert asset.tenant_id == tenant_a
    assert asset.brand_id == brand_a
    assert asset.kind.value == "font"
    assert asset.approved is True
    assert asset.mime == "font/ttf"
    assert asset.license == "OFL-1.1"
    assert asset.local_path is not None

    stored_path = Path(asset.local_path)
    assert stored_path.is_relative_to(assets_root / tenant_a / brand_a)
    assert stored_path.read_bytes() == (
        _BUILTIN_ROOT / "poppins" / "Poppins-Regular.ttf"
    ).read_bytes()

    foreign = await client.post(
        f"/brands/{brand_a}/fonts/poppins",
        headers=_auth(token_b),
    )
    assert foreign.status_code == 404, "IDOR: tenant B materialized a font for tenant A"


async def test_raw_asset_returns_bytes_and_mime_without_cross_tenant_access(
    client: AsyncClient,
    assets_root: Path,
) -> None:
    _, token_a = await _new_tenant(client, "Agency A", "raw-agency-a")
    _, token_b = await _new_tenant(client, "Agency B", "raw-agency-b")
    brand_a = await _new_brand(client, token_a, "raw-brand-a")
    created = await client.post(
        f"/brands/{brand_a}/fonts/lato",
        headers=_auth(token_a),
    )
    assert created.status_code == 201, created.text
    asset_id = created.json()["id"]

    response = await client.get(f"/assets/{asset_id}/raw", headers=_auth(token_a))
    assert response.status_code == 200, response.text
    assert response.content == (_BUILTIN_ROOT / "lato" / "Lato-Regular.ttf").read_bytes()
    assert response.headers["content-type"] == "font/ttf"

    foreign = await client.get(f"/assets/{asset_id}/raw", headers=_auth(token_b))
    assert foreign.status_code == 404, "IDOR: tenant B read tenant A's asset bytes"

    # A row cannot escape its server-generated tenant/brand directory through a symlink.
    stored_path = Path(created.json()["local_path"])
    outside_path = assets_root.parent / "outside.ttf"
    outside_path.write_bytes((_BUILTIN_ROOT / "lato" / "Lato-Regular.ttf").read_bytes())
    stored_path.unlink()
    stored_path.symlink_to(outside_path)
    escaped = await client.get(f"/assets/{asset_id}/raw", headers=_auth(token_a))
    assert escaped.status_code == 404
