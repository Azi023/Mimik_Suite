"""Shared async stealth utilities for the browser-automation image adapters.

These wrap Playwright's persistent-context launch with the vanilla-Playwright hardening the
subscription image backends need (Leonardo, and any future web-app backend): drop the
`--enable-automation` flag, disable the `AutomationControlled` blink feature, and drive a
real installed Chrome channel when present. Human-pacing helpers add jittered pauses/typing
so the automation reads less like a bot.

For STRONGER evasion, swap Playwright for `patchright` — a drop-in Playwright replacement that
patches deeper automation fingerprints (CDP `Runtime.enable` leaks, etc.). It is deliberately
NOT added here: it would be an unprompted dependency, and the launcher args below are the
vanilla-Playwright hardening that ships with what we already have. Upgrade path when needed:
`import patchright.async_api as playwright` in place of `playwright.async_api` — same API.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from playwright.async_api import BrowserContext, Locator, Playwright


# Vanilla-Playwright anti-automation launch: use the REAL installed Chrome (not "Chrome for
# Testing") and drop the automation fingerprints web apps key on. Mirrors scripts/browser_login.py.
_LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]
_IGNORE_DEFAULT_ARGS = ["--enable-automation"]
_VIEWPORT = {"width": 1440, "height": 900}


@dataclass
class StealthSession:
    """A browser context plus its Playwright handle. The CALLER closes both:

        session = await launch_stealth_context(profile_dir)
        try:
            page = session.context.pages[0] or await session.context.new_page()
            ...
        finally:
            await session.aclose()

    `owns_context` is False for CDP-attached sessions (we connected to a browser the human
    launched) — aclose then leaves their window open and only detaches our Playwright handle.
    """

    playwright: "Playwright"
    context: "BrowserContext"
    owns_context: bool = True

    async def aclose(self) -> None:
        """Detach cleanly. Only close the context if WE launched it (never the human's window)."""
        if self.owns_context:
            try:
                await self.context.close()
            except Exception:  # noqa: BLE001 - teardown best-effort; nothing to recover
                pass
        await self.playwright.stop()


async def launch_stealth_context(profile_dir: str, *, headless: bool = False) -> StealthSession:
    """Launch a hardened persistent Chromium context bound to `profile_dir`.

    Prefers channel="chrome" (the real installed browser passes human-verification walls more
    often than bundled Chromium); falls back to bundled Chromium if Chrome is unavailable.
    Returns a `StealthSession`; the caller is responsible for `await session.aclose()`.
    """
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    last_error: Exception | None = None
    for channel in ("chrome", None):
        try:
            context = await playwright.chromium.launch_persistent_context(
                profile_dir,
                headless=headless,
                channel=channel,
                args=_LAUNCH_ARGS,
                ignore_default_args=_IGNORE_DEFAULT_ARGS,
                viewport=_VIEWPORT,
            )
            return StealthSession(playwright=playwright, context=context)
        except Exception as exc:  # noqa: BLE001 - fall through to bundled chromium
            last_error = exc
            continue
    await playwright.stop()
    raise RuntimeError(f"could not launch Chrome or bundled Chromium: {last_error}")


async def connect_cdp_session(cdp_url: str) -> StealthSession:
    """Attach to a REAL Chrome the human already launched (via scripts/chrome_debug.py) and
    logged in on. This is the reliable anti-Cloudflare path: Playwright never *launches* a
    detectable browser — it drives the human-verified session over the DevTools protocol, so
    Turnstile/"verify you are human" walls were already cleared by the actual person.

    `cdp_url` is the DevTools endpoint, e.g. http://localhost:9222. Uses the browser's existing
    context (the logged-in one) and marks the session non-owning so aclose leaves it open.
    Raises RuntimeError if nothing is listening (caller can fall back to a launch).
    """
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
    except Exception as exc:  # noqa: BLE001 - no debug Chrome running
        await playwright.stop()
        raise RuntimeError(f"could not attach to Chrome at {cdp_url}: {exc}") from exc
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    return StealthSession(playwright=playwright, context=context, owns_context=False)


# ---------- human-pacing helpers ----------
#
# `random` is used module-level and intentionally NOT seeded — this is app pacing, not
# anything that needs reproducibility or cryptographic strength. Bounds are asserted so a
# swapped (lo, hi) can't silently invert the delay.


async def human_pause(lo: float = 0.4, hi: float = 1.6) -> None:
    """Sleep a random human-ish beat in [lo, hi] seconds."""
    if lo < 0 or hi < lo:
        raise ValueError(f"human_pause bounds invalid: lo={lo}, hi={hi}")
    import asyncio

    await asyncio.sleep(random.uniform(lo, hi))


async def human_type(locator: "Locator", text: str) -> None:
    """Type `text` into `locator` one character at a time with ~40-140ms per-char jitter."""
    delay_ms = random.uniform(40, 140)
    await locator.press_sequentially(text, delay=delay_ms)


async def human_click(locator: "Locator") -> None:
    """A tiny pre-pause, then a click — avoids the instant machine-click signature."""
    await human_pause(0.15, 0.5)
    await locator.click()
