"""Brand-brief extraction: URL -> BriefSections (§1-5 auto-draft).

Deterministic, evidence-only extraction. The invariant here mirrors the human rule in
`mimik-knowledge/prompts/brand_brief_extraction.md`: **report only what the page shows,
never fabricate a color, font, or claim.** Fields the evidence can't support stay `None`.

Fetch strategy (degrades cleanly, no network install ever attempted):
  1. Browser path (RICH, optional): ProofKit's Playwright capture renders JS and reads
     computed styles. Used ONLY if `proofkit` + `playwright` are importable. See
     `_fetch_html_via_browser`. Currently a clean seam — neither is installed in this env.
  2. Stdlib path (DEFAULT): `urllib` GETs the raw HTML. No JS execution, so it sees only
     server-rendered markup + linked/inline CSS. This is what runs today.

The LLM/vision enrichment (voice/tone polish, palette-from-screenshot on the free Gemini
tier) is deferred to P2 and sits behind the `_vision_pass` seam — see the TODO there. We do
NOT call any paid LLM/vision API here.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.request
from html import unescape
from urllib.parse import urljoin, urlparse

from mimik_contracts import BriefSections, BrandTokens, ColorRole, Typography

_USER_AGENT = "MimikSuite-BriefExtractor/0.1 (+https://mimikcreations.com)"
_FETCH_TIMEOUT_S = 15
_MAX_BYTES = 3_000_000  # cap the read so a hostile/huge page can't exhaust memory

# Hex colors in CSS / inline styles / style attributes. 3- or 6-digit.
_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
# font-family declarations, e.g. font-family: "Inter", Helvetica, sans-serif;
# Value runs until the declaration terminator (; } or end) — quotes ARE allowed inside it.
_FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}]+)", re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

# Generic CSS font keywords that are NOT brand typefaces — never report these as a font.
_GENERIC_FONTS = {
    "inherit", "initial", "unset", "serif", "sans-serif", "monospace",
    "cursive", "fantasy", "system-ui", "ui-sans-serif", "ui-serif",
    "ui-monospace", "ui-rounded", "-apple-system", "blinkmacsystemfont",
    "revert", "revert-layer", "none",
}


def _strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", fragment))).strip()


def _first(pattern: re.Pattern[str], html: str) -> str | None:
    m = pattern.search(html)
    if not m:
        return None
    text = _strip_tags(m.group(1))
    return text or None


def extract_colors(html: str, *, limit: int = 6) -> list[ColorRole]:
    """Pull distinct hex colors, most-frequent first, and role-label the top few.

    We label by frequency rank only (primary/secondary/accent...). We do NOT guess semantic
    intent — that's a human/vision call in §3's usage rules, left for the designer.
    """
    counts: dict[str, int] = {}
    for raw in _HEX_RE.findall(html):
        hexval = raw.lower()
        if len(hexval) == 4:  # expand #abc -> #aabbcc so downstream hex is always 6-digit
            hexval = "#" + "".join(c * 2 for c in hexval[1:])
        counts[hexval] = counts.get(hexval, 0) + 1
    ordered = sorted(counts, key=lambda h: (-counts[h], h))[:limit]
    roles = ["primary", "secondary", "accent"]
    out: list[ColorRole] = []
    for i, hexval in enumerate(ordered):
        name = roles[i] if i < len(roles) else f"color_{i + 1}"
        out.append(ColorRole(name=name, hex=hexval, usage=None))
    return out


def extract_fonts(html: str) -> Typography:
    """Read the first real font family from each `font-family` declaration.

    Skips generic CSS keywords (sans-serif, system-ui, ...). First distinct family seen is
    treated as the heading font, the second as body — a heuristic, refined by the designer.
    """
    families: list[str] = []
    seen: set[str] = set()
    for decl in _FONT_FAMILY_RE.findall(html):
        first_family = decl.split(",")[0].strip().strip("\"'").strip()
        key = first_family.lower()
        if not first_family or key in _GENERIC_FONTS or key in seen:
            continue
        seen.add(key)
        families.append(first_family)
    heading = families[0] if families else None
    body = families[1] if len(families) > 1 else None
    return Typography(heading_font=heading, body_font=body, hierarchy=[])


def build_snapshot(html: str) -> str | None:
    """§1 snapshot from <title> + <meta description> + first <h1>. Evidence only."""
    parts: list[str] = []
    for value in (_first(_TITLE_RE, html), _first(_META_DESC_RE, html), _first(_H1_RE, html)):
        if value and value not in parts:
            parts.append(value)
    if not parts:
        return None
    return " — ".join(parts)


def _voice_tone_note(snapshot: str | None) -> str | None:
    """Heuristic §5 placeholder. A short, honest note — not fabricated adjectives.

    TODO(P2): replace with an LLM pass over the full page copy + socials, prompted by
    `mimik-knowledge/prompts/brand_brief_extraction.md`, on the free Gemini tier. That pass
    infers real voice adjectives and quotes an example line. Until then we only state what
    we grounded the note in, so the designer knows it's a stub, not an inference.
    """
    if snapshot is None:
        return None
    return (
        "Heuristic note (no LLM pass yet): derived from on-page title/description copy. "
        "Voice adjectives + a quoted example line are a P2 LLM/vision task — do not treat "
        "this as a finished §5."
    )


# --- SSRF egress guard -----------------------------------------------------------------
# The URL is TENANT-SUPPLIED (untrusted). Before any fetch, resolve the host and refuse
# non-public targets — loopback, private (RFC1918), link-local (incl. 169.254.169.254 cloud
# metadata), reserved, multicast. This stops a client from making the server read internal
# resources (the DB, metadata endpoints, other tenants' infra).

def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254) so the v4 checks apply.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or not ip.is_global
    )


def _assert_public_http_url(url: str) -> None:
    """Raise ValueError unless `url` is http(s) AND every resolved IP is a public address."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs can be extracted.")
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host.")
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {host}") from exc
    if not infos:
        raise ValueError(f"Could not resolve host: {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_disallowed_ip(ip):
            raise ValueError(f"Refusing to fetch a non-public address ({ip}) — SSRF guard.")


# --- fetch seams -----------------------------------------------------------------------

def _browser_available() -> bool:
    """True only if BOTH ProofKit and Playwright import. Neither is installed here today."""
    try:
        import playwright.async_api  # noqa: F401
        import proofkit  # noqa: F401
    except ImportError:
        return False
    return True


async def _fetch_html_via_browser(url: str) -> str:
    """RICH path (optional upgrade). Renders JS + reads computed styles via ProofKit.

    TODO(browser upgrade): wire this to ProofKit's
    `proofkit.qualify.browser.capture_page(url)` (returns rendered `html` + a computed
    `font_families` sweep) or `proofkit.collector.playwright_capture.PlaywrightCapture`.
    Both lazily import Playwright and read *computed* CSS, which catches fonts/colors that
    the stdlib path misses (JS-injected styles, external stylesheets). Gated by
    `_browser_available()`; only reached once `proofkit` + `playwright` are installed.
    """
    from proofkit.qualify.browser import capture_page  # pragma: no cover - optional dep

    snapshot = await capture_page(url)  # pragma: no cover - optional dep
    return snapshot.get("html", "")  # pragma: no cover - optional dep


_MAX_REDIRECTS = 5


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never auto-follow a redirect — the default opener would follow a 3xx to an internal
    target (e.g. cloud metadata) WITHOUT re-running the SSRF guard. We follow manually,
    re-validating each hop, so the validated IP and the connected IP can't diverge via a
    redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _fetch_html_via_urllib(url: str) -> str:
    """DEFAULT path. Raw server-rendered HTML via stdlib. No JS, no browser needed.

    Redirects are followed manually with a per-hop SSRF re-check (`_assert_public_http_url`),
    closing the validate-then-use TOCTOU where a public URL 3xx-redirects to an internal one.
    (A same-host DNS rebind between check and connect remains a residual of the stdlib path —
    fully closing it needs connect-to-pinned-IP, a follow-up if this graduates to the browser
    fetch.)
    """
    opener = urllib.request.build_opener(_NoRedirect)
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        req = urllib.request.Request(current, headers={"User-Agent": _USER_AGENT})
        try:
            # nosec B310: scheme + public-IP validated by the caller / per-hop below.
            with opener.open(req, timeout=_FETCH_TIMEOUT_S) as resp:  # noqa: S310
                raw = resp.read(_MAX_BYTES)
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise
            location = exc.headers.get("Location")
            if not location:
                raise ValueError("redirect without a Location header") from exc
            current = urljoin(current, location)
            _assert_public_http_url(current)  # re-validate the redirect target before following
    raise ValueError(f"too many redirects (> {_MAX_REDIRECTS})")


async def _fetch_html(url: str) -> str:
    if _browser_available():
        return await _fetch_html_via_browser(url)
    return _fetch_html_via_urllib(url)


def _vision_pass(sections: BriefSections, html: str) -> BriefSections:
    """Seam for the P2 free-Gemini vision/LLM enrichment. No-op today.

    TODO(P2): screenshot the rendered page, send it (plus the extracted copy) to the free
    Gemini tier using `mimik-knowledge/prompts/brand_brief_extraction.md`, and fill/refine
    §1 snapshot, §2 logo_notes, and §5 voice_tone from what the model *observes* — still
    evidence-bound, never invented. No paid API. Returns sections unchanged for now.
    """
    return sections


# --- public entrypoint -----------------------------------------------------------------

def extract_brief_sections_from_html(html: str) -> BriefSections:
    """Pure, network-free core: HTML string -> BriefSections. Unit-testable with a fixture."""
    snapshot = build_snapshot(html)
    tokens = BrandTokens(
        colors=extract_colors(html),
        typography=extract_fonts(html),
    )
    sections = BriefSections(
        snapshot=snapshot,
        logo_notes=None,  # §2 needs vision (logo mark + assessment) — a P2/human task.
        tokens=tokens,
        voice_tone=_voice_tone_note(snapshot),
        # §6-9 are human-filled; leave defaults (empty).
    )
    return _vision_pass(sections, html)


async def extract_brief_sections(url: str) -> BriefSections:
    """Scrape `url` and auto-draft brief sections §1-5.

    The URL is untrusted (tenant-supplied); `_assert_public_http_url` rejects non-public
    targets before any network call (SSRF defence).
    """
    _assert_public_http_url(url)
    html = await _fetch_html(url)
    return extract_brief_sections_from_html(html)
