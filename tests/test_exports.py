"""Authenticated editable-export API contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient

from api.core.security import create_access_token
from api.db.session import get_session
from api.main import app
from creative.export import svg as svg_export


_ONE_PIXEL_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    async def _unused_session() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_session] = _unused_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _headers() -> dict[str, str]:
    token = create_access_token(tenant_id="tenant-glo2go", role="team")
    return {"Authorization": f"Bearer {token}"}


def _payload() -> dict[str, str]:
    return {
        "format_key": "ig_post",
        "image_ref": _ONE_PIXEL_PNG,
        "headline": "Skin boosters, explained",
        "sub": "A consultation-led plan.",
        "cta": "Book now",
        "palette_ink": "#5A2A6B",
        "palette_ground": "#FFFFFF",
        "badge_text": "Glo2Go Aesthetics",
        "text_region": "bottom_right",
    }


def test_svg_export_is_an_editable_attachment(client: TestClient) -> None:
    response = client.post("/exports/svg", json=_payload(), headers=_headers())

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.headers["content-disposition"] == (
        'attachment; filename="glo2go-aesthetics-ig_post.svg"'
    )
    assert response.content.startswith((b"<svg", b"<?xml"))


def test_png_preview_is_inline(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _preview(
        html: str,
        width: int,
        height: int,
        *,
        scale: int,
    ) -> bytes:
        assert "<svg" in html
        assert (width, height, scale) == (1080, 1080, 1)
        return b"png-preview"

    monkeypatch.setattr(svg_export, "render_html_to_png", _preview)

    response = client.post("/exports/png-preview", json=_payload(), headers=_headers())

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == "inline"
    assert response.content == b"png-preview"
