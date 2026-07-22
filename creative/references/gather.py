"""Gather candidate visual references for operator-led R&D.

Provider fetchers live in a small registry. Their blocking stdlib HTTP calls run in a
worker thread, and `_get` stays deliberately small so tests can replace the network
boundary. All returned strings, including tags, are untrusted web data: consumers must
sanitize and fence them before using them in any model prompt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import urllib.request
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

from pydantic import BaseModel

_OPENVERSE_ENDPOINT = "https://api.openverse.org/v1/images/"
_UNSPLASH_ENDPOINT = "https://api.unsplash.com/search/photos"
_PEXELS_ENDPOINT = "https://api.pexels.com/v1/search"


class ReferenceCandidate(BaseModel):
    """One unvetted search result; text and tags remain untrusted web data."""

    title: str
    url: str
    thumbnail: str | None
    source: str
    tags: list[str]
    license: str
    width: int | None
    height: int | None


type ReferenceFetcher = Callable[[str, int], Awaitable[list[ReferenceCandidate]]]


def _get(url: str, *, headers: dict[str, str] | None = None) -> object:
    """GET JSON from a fixed provider URL; urllib HTTP errors intentionally propagate."""
    request_headers = {"Accept": "application/json", "User-Agent": "Mimik-Suite/0.1"}
    if headers is not None:
        request_headers.update(headers)
    request = urllib.request.Request(
        url,
        headers=request_headers,
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def _clean_text(value: object, *, fallback: str) -> str:
    if isinstance(value, str):
        cleaned = " ".join(value.split())
        if cleaned:
            return cleaned
    return fallback


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _dimension(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _tags(value: object, *, name_key: str = "name") -> list[str]:
    if not isinstance(value, list):
        return []

    parsed: list[str] = []
    for tag in value:
        name: object = tag.get(name_key) if isinstance(tag, dict) else tag
        cleaned = _optional_text(name)
        if cleaned is not None:
            parsed.append(cleaned)
    return parsed


def _parse_openverse_candidate(item: dict[str, object], *, index: int) -> ReferenceCandidate:
    image_url = _optional_text(item.get("url")) or _optional_text(item.get("foreign_landing_url"))
    if image_url is None:
        raise ValueError(f"Openverse result {index} has no image URL")

    return ReferenceCandidate(
        title=_clean_text(item.get("title"), fallback="Untitled"),
        url=image_url,
        thumbnail=_optional_text(item.get("thumbnail")),
        source=_clean_text(item.get("source"), fallback="openverse"),
        tags=_tags(item.get("tags")),
        license=_clean_text(item.get("license"), fallback="unknown"),
        width=_dimension(item.get("width")),
        height=_dimension(item.get("height")),
    )


async def _fetch_openverse(query: str, limit: int) -> list[ReferenceCandidate]:
    params = urlencode({"q": query, "page_size": limit})
    payload = await asyncio.to_thread(_get, f"{_OPENVERSE_ENDPOINT}?{params}")
    if not isinstance(payload, dict):
        raise ValueError("Openverse response root is not an object")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("Openverse response has no results list")

    candidates: list[ReferenceCandidate] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise ValueError(f"Openverse result {index} is not an object")
        candidates.append(_parse_openverse_candidate(item, index=index))
    return candidates


def _require_provider_key(source: str, environment_variable: str) -> str:
    key = os.environ.get(environment_variable)
    if key is None or not key.strip():
        raise RuntimeError(f"{source}: set {environment_variable} to use this source")
    return key.strip()


def _parse_unsplash_candidate(item: dict[str, object], *, index: int) -> ReferenceCandidate:
    urls = item.get("urls")
    if not isinstance(urls, dict):
        raise ValueError(f"Unsplash result {index} has no urls object")

    image_url = (
        _optional_text(urls.get("full"))
        or _optional_text(urls.get("regular"))
        or _optional_text(urls.get("raw"))
    )
    if image_url is None:
        raise ValueError(f"Unsplash result {index} has no image URL")

    title_fallback = _clean_text(item.get("alt_description"), fallback="Untitled")
    return ReferenceCandidate(
        title=_clean_text(item.get("description"), fallback=title_fallback),
        url=image_url,
        thumbnail=_optional_text(urls.get("small")) or _optional_text(urls.get("thumb")),
        source="unsplash",
        tags=_tags(item.get("tags"), name_key="title"),
        license="Unsplash License",
        width=_dimension(item.get("width")),
        height=_dimension(item.get("height")),
    )


async def _fetch_unsplash(query: str, limit: int) -> list[ReferenceCandidate]:
    access_key = _require_provider_key("UNSPLASH", "UNSPLASH_ACCESS_KEY")
    params = urlencode({"query": query, "per_page": limit})
    payload = await asyncio.to_thread(
        _get,
        f"{_UNSPLASH_ENDPOINT}?{params}",
        headers={"Authorization": f"Client-ID {access_key}"},
    )
    if not isinstance(payload, dict):
        raise ValueError("Unsplash response root is not an object")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("Unsplash response has no results list")

    candidates: list[ReferenceCandidate] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise ValueError(f"Unsplash result {index} is not an object")
        candidates.append(_parse_unsplash_candidate(item, index=index))
    return candidates


def _parse_pexels_candidate(item: dict[str, object], *, index: int) -> ReferenceCandidate:
    sources = item.get("src")
    if not isinstance(sources, dict):
        raise ValueError(f"Pexels result {index} has no src object")

    image_url = (
        _optional_text(sources.get("original"))
        or _optional_text(sources.get("large2x"))
        or _optional_text(sources.get("large"))
    )
    if image_url is None:
        raise ValueError(f"Pexels result {index} has no image URL")

    thumbnail = (
        _optional_text(sources.get("medium"))
        or _optional_text(sources.get("small"))
        or _optional_text(sources.get("tiny"))
    )
    return ReferenceCandidate(
        title=_clean_text(item.get("alt"), fallback="Untitled"),
        url=image_url,
        thumbnail=thumbnail,
        source="pexels",
        tags=_tags(item.get("tags")),
        license="Pexels License",
        width=_dimension(item.get("width")),
        height=_dimension(item.get("height")),
    )


async def _fetch_pexels(query: str, limit: int) -> list[ReferenceCandidate]:
    api_key = _require_provider_key("PEXELS", "PEXELS_API_KEY")
    params = urlencode({"query": query, "per_page": limit})
    payload = await asyncio.to_thread(
        _get,
        f"{_PEXELS_ENDPOINT}?{params}",
        headers={"Authorization": api_key},
    )
    if not isinstance(payload, dict):
        raise ValueError("Pexels response root is not an object")

    results = payload.get("photos")
    if not isinstance(results, list):
        raise ValueError("Pexels response has no photos list")

    candidates: list[ReferenceCandidate] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            raise ValueError(f"Pexels result {index} is not an object")
        candidates.append(_parse_pexels_candidate(item, index=index))
    return candidates


# Provider registry: add new async fetchers here without changing gather_references.
FETCHERS: dict[str, ReferenceFetcher | None] = {
    "openverse": _fetch_openverse,
    "unsplash": _fetch_unsplash,
    "pexels": _fetch_pexels,
    "pinterest": None,  # TODO: Pinterest provider; access and licensing need validation.
    "dribbble": None,  # TODO: Dribbble provider; API access needs validation.
    "behance": None,  # TODO: Behance provider; API access and usage terms need validation.
    "envato": None,  # TODO: Envato provider; catalog API access needs validation.
}


def build_query(*, niche: str, medium: str, keywords: list[str], broaden: bool = False) -> str:
    """Compose a short deterministic query from the strongest normalized terms.

    Inputs are expected to be operator- or brand-supplied. Do not reuse gathered web tags
    here as prompt material without applying the project's untrusted-data safeguards.
    """
    terms: list[str] = []
    seen: set[str] = set()
    for raw_term in [niche, *keywords, medium]:
        term = " ".join(raw_term.split())
        dedupe_key = term.casefold()
        if term and dedupe_key not in seen:
            terms.append(term)
            seen.add(dedupe_key)

    if not terms:
        raise ValueError("niche, medium, or keywords must contain at least one search term")
    term_limit = 2 if broaden else 3
    return " ".join(terms[:term_limit])


async def gather_references(
    query: str,
    *,
    limit: int = 12,
    source: str = "openverse",
) -> list[ReferenceCandidate]:
    """Gather unvetted reference candidates from the selected provider."""
    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("query must not be blank")
    if isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    source_key = source.strip().casefold()
    if source_key not in FETCHERS:
        available = ", ".join(sorted(FETCHERS))
        raise ValueError(f"unsupported reference source {source!r}; available: {available}")
    fetcher = FETCHERS[source_key]
    if fetcher is None:
        raise NotImplementedError(f"reference source {source!r} is registered as a TODO")
    return await fetcher(normalized_query, limit)


def _safe_cli_text(value: str) -> str:
    printable = "".join(character if character.isprintable() else " " for character in value)
    return " ".join(printable.split())


def _main() -> None:
    parser = argparse.ArgumentParser(description="Gather visual references for operator review.")
    parser.add_argument("query", help="Search query to send to the selected provider.")
    parser.add_argument("--limit", type=int, default=12, help="Maximum candidates (default: 12).")
    parser.add_argument("--source", default="openverse", help="Fetcher name (default: openverse).")
    args = parser.parse_args()

    candidates = asyncio.run(gather_references(args.query, limit=args.limit, source=args.source))
    for candidate in candidates:
        print(
            " · ".join(
                _safe_cli_text(value)
                for value in (
                    candidate.title,
                    candidate.source,
                    candidate.license,
                    candidate.url,
                )
            )
        )


if __name__ == "__main__":
    _main()
