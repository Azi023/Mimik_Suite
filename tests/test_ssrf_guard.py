"""SSRF guard: the brief-extraction fetcher must refuse non-public targets.

The URL is tenant-supplied. These assert the server won't be tricked into reading internal
resources (cloud metadata, the DB host, RFC1918). All checks are offline — the guard raises
before any socket connect (literal IPs and `localhost` resolve locally, no egress).
"""

from __future__ import annotations

import pytest

from api.services.brief_extraction import _assert_public_http_url, extract_brief_sections


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata (link-local)
        "http://127.0.0.1/",                          # loopback
        "http://localhost/",                          # loopback by name
        "http://10.0.0.5/",                           # RFC1918 private
        "http://192.168.1.1/",                        # RFC1918 private
        "http://172.16.0.9/",                         # RFC1918 private
        "http://[::1]/",                              # IPv6 loopback
        "http://0.0.0.0/",                            # unspecified
    ],
)
def test_internal_targets_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        _assert_public_http_url(url)


@pytest.mark.parametrize("url", ["ftp://example.com", "file:///etc/passwd", "gopher://x", "//nohost"])
def test_non_http_schemes_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        _assert_public_http_url(url)


async def test_extract_rejects_metadata_endpoint_before_fetch() -> None:
    # The public entrypoint must apply the guard (raise, never fetch).
    with pytest.raises(ValueError):
        await extract_brief_sections("http://169.254.169.254/latest/meta-data/")
