"""Leonardo.ai image generation via browser automation (subscription path, no API cost).

Drives the Leonardo.ai WEB app on the operator's subscription through a LOGGED-IN Playwright
persistent profile (bootstrap once via `scripts/leonardo_login.py`). No API key, no per-image
spend — the fragility (UI drift, rate limits) is accepted and isolated behind this adapter, so
swapping to a paid image API later stays a one-line config change (register a different class).

The stealth launch + human-pacing live in `stealth_browser.py`. This module is just the
Leonardo-specific flow: navigate → type the prompt → generate → grab the first result → save.

⚠ SELECTORS — GUESSED, tuned against the live UI on first real run — expect to adjust these.
    The live Leonardo DOM was NOT available while writing this; every selector below is a
    best-guess robust (role/text/placeholder) locator. Each generation STEP is a small helper
    that raises a clear, actionable error naming the step that failed, so first-run tuning is a
    matter of fixing one constant and re-running. The guessed selectors, per step:

      _LOGIN_MARKERS      : URL substrings that mean "not logged in" -> ("login", "auth", "signin")
      _PROMPT_BOX         : prompt textarea      -> placeholder=~"prompt" (fallback role=textbox)
      _GENERATE_BUTTON    : the Generate button  -> role=button name=~"generate"
      _RESULT_IMAGE       : first result image   -> the generation feed's first <img> with a
                            leonardo/cdn src (img[src*='cdn.leonardo']) — NOT the prompt-box or
                            reference thumbnails.

    When tuning: run `scripts/leonardo_generate.py "<prompt>"` headful, watch which _step()
    raises, open devtools on the live page, and correct the matching constant here.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from mimik_contracts import ImageBackend

from . import stealth_browser
from .base import ImageAdapter, ImageRequest, ImageResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from playwright.async_api import BrowserContext, Locator, Page


LEONARDO_URL = "https://app.leonardo.ai/"
_MODEL_LABEL = "leonardo-web"

# ⚠ GUESSED SELECTORS — see module docstring. Tune on first live run.
_LOGIN_MARKERS: tuple[str, ...] = ("login", "auth", "signin", "sign-in")
_PROMPT_PLACEHOLDER_RE = "prompt"  # matched case-insensitively against the textarea placeholder
_GENERATE_BUTTON_RE = "generate"  # matched case-insensitively against the button's accessible name
# Confirmed against the live UI (2026-07-20): generated outputs are served from
# cdn.leonardo.ai/users/<uid>/generations/<gen>/… — the '/generations/' path segment is what
# separates a real result from the site's static UI gradients (…/static/…auto_preset.webp).
_RESULT_IMAGE_CSS = "img[src*='/generations/']"

_NAV_TIMEOUT_MS = 60_000
_RESULT_TIMEOUT_MS = 180_000  # generation can take a while; give the first image up to 3 min

# Preferred path: ATTACH to a real Chrome the human launched + logged in on (passes Cloudflare
# Turnstile, which blocks a Playwright-*launched* browser). Set to "" to force a fresh launch.
_DEFAULT_CDP_URL = "http://localhost:9222"


class LeonardoBrowserAdapter(ImageAdapter):
    backend = ImageBackend.LEONARDO_BROWSER

    def __init__(self, *, artifacts_dir: Path = Path("artifacts"), profile_dir: str | None = None) -> None:
        self.artifacts_dir = artifacts_dir
        self.profile_dir = profile_dir or os.environ.get("LEONARDO_BROWSER_PROFILE_DIR") or "var/browser/leonardo"

    async def _acquire_session(self) -> "stealth_browser.StealthSession":
        """Attach to the human's already-logged-in Chrome (CDP) if one is running; otherwise
        launch a fresh hardened context. CDP is the reliable anti-Cloudflare path — the human
        cleared the "verify you are human" wall in their own real browser, and we just drive it.

        `stealth_browser` is referenced through the module so tests can monkeypatch its
        functions and never open a real browser.
        """
        cdp_url = os.environ.get("LEONARDO_CDP_URL", _DEFAULT_CDP_URL).strip()
        if cdp_url:
            try:
                return await stealth_browser.connect_cdp_session(cdp_url)
            except Exception:  # noqa: BLE001 - no debug Chrome running → fall back to a launch
                pass
        return await stealth_browser.launch_stealth_context(self.profile_dir, headless=False)

    @staticmethod
    async def _pick_page(context: "BrowserContext") -> "Page":
        """Prefer an already-open Leonardo tab (attached-Chrome case, where other tabs like
        ChatGPT must NOT be hijacked); otherwise open a fresh tab."""
        for page in context.pages:
            if "leonardo.ai" in (page.url or ""):
                return page
        return await context.new_page()

    async def generate(self, request: ImageRequest) -> ImageResult:
        session = await self._acquire_session()
        try:
            page = await self._pick_page(session.context)
            await self._open_tool(page)
            await self._assert_logged_in(page)
            await self._enter_prompt(page, request.prompt)
            await self._trigger_generate(page)
            image_bytes = await self._grab_first_result(page)
            path = self._save_png(image_bytes)
        finally:
            await session.aclose()

        return ImageResult(
            backend=self.backend,
            artifact_ref=str(path),
            prompt=request.prompt,
            model=_MODEL_LABEL,
        )

    # ---------- steps (each raises a clear, actionable error naming the failed step) ----------

    async def _open_tool(self, page: "Page") -> None:
        try:
            await page.goto(LEONARDO_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001 - re-raise with a step-named message
            raise RuntimeError(f"Leonardo step 'open tool' failed navigating to {LEONARDO_URL}: {exc}") from exc
        await stealth_browser.human_pause()

    async def _assert_logged_in(self, page: "Page") -> None:
        url = (page.url or "").lower()
        if any(marker in url for marker in _LOGIN_MARKERS):
            raise RuntimeError(
                "Leonardo session not logged in — run scripts/leonardo_login.py "
                f"(landed on {page.url!r})"
            )

    async def _enter_prompt(self, page: "Page", prompt: str) -> None:
        box = await self._locate_prompt_box(page)
        try:
            await stealth_browser.human_click(box)
            await stealth_browser.human_type(box, prompt)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Leonardo step 'enter prompt' failed typing into the prompt box: {exc}") from exc
        await stealth_browser.human_pause()

    async def _trigger_generate(self, page: "Page") -> None:
        button = page.get_by_role("button", name=self._ci(_GENERATE_BUTTON_RE))
        try:
            await button.first.wait_for(state="visible", timeout=_NAV_TIMEOUT_MS)
            await stealth_browser.human_click(button.first)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Leonardo step 'trigger generate' failed — could not find/click the Generate "
                f"button (guessed name~='{_GENERATE_BUTTON_RE}'): {exc}"
            ) from exc
        await stealth_browser.human_pause()

    async def _grab_first_result(self, page: "Page") -> bytes:
        image = page.locator(_RESULT_IMAGE_CSS).first
        try:
            await image.wait_for(state="visible", timeout=_RESULT_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Leonardo step 'grab first result' failed — no result image rendered within "
                f"{_RESULT_TIMEOUT_MS // 1000}s (guessed selector '{_RESULT_IMAGE_CSS}'): {exc}"
            ) from exc
        src = await image.get_attribute("src")
        if not src:
            raise RuntimeError("Leonardo step 'grab first result' failed — result image has no src")
        return await self._download(page, src)

    # ---------- helpers ----------

    async def _locate_prompt_box(self, page: "Page") -> "Locator":
        """Best-guess prompt box: placeholder containing 'prompt', else the first textbox."""
        by_placeholder = page.get_by_placeholder(self._ci(_PROMPT_PLACEHOLDER_RE))
        try:
            await by_placeholder.first.wait_for(state="visible", timeout=_NAV_TIMEOUT_MS)
            return by_placeholder.first
        except Exception:  # noqa: BLE001 - fall back to a generic textbox role
            fallback = page.get_by_role("textbox")
            try:
                await fallback.first.wait_for(state="visible", timeout=_NAV_TIMEOUT_MS)
                return fallback.first
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "Leonardo step 'enter prompt' failed — could not find the prompt box "
                    f"(guessed placeholder~='{_PROMPT_PLACEHOLDER_RE}' / role=textbox): {exc}"
                ) from exc

    async def _download(self, page: "Page", src: str) -> bytes:
        """Fetch the result image bytes. Reuses the page's authenticated session for the fetch."""
        try:
            response = await page.request.get(src)
            return await response.body()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Leonardo step 'download result' failed fetching {src!r}: {exc}") from exc

    def _save_png(self, image_bytes: bytes) -> Path:
        """Land the bytes under artifacts_dir as a PNG (mirrors router.write_image_artifact)."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifacts_dir / f"{self.backend.value}_{uuid.uuid4().hex}.png"
        path.write_bytes(image_bytes)
        return path

    @staticmethod
    def _ci(pattern: str):
        """A case-insensitive regex for Playwright name/placeholder matching."""
        import re

        return re.compile(pattern, re.IGNORECASE)
