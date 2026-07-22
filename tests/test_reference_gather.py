"""Reference gathering parses provider data without making real network calls."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from creative.references import gather as gather_module


async def test_gather_references_parses_openverse_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_urls: list[str] = []

    def fake_get(url: str) -> dict[str, object]:
        requested_urls.append(url)
        return {
            "results": [
                {
                    "title": "Quiet editorial wedding portrait",
                    "url": "https://images.example.test/original.jpg",
                    "thumbnail": "https://images.example.test/thumbnail.jpg",
                    "source": "flickr",
                    "tags": [
                        {"name": "editorial"},
                        {"name": "negative space"},
                        {"name": ""},
                    ],
                    "license": "cc-by",
                    "width": 1600,
                    "height": 1067,
                }
            ]
        }

    monkeypatch.setattr(gather_module, "_get", fake_get)

    candidates = await gather_module.gather_references("modern Muslim wedding editorial", limit=3)

    assert len(requested_urls) == 1
    query_params = parse_qs(urlparse(requested_urls[0]).query)
    assert query_params == {
        "q": ["modern Muslim wedding editorial"],
        "page_size": ["3"],
    }
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Quiet editorial wedding portrait"
    assert candidate.url == "https://images.example.test/original.jpg"
    assert candidate.thumbnail == "https://images.example.test/thumbnail.jpg"
    assert candidate.source == "flickr"
    assert candidate.tags == ["editorial", "negative space"]
    assert candidate.license == "cc-by"
    assert candidate.width == 1600
    assert candidate.height == 1067


async def test_gather_references_parses_unsplash_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[tuple[str, dict[str, str] | None]] = []

    def fake_get(url: str, *, headers: dict[str, str] | None = None) -> dict[str, object]:
        requested.append((url, headers))
        return {
            "total": 1,
            "total_pages": 1,
            "results": [
                {
                    "id": "unsplash-photo-1",
                    "description": None,
                    "alt_description": "Elegant Muslim matchmaking portrait",
                    "width": 2400,
                    "height": 3000,
                    "urls": {
                        "raw": "https://images.unsplash.com/raw.jpg",
                        "full": "https://images.unsplash.com/full.jpg",
                        "regular": "https://images.unsplash.com/regular.jpg",
                        "small": "https://images.unsplash.com/small.jpg",
                        "thumb": "https://images.unsplash.com/thumb.jpg",
                    },
                    "links": {"html": "https://unsplash.com/photos/unsplash-photo-1"},
                    "tags": [{"title": "editorial"}, {"title": "lavender"}],
                }
            ],
        }

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-unsplash-key")
    monkeypatch.setattr(gather_module, "_get", fake_get)

    candidates = await gather_module.gather_references(
        "Muslim matchmaking elegant", limit=4, source="unsplash"
    )

    assert len(requested) == 1
    requested_url, requested_headers = requested[0]
    assert parse_qs(urlparse(requested_url).query) == {
        "query": ["Muslim matchmaking elegant"],
        "per_page": ["4"],
    }
    assert requested_headers == {"Authorization": "Client-ID test-unsplash-key"}
    assert candidates == [
        gather_module.ReferenceCandidate(
            title="Elegant Muslim matchmaking portrait",
            url="https://images.unsplash.com/full.jpg",
            thumbnail="https://images.unsplash.com/small.jpg",
            source="unsplash",
            tags=["editorial", "lavender"],
            license="Unsplash License",
            width=2400,
            height=3000,
        )
    ]


async def test_gather_references_parses_pexels_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested: list[tuple[str, dict[str, str] | None]] = []

    def fake_get(url: str, *, headers: dict[str, str] | None = None) -> dict[str, object]:
        requested.append((url, headers))
        return {
            "page": 1,
            "per_page": 5,
            "total_results": 1,
            "photos": [
                {
                    "id": 101,
                    "width": 3200,
                    "height": 2133,
                    "url": "https://www.pexels.com/photo/101/",
                    "photographer": "Example Photographer",
                    "photographer_url": "https://www.pexels.com/@example",
                    "photographer_id": 10,
                    "avg_color": "#B7A6C9",
                    "src": {
                        "original": "https://images.pexels.com/photos/101/original.jpeg",
                        "large2x": "https://images.pexels.com/photos/101/large2x.jpeg",
                        "large": "https://images.pexels.com/photos/101/large.jpeg",
                        "medium": "https://images.pexels.com/photos/101/medium.jpeg",
                        "small": "https://images.pexels.com/photos/101/small.jpeg",
                        "portrait": "https://images.pexels.com/photos/101/portrait.jpeg",
                        "landscape": "https://images.pexels.com/photos/101/landscape.jpeg",
                        "tiny": "https://images.pexels.com/photos/101/tiny.jpeg",
                    },
                    "liked": False,
                    "alt": "Lavender editorial matchmaking campaign",
                }
            ],
        }

    monkeypatch.setenv("PEXELS_API_KEY", "test-pexels-key")
    monkeypatch.setattr(gather_module, "_get", fake_get)

    candidates = await gather_module.gather_references(
        "Muslim matchmaking editorial", limit=5, source="pexels"
    )

    assert len(requested) == 1
    requested_url, requested_headers = requested[0]
    assert parse_qs(urlparse(requested_url).query) == {
        "query": ["Muslim matchmaking editorial"],
        "per_page": ["5"],
    }
    assert requested_headers == {"Authorization": "test-pexels-key"}
    assert candidates == [
        gather_module.ReferenceCandidate(
            title="Lavender editorial matchmaking campaign",
            url="https://images.pexels.com/photos/101/original.jpeg",
            thumbnail="https://images.pexels.com/photos/101/medium.jpeg",
            source="pexels",
            tags=[],
            license="Pexels License",
            width=3200,
            height=2133,
        )
    ]


@pytest.mark.parametrize(
    ("source", "environment_variable", "message"),
    [
        (
            "unsplash",
            "UNSPLASH_ACCESS_KEY",
            "UNSPLASH: set UNSPLASH_ACCESS_KEY to use this source",
        ),
        ("pexels", "PEXELS_API_KEY", "PEXELS: set PEXELS_API_KEY to use this source"),
    ],
)
async def test_keyed_provider_requires_environment_key_before_request(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    environment_variable: str,
    message: str,
) -> None:
    def fail_get(url: str, *, headers: dict[str, str] | None = None) -> dict[str, object]:
        pytest.fail(f"network seam called without a provider key: {url=} {headers=}")

    monkeypatch.delenv(environment_variable, raising=False)
    monkeypatch.setattr(gather_module, "_get", fail_get)

    with pytest.raises(RuntimeError, match=f"^{message}$"):
        await gather_module.gather_references("matchmaking editorial", source=source)


def test_build_query_keeps_niche_and_two_strong_style_terms() -> None:
    query = gather_module.build_query(
        niche="  Muslim   matchmaking service ",
        medium="Instagram carousel",
        keywords=["elegant", "modest", "editorial", "ELEGANT", " "],
    )

    assert query == "Muslim matchmaking service elegant modest"


def test_build_query_broaden_keeps_only_two_strongest_terms() -> None:
    query = gather_module.build_query(
        niche="  Muslim   matchmaking service ",
        medium="Instagram carousel",
        keywords=["elegant", "modest", "editorial"],
        broaden=True,
    )

    assert query == "Muslim matchmaking service elegant"
