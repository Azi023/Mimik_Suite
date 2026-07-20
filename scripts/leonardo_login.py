"""One-time (headed) login bootstrap for the Leonardo.ai browser session.

Run it, sign in ONCE in the window that opens (use the mimikcreations Google account —
tick "remember me"), then close the window. The session lands in a persistent Chromium
profile that later automation reuses headlessly — same pattern as the ChatGPT/AI-Studio
browser adapters. No credentials ever touch this repo; the profile dir is gitignored.

    uv run --no-sync python scripts/leonardo_login.py           # opens the login window
    uv run --no-sync python scripts/leonardo_login.py --check   # verifies the saved session

Notes:
- Uses channel="chrome" (real Chrome) when available: Google sign-in blocks plain
  automated Chromium more often than branded Chrome.
- LEONARDO_BROWSER_PROFILE_DIR overrides the profile location (default var/browser/leonardo).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

LEONARDO_URL = "https://app.leonardo.ai/"


def profile_dir() -> Path:
    root = os.environ.get("LEONARDO_BROWSER_PROFILE_DIR") or "var/browser/leonardo"
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _launch(headless: bool):
    from playwright.async_api import async_playwright

    p = await async_playwright().start()
    for channel in ("chrome", None):
        try:
            ctx = await p.chromium.launch_persistent_context(
                str(profile_dir()),
                headless=headless,
                channel=channel,
                viewport={"width": 1440, "height": 900},
            )
            return p, ctx
        except Exception:  # noqa: BLE001 — fall through to plain chromium
            continue
    raise RuntimeError("could not launch Chrome or Chromium")


async def login() -> None:
    p, ctx = await _launch(headless=False)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    # Leonardo is a heavy SPA — the full "load" event can exceed 30s. Wait only for
    # domcontentloaded (fires early) and never let a slow load abort the login: the
    # window is open and usable regardless.
    try:
        await page.goto(LEONARDO_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:  # noqa: BLE001 — page kept loading; you can still log in
        print(f"(page still finishing load — that's fine, just log in: {exc})")
    print("Sign in to Leonardo in the window (Google or email), then CLOSE the window.")
    try:
        await ctx.wait_for_event("close", timeout=15 * 60 * 1000)
    except Exception:  # noqa: BLE001 — operator closed it / timeout: either way we're done
        pass
    finally:
        try:
            await ctx.close()
        except Exception:  # noqa: BLE001
            pass
        await p.stop()
    print(f"Session saved to {profile_dir()}")


async def check() -> None:
    p, ctx = await _launch(headless=True)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto(LEONARDO_URL, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(6_000)
    url = page.url
    logged_in = "login" not in url and "auth" not in url
    print(f"landed on: {url}")
    print("session: LOGGED IN" if logged_in else "session: NOT logged in — run without --check first")
    await ctx.close()
    await p.stop()


if __name__ == "__main__":
    asyncio.run(check() if "--check" in sys.argv else login())
