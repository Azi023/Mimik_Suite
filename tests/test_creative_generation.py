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


# --- Live-path brand-QA (M-08 / Lane A): run_live_qa against the ACTUAL rendered output -----
#
# The live generation path renders a semantic SVG (named, bbox-carrying layers) + a raster
# preview and bypasses creative.pipeline, so these gate creative.qa.live.run_live_qa directly.
# render_creative_svg is browser-free when handed a data-URI image + an explicit badge
# luminance, so the SVG geometry/colours are deterministic; only the pixel-sampling checks
# (headline contrast, logo luminance) need Playwright and are skipped without it.

from creative.export.svg import render_creative_svg  # noqa: E402
from creative.qa.live import run_live_qa  # noqa: E402
from creative.render.compositor import browser_available  # noqa: E402
from creative.style_profile import get_style_profile  # noqa: E402
from mimik_contracts import Brand, BrandTokens  # noqa: E402

_qa_browser = pytest.mark.skipif(not browser_available(), reason="playwright not installed")


def _solid_png(hex_color: str, width: int, height: int) -> bytes:
    """A real solid-color RGBA PNG, stdlib-only (no PIL)."""
    import struct
    import zlib

    r, g, b = (int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    row = b"\x00" + bytes((r, g, b, 255)) * width
    raw = row * height

    def chunk(typ: bytes, data: bytes) -> bytes:
        payload = typ + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _png_data_uri(hex_color: str, size: int = 8) -> str:
    return "data:image/png;base64," + base64.b64encode(_solid_png(hex_color, size, size)).decode("ascii")


def _qa_brand() -> Brand:
    return Brand(tenant_id="t1", client_id="c1", slug="glo2go", name="Glo2Go", tokens=BrandTokens())


def _qa_svg(*, ink: str, ground: str, logo_ref: str | None = None, badge_bg: float = 0.95) -> str:
    """A real Glo2Go hero SVG (browser-free: data-URI image + explicit badge luminance).

    badge_bg high (light) -> "plum" badge theme -> the badge rect fills with palette_ink, which
    is what reproduces the purple-on-purple logo case when the logo is also plum.
    """
    return render_creative_svg(
        format_key="ig_post",
        image_ref=_png_data_uri("#CCCCCC"),
        headline="Skin boosters, explained",
        sub="What they do and who they suit",
        cta="Book a consult",
        palette_ink=ink,
        palette_ground=ground,
        badge_text="G2G",
        logo_ref=logo_ref,
        badge_background_luminance=badge_bg,
    )


@_qa_browser
async def test_live_qa_flags_low_contrast_headline() -> None:
    # Near-white ink on a white rendered ground: the sampled headline contrast fails and a
    # scrim/darker ground is requested.
    svg = _qa_svg(ink="#F0F0F0", ground="#FFFFFF")
    preview = _solid_png("#FFFFFF", 1080, 1080)
    report = await run_live_qa(
        preview, svg, brand=_qa_brand(), profile=None,
        format_key="ig_post", source_kind="brand_placeholder", expect_logo=False,
    )
    assert not report.passed
    assert any(f.startswith("contrast:") for f in report.failures), report.failures
    assert report.needs_scrim


@_qa_browser
async def test_live_qa_flags_invisible_logo() -> None:
    # The Glo2Go dogfood regression: a plum mark on the plum badge ground.
    plum = "#5A2A6B"
    svg = _qa_svg(ink=plum, ground="#FFFFFF", logo_ref=_png_data_uri(plum))
    preview = _solid_png("#FFFFFF", 1080, 1080)
    report = await run_live_qa(
        preview, svg, brand=_qa_brand(), profile=None,
        format_key="ig_post", source_kind="licensed_stock", expect_logo=True,
    )
    assert any("mark-vs-ground" in f for f in report.failures), report.failures


@_qa_browser
async def test_live_qa_passes_knockout_logo() -> None:
    # A white knockout mark on the same plum badge ground stays visible.
    svg = _qa_svg(ink="#5A2A6B", ground="#FFFFFF", logo_ref=_png_data_uri("#FFFFFF"))
    preview = _solid_png("#FFFFFF", 1080, 1080)
    report = await run_live_qa(
        preview, svg, brand=_qa_brand(), profile=None,
        format_key="ig_post", source_kind="ai_realistic", expect_logo=True,
    )
    assert not any("mark-vs-ground" in f for f in report.failures), report.failures


async def test_live_qa_simply_nikah_rejects_real_photo_source() -> None:
    # Modesty/source guard: Simply Nikah forbids real photography of people. Pure code — no
    # browser needed, so this runs everywhere.
    svg = _qa_svg(ink="#2B0A2E", ground="#FAF7FB")
    preview = _solid_png("#FAF7FB", 1080, 1080)
    report = await run_live_qa(
        preview, svg, brand=_qa_brand(), profile=get_style_profile("simply-nikah"),
        format_key="ig_post", source_kind="licensed_stock", expect_logo=False,
    )
    assert not report.passed
    assert any(f.startswith("source:") and "Simply Nikah" in f for f in report.failures), report.failures


async def test_live_qa_simply_nikah_allows_generated_vector() -> None:
    svg = _qa_svg(ink="#2B0A2E", ground="#FAF7FB")
    preview = _solid_png("#FAF7FB", 1080, 1080)
    report = await run_live_qa(
        preview, svg, brand=_qa_brand(), profile=get_style_profile("simply-nikah"),
        format_key="ig_post", source_kind="generated_vector", expect_logo=False,
    )
    assert not any(f.startswith("source:") for f in report.failures), report.failures
