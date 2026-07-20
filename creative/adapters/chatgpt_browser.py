"""ChatGPT image generation via browser automation (subscription path, no API cost).

Drives chatgpt.com on the operator's ChatGPT subscription through the SAME hardened-Playwright
stealth layer as the Leonardo backend: attach over CDP to a real logged-in Chrome (the anti-bot
path — a human cleared Cloudflare in their own browser), drive only the ChatGPT tab, human-pace
every action. No API key, no per-image spend. Fragility (UI drift, rate limits) is accepted for
the build phase and isolated behind this adapter, so swapping to the paid GPT-Image API later
stays a one-line config change (register a different class for ImageBackend.GPT_IMAGE).

⚠ SELECTORS — GUESSED, to be tuned against the live UI on first real run (same discipline as
    leonardo_browser). Each generation STEP is a small helper that raises a clear, actionable
    error naming the step that failed, so first-run tuning is one constant + a re-run:

      _LOGIN_MARKERS      : URL substrings meaning "not logged in" -> ("auth", "login", ...)
      _PROMPT_PLACEHOLDER : composer box -> placeholder ~"message|ask" (fallback role=textbox)
      _SEND_BUTTON_RE     : the send button -> role=button name ~"send"
      _RESULT_IMAGE_CSS   : the generated image -> <img> served from oaiusercontent (the DALL·E /
                            gpt-image output host) — the 'oaiusercontent' segment separates a real
                            result from avatars/UI icons.

    Tune by running scripts/chatgpt_generate.py "<prompt>" headful and watching which _step()
    raises (mirrors the leonardo tuning loop).

Model/tool selection (which image model the ChatGPT UI uses) is driven by whatever the attached
conversation is set to — a "pick model" UI-automation enhancement is deferred, exactly as it is
for Leonardo. The docs/ prompt-library PDFs are for prompt-quality R&D later, not this plumbing.
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


CHATGPT_URL = "https://chatgpt.com/"
_MODEL_LABEL = "chatgpt-web"
_DOMAIN_MARKERS: tuple[str, ...] = ("chatgpt.com", "chat.openai.com")

# ⚠ GUESSED SELECTORS — see module docstring. Tune on first live run.
_LOGIN_MARKERS: tuple[str, ...] = ("auth", "login", "signin", "sign-in")
_PROMPT_PLACEHOLDER_RE = "message|ask"  # "Message ChatGPT" / "Ask anything"
_SEND_BUTTON_RE = "send"  # role=button accessible name ~ "Send" / "Send prompt"
# Generated images are served from *.oaiusercontent.com (the DALL·E / gpt-image output host);
# that host segment separates a real result from avatars / UI icons on the page.
_RESULT_IMAGE_CSS = "img[src*='oaiusercontent']"

# Force a pure image response: no clarifying questions, no prose — just the image. Client copy is
# never fed here (this is a system-composed directive around the operator/team-supplied prompt).
_IMAGE_DIRECTIVE = (
    "Generate a single image from the description below. Return ONLY the image — do not ask "
    "any clarifying questions and do not add any text.\n\n{prompt}"
)

_NAV_TIMEOUT_MS = 60_000
_RESULT_TIMEOUT_MS = 180_000  # image generation can take a while; give the result up to 3 min

# Preferred path: ATTACH to the real Chrome the human launched + logged in on (same debug browser
# the Leonardo backend uses — ChatGPT is logged in there too). Set "" to force a fresh launch.
_DEFAULT_CDP_URL = "http://localhost:9222"


class ChatGPTBrowserAdapter(ImageAdapter):
    backend = ImageBackend.CHATGPT_BROWSER

    def __init__(
        self, *, artifacts_dir: Path = Path("artifacts"), profile_dir: str | None = None
    ) -> None:
        self.artifacts_dir = artifacts_dir
        self.profile_dir = (
            profile_dir or os.environ.get("CHATGPT_BROWSER_PROFILE_DIR") or "var/browser/chatgpt"
        )

    async def _acquire_session(self) -> "stealth_browser.StealthSession":
        """Attach to the human's already-logged-in Chrome (CDP) if one is running; otherwise
        launch a fresh hardened context. Referenced through the module so tests can monkeypatch
        stealth_browser and never open a real browser."""
        cdp_url = os.environ.get("CHATGPT_CDP_URL", _DEFAULT_CDP_URL).strip()
        if cdp_url:
            try:
                return await stealth_browser.connect_cdp_session(cdp_url)
            except Exception:  # noqa: BLE001 - no debug Chrome running → fall back to a launch
                pass
        return await stealth_browser.launch_stealth_context(self.profile_dir, headless=False)

    @staticmethod
    async def _pick_page(context: "BrowserContext") -> "Page":
        """Prefer an already-open ChatGPT tab (attached-Chrome case, where other tabs like the
        Leonardo generator must NOT be hijacked); otherwise open a fresh tab."""
        for page in context.pages:
            if any(marker in (page.url or "") for marker in _DOMAIN_MARKERS):
                return page
        return await context.new_page()

    async def generate(self, request: ImageRequest) -> ImageResult:
        session = await self._acquire_session()
        try:
            page = await self._pick_page(session.context)
            await self._open_tool(page)
            await self._assert_logged_in(page)
            await self._enter_prompt(page, request.prompt)
            await self._submit(page)
            image_bytes = await self._grab_result(page)
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
        # Already on a ChatGPT tab (the attached, logged-in conversation): don't navigate — a goto
        # would start a fresh chat and could drop a chosen model, mirroring the Leonardo behaviour.
        if any(marker in (page.url or "") for marker in _DOMAIN_MARKERS):
            return
        try:
            await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001 - re-raise with a step-named message
            raise RuntimeError(
                f"ChatGPT step 'open tool' failed navigating to {CHATGPT_URL}: {exc}"
            ) from exc
        await stealth_browser.human_pause()

    async def _assert_logged_in(self, page: "Page") -> None:
        url = (page.url or "").lower()
        if any(marker in url for marker in _LOGIN_MARKERS):
            raise RuntimeError(
                "ChatGPT session not logged in — log into chatgpt.com in the debug Chrome "
                f"(landed on {page.url!r})"
            )

    async def _enter_prompt(self, page: "Page", prompt: str) -> None:
        box = await self._locate_prompt_box(page)
        try:
            await stealth_browser.human_click(box)
            await stealth_browser.human_type(box, _IMAGE_DIRECTIVE.format(prompt=prompt))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"ChatGPT step 'enter prompt' failed typing into the composer: {exc}"
            ) from exc
        await stealth_browser.human_pause()

    async def _submit(self, page: "Page") -> None:
        button = page.get_by_role("button", name=self._ci(_SEND_BUTTON_RE))
        try:
            await button.first.wait_for(state="visible", timeout=_NAV_TIMEOUT_MS)
            await stealth_browser.human_click(button.first)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "ChatGPT step 'submit' failed — could not find/click the send button "
                f"(guessed name~='{_SEND_BUTTON_RE}'): {exc}"
            ) from exc
        await stealth_browser.human_pause()

    async def _grab_result(self, page: "Page") -> bytes:
        # The newest generated image is the LAST matching <img> in the conversation.
        image = page.locator(_RESULT_IMAGE_CSS).last
        try:
            await image.wait_for(state="visible", timeout=_RESULT_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "ChatGPT step 'grab result' failed — no generated image rendered within "
                f"{_RESULT_TIMEOUT_MS // 1000}s (guessed selector '{_RESULT_IMAGE_CSS}'): {exc}"
            ) from exc
        src = await image.get_attribute("src")
        if not src:
            raise RuntimeError("ChatGPT step 'grab result' failed — generated image has no src")
        return await self._download(page, src)

    # ---------- helpers ----------

    async def _locate_prompt_box(self, page: "Page") -> "Locator":
        """Best-guess composer: placeholder ~ 'message'/'ask', else the first textbox role."""
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
                    "ChatGPT step 'enter prompt' failed — could not find the composer "
                    f"(guessed placeholder~='{_PROMPT_PLACEHOLDER_RE}' / role=textbox): {exc}"
                ) from exc

    async def _download(self, page: "Page", src: str) -> bytes:
        """Fetch the result image bytes, reusing the page's authenticated session for the fetch."""
        try:
            response = await page.request.get(src)
            return await response.body()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"ChatGPT step 'download result' failed fetching {src!r}: {exc}"
            ) from exc

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
