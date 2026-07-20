"""Shared async stealth utilities for the browser-automation image adapters.

These wrap Playwright's persistent-context launch with the vanilla-Playwright hardening the
subscription image backends need (Leonardo, and any future web-app backend): drop the
`--enable-automation` flag, disable the `AutomationControlled` blink feature, and drive a
real installed Chrome channel when present. Human-pacing helpers add jittered pauses/typing
so the automation reads less like a bot.

Detection hardening (`_async_playwright`): we drive through **patchright** — a hardened
Playwright fork that suppresses the automation leaks vanilla Playwright emits *even in attach
mode*, notably the CDP `Runtime.enable` call anti-bot walls (Cloudflare Turnstile) fingerprint.
Falls back to vanilla Playwright if patchright is absent. Combined with attach-to-real-Chrome
(never launching a bot browser) + widened human pacing below, the automation reads as a
logged-in human using the web app — which is the whole point.
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


def _async_playwright():
    """Prefer `patchright` — a hardened Playwright fork that suppresses the automation leaks
    vanilla Playwright emits even in attach mode (notably the CDP `Runtime.enable` call that
    anti-bot walls like Cloudflare fingerprint). Falls back to vanilla Playwright if patchright
    is not installed. Same async API either way."""
    try:
        from patchright.async_api import async_playwright  # hardened
    except ImportError:  # pragma: no cover - patchright is a declared dep, fallback is a safety net
        from playwright.async_api import async_playwright
    return async_playwright()


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
    playwright = await _async_playwright().start()
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
    playwright = await _async_playwright().start()
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


async def human_pause(lo: float = 0.8, hi: float = 2.6) -> None:
    """Sleep a random human-ish beat in [lo, hi] seconds. Widened defaults: a real person
    doesn't act on sub-second machine cadence."""
    if lo < 0 or hi < lo:
        raise ValueError(f"human_pause bounds invalid: lo={lo}, hi={hi}")
    import asyncio

    await asyncio.sleep(random.uniform(lo, hi))


async def human_type(locator: "Locator", text: str) -> None:
    """Type `text` one character at a time with ~70-190ms per-char jitter (unhurried typing)."""
    delay_ms = random.uniform(70, 190)
    await locator.press_sequentially(text, delay=delay_ms)


async def human_click(locator: "Locator") -> None:
    """A short pre-pause, then a click — avoids the instant machine-click signature."""
    await human_pause(0.3, 0.9)
    await locator.click()


async def human_cooldown(lo: float = 8.0, hi: float = 22.0) -> None:
    """A longer between-actions cooldown (e.g. between generations). Volume + cadence is what
    trips bans over time, so callers should space repeated generations with this, not fire in
    bursts. The real volume cap belongs to the caller (per-session / per-client limits)."""
    if lo < 0 or hi < lo:
        raise ValueError(f"human_cooldown bounds invalid: lo={lo}, hi={hi}")
    import asyncio

    await asyncio.sleep(random.uniform(lo, hi))
