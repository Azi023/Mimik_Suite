"""Client-scoped Studio generation: API orchestration, persistence, and artifact reads."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from conftest import superadmin_headers
from httpx import AsyncClient
from mimik_contracts import CopyBlock

from api.services import creative_generation
from creative.references.gather import ReferenceCandidate
from creative.vision.text_region import TextRegion


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAADED76LAAAAFElEQVR4nGOo6OjHgA0wYRUdtBIAuqUBm3K9vGMAAAAASUVORK5CYII="
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _ImageResponse:
    headers = {"Content-Type": "image/png", "Content-Length": str(len(_PNG))}

    def __enter__(self) -> _ImageResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return _PNG if amount < 0 else _PNG[:amount]


class _ImageOpener:
    def open(self, *_args: object, **_kwargs: object) -> _ImageResponse:
        return _ImageResponse()


def test_pexels_download_disables_automatic_redirects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_build_opener(handler: object) -> _ImageOpener:
        assert getattr(handler, "__name__", handler.__class__.__name__) == "_NoRedirect"
        return _ImageOpener()

    monkeypatch.setattr("urllib.request.build_opener", fake_build_opener)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: pytest.fail("default urlopen follows redirects before validation"),
    )

    written = creative_generation._download_pexels_photo(
        "https://images.pexels.com/photos/123/pexels-photo-123.png",
        tmp_path,
    )

    assert written.read_bytes() == _PNG


async def test_generate_creative_creates_record_and_preview(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    async def fake_gather(
        query: str,
        *,
        limit: int,
        source: str,
    ) -> list[ReferenceCandidate]:
        assert "skin clinic" in query.casefold()
        assert "hydration" in query.casefold()
        assert (limit, source) == (1, "pexels")
        return [
            ReferenceCandidate(
                title="Clinic portrait",
                url="https://images.pexels.com/photos/123/pexels-photo-123.png",
                thumbnail=None,
                source="pexels",
                tags=[],
                license="Pexels License",
                width=1080,
                height=1080,
            )
        ]

    async def fake_region(_image_ref: str) -> TextRegion:
        return TextRegion(region="bottom_right", reason="calm negative space")

    async def fake_glo2go(*_args: object, **_kwargs: object) -> bytes:
        return b"profile-render"

    async def fake_rasterize(svg: str, format_key: str) -> bytes:
        assert "data-design-rule-ids" in svg
        assert format_key == "ig_post"
        return b"preview-png"

    async def fake_psd(**kwargs: object) -> bytes:
        assert kwargs["format_key"] == "ig_post"
        assert kwargs["headline"] == "Hydration, explained"
        return b"8BPS-layered"

    def fake_draft(*_args: object, **_kwargs: object) -> CopyBlock:
        return CopyBlock(
            headline="Hydration, explained",
            subhead="A consultation-led approach",
            cta="Book a consultation",
        )

    def fake_prompt(_prompt: str) -> str:
        return (
            '{"image_prompt":"A credible premium skin clinic portrait with soft natural '
            'light, restrained plum accents, clean medical styling, calm negative space, '
            'editorial depth and one clear subject without signage or words.",'
            '"art_direction_notes":"stock search direction"}'
        )

    monkeypatch.setattr("creative.references.gather.gather_references", fake_gather)
    monkeypatch.setattr("creative.vision.text_region.find_text_region", fake_region)
    monkeypatch.setattr("creative.render.glo2go_templates.render_glo2go", fake_glo2go)
    monkeypatch.setattr("creative.export.svg.rasterize_svg_to_png", fake_rasterize)
    monkeypatch.setattr("creative.export.psd.render_creative_psd", fake_psd)
    monkeypatch.setattr("creative.copy.l0.draft_copy", fake_draft)
    monkeypatch.setattr(
        "creative.art_direction.default_generate",
        lambda: (fake_prompt, "test-art-director"),
    )
    monkeypatch.setattr("urllib.request.build_opener", lambda *_args: _ImageOpener())

    owner = (
        await client.post(
            "/tenants",
            json={"name": "Mimik", "slug": "mimik"},
            headers=superadmin_headers(),
        )
    ).json()["access_token"]
    client_id = (
        await client.post(
            "/clients",
            json={"name": "Glo2Go", "industry": "Skin clinic"},
            headers=_auth(owner),
        )
    ).json()["id"]
    brand = await client.post(
        "/brands",
        json={
            "client_id": client_id,
            "name": "Glo2Go Aesthetics",
            "slug": "glo2go-aesthetics",
            "niche": "skin clinic",
            "tokens": {
                "colors": [
                    {"name": "primary", "hex": "#5A2A6B"},
                    {"name": "ground", "hex": "#FFFFFF"},
                ]
            },
        },
        headers=_auth(owner),
    )
    assert brand.status_code == 201, brand.text

    generated = await client.post(
        f"/clients/{client_id}/creatives:generate",
        json={"topic": "hydration", "pillar": "Education"},
        headers=_auth(owner),
    )

    assert generated.status_code == 200, generated.text
    payload = generated.json()
    creative = payload["creative"]
    assert payload["preview_url"] == f"/creatives/{creative['id']}/preview"
    assert payload["svg_url"] == f"/exports/svg?creative_id={creative['id']}"
    assert payload["psd_url"] == f"/creatives/{creative['id']}/export.psd"
    assert creative["manifest"]["copy_block"]["headline"] == "Hydration, explained"
    assert creative["manifest"]["layers"][0]["recipe"]["params"]["style_profile_id"] == (
        "glo2go-aesthetics"
    )

    jobs = await client.get(f"/jobs?client_id={client_id}", headers=_auth(owner))
    assert jobs.status_code == 200
    assert [(job["id"], job["status"]) for job in jobs.json()] == [
        (creative["job_id"], "internal_review")
    ]

    latest = await client.get(
        f"/clients/{client_id}/creatives/latest",
        headers=_auth(owner),
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["creative"]["id"] == creative["id"]

    preview = await client.get(payload["preview_url"], headers=_auth(owner))
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"] == "image/png"
    assert preview.content == b"preview-png"

    svg = await client.get(payload["svg_url"], headers=_auth(owner))
    assert svg.status_code == 200, svg.text
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert b"layer-headline" in svg.content

    psd = await client.get(payload["psd_url"], headers=_auth(owner))
    assert psd.status_code == 200, psd.text
    assert psd.headers["content-type"] == "image/vnd.adobe.photoshop"
    assert psd.content == b"8BPS-layered"

    other_owner = (
        await client.post(
            "/tenants",
            json={"name": "Other agency", "slug": "other-agency"},
            headers=superadmin_headers(),
        )
    ).json()["access_token"]
    assert (
        await client.post(
            f"/clients/{client_id}/creatives:generate",
            json={"topic": "cross-tenant attempt"},
            headers=_auth(other_owner),
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/clients/{client_id}/creatives/latest",
            headers=_auth(other_owner),
        )
    ).status_code == 404
    for artifact_url in (payload["preview_url"], payload["svg_url"], payload["psd_url"]):
        assert (await client.get(artifact_url, headers=_auth(other_owner))).status_code == 404
