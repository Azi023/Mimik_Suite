"""Tenant-safe font-pack downloads for Brand Kit v2."""

from __future__ import annotations

import io
import zipfile

from conftest import superadmin_headers
from httpx import AsyncClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_tenant(client: AsyncClient, name: str, slug: str) -> str:
    response = await client.post(
        "/tenants",
        json={"name": name, "slug": slug},
        headers=superadmin_headers(),
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


async def _new_brand(
    client: AsyncClient,
    token: str,
    *,
    slug: str,
    typography: dict[str, object] | None = None,
) -> str:
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
            "tokens": {"typography": typography or {}},
        },
        headers=_auth(token),
    )
    assert brand_response.status_code == 201, brand_response.text
    return brand_response.json()["id"]


def _open_zip(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data))


async def test_font_pack_hides_a_brand_in_another_tenant(client: AsyncClient) -> None:
    token_a = await _new_tenant(client, "Agency A", "font-pack-a")
    token_b = await _new_tenant(client, "Agency B", "font-pack-b")
    brand_a = await _new_brand(client, token_a, slug="brand-a")

    response = await client.get(f"/brands/{brand_a}/font-pack", headers=_auth(token_b))

    assert response.status_code == 404, "IDOR: tenant B downloaded tenant A's fonts"


async def test_font_pack_contains_builtin_font_files_and_licenses(
    client: AsyncClient,
) -> None:
    token = await _new_tenant(client, "Mimik", "font-pack-mimik")
    brand_id = await _new_brand(
        client,
        token,
        slug="glo2go",
        typography={
            "font_roles": [
                {
                    "role": "heading",
                    "source": "builtin",
                    "builtin_key": "poppins",
                    "weights": ["400", "700"],
                }
            ]
        },
    )

    response = await client.get(f"/brands/{brand_id}/font-pack", headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == ('attachment; filename="glo2go-fonts.zip"')
    with _open_zip(response.content) as archive:
        names = set(archive.namelist())
        assert "fonts/poppins/Poppins-Regular.ttf" in names
        assert "fonts/poppins/Poppins-Bold.ttf" in names
        assert "LICENSES.txt" in names


async def test_font_pack_empty_state_contains_readme(client: AsyncClient) -> None:
    token = await _new_tenant(client, "Mimik", "font-pack-empty")
    brand_id = await _new_brand(client, token, slug="unconfigured")

    response = await client.get(f"/brands/{brand_id}/font-pack", headers=_auth(token))

    assert response.status_code == 200, response.text
    with _open_zip(response.content) as archive:
        assert set(archive.namelist()) == {"README.txt", "LICENSES.txt"}
        readme = archive.read("README.txt").decode("utf-8")
        assert "Unconfigured Brand" in readme
        assert "No fonts are configured yet" in readme
