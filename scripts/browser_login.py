"""One-time browser login for the image adapters.

The image backends drive your PRO ChatGPT / Google AI-Studio through a LOGGED-IN Playwright
profile. Run this ONCE per site: it opens a real browser window using a persistent profile
directory; you log in by hand; close it. Automation then reuses that profile — no passwords
are ever stored.

    uv run --no-sync python scripts/browser_login.py chatgpt
    uv run --no-sync python scripts/browser_login.py aistudio

Then paste the printed path into .env (CHATGPT_BROWSER_PROFILE_DIR / AISTUDIO_BROWSER_PROFILE_DIR).
"""

from __future__ import annotations

import sys
from pathlib import Path

SITES = {
    "chatgpt": ("https://chatgpt.com", "CHATGPT_BROWSER_PROFILE_DIR"),
    "aistudio": ("https://aistudio.google.com", "AISTUDIO_BROWSER_PROFILE_DIR"),
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in SITES:
        print("usage: python scripts/browser_login.py [chatgpt|aistudio]")
        return 2
    site = sys.argv[1]
    url, env_var = SITES[site]
    profile_dir = Path.home() / ".mimik" / "browser-profiles" / site
    profile_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile_dir), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded")
        print(f"\nA browser opened at {url}.")
        print("Log in fully (finish any 2FA), then return here.")
        input("Press Enter once you're logged in — this saves the session and closes the browser... ")
        ctx.close()
    print(f"\n✓ Saved. Add this line to your .env:\n{env_var}={profile_dir}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
