"""One-time browser login for the image adapters.

The image backends drive your PRO ChatGPT / Google AI-Studio through a LOGGED-IN Playwright
profile. Run this ONCE per site: a real browser window opens; you log in by hand; then you
just CLOSE the window and the session is saved. Automation reuses that profile afterward —
no passwords are ever stored.

    uv run --no-sync python scripts/browser_login.py chatgpt
    uv run --no-sync python scripts/browser_login.py aistudio
    uv run --no-sync python scripts/browser_login.py --verify   # headless self-test, no login

Then paste the printed path into .env (CHATGPT_BROWSER_PROFILE_DIR / AISTUDIO_BROWSER_PROFILE_DIR).

Note: it waits for you to CLOSE THE WINDOW (not for a keypress), so it works fine when run
through Claude Code's `!` shell, which has no interactive stdin.
"""

from __future__ import annotations

import sys
from pathlib import Path

SITES = {
    "chatgpt": ("https://chatgpt.com", "CHATGPT_BROWSER_PROFILE_DIR"),
    "aistudio": ("https://aistudio.google.com", "AISTUDIO_BROWSER_PROFILE_DIR"),
}

_WAIT_MS = 20 * 60 * 1000  # give the operator up to 20 min to log in + close the window

# Anti-automation launch: use the REAL installed Chrome (not "Chrome for Testing") and drop the
# automation fingerprints Cloudflare keys on. This gives the best chance of passing a human
# verification during an interactive login; aggressive walls (OpenAI) may still loop.
_ARGS = ["--disable-blink-features=AutomationControlled"]
_IGNORE = ["--enable-automation"]


def _profile_dir(site: str) -> Path:
    d = Path.home() / ".mimik" / "browser-profiles" / site
    d.mkdir(parents=True, exist_ok=True)
    return d


def _launch(p, profile_dir: Path, *, headless: bool):
    """Launch a persistent context, preferring the real Chrome channel; fall back to bundled."""
    try:
        return p.chromium.launch_persistent_context(
            str(profile_dir), channel="chrome", headless=headless, args=_ARGS, ignore_default_args=_IGNORE
        )
    except Exception:
        return p.chromium.launch_persistent_context(
            str(profile_dir), headless=headless, args=_ARGS, ignore_default_args=_IGNORE
        )


def verify() -> int:
    """Headless self-test: proves Playwright + persistent context work. No login."""
    from playwright.sync_api import sync_playwright

    d = _profile_dir("_verify")
    with sync_playwright() as p:
        ctx = _launch(p, d, headless=True)
        ctx.new_page().goto("about:blank")
        ctx.close()
    print("✓ browser automation works (persistent context OK)")
    return 0


def login(site: str) -> int:
    url, env_var = SITES[site]
    d = _profile_dir(site)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = _launch(p, d, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded")
        print(f"\nA browser opened at {url}.")
        print("→ Log in fully (finish any 2FA), then CLOSE the browser window to finish.")
        print("  (waiting up to 20 min for you to close it…)")
        try:
            ctx.wait_for_event("close", timeout=_WAIT_MS)
        except Exception:
            pass  # timed out, or already closed — cookies are persisted to disk regardless
        try:
            ctx.close()
        except Exception:
            pass
    print(f"\n✓ Session saved. Add this to your .env:\n{env_var}={d}\n")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args == ["--verify"]:
        return verify()
    if len(args) == 1 and args[0] in SITES:
        return login(args[0])
    print("usage: python scripts/browser_login.py [chatgpt|aistudio|--verify]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
