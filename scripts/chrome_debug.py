"""Launch your REAL Chrome with a DevTools debug port, so the harness can ATTACH to it.

Why: Playwright *launching* a browser ("Chrome for Testing" + automation flags) trips
Cloudflare Turnstile ("verify you are human"). The reliable fix is the opposite — YOU launch
a normal Chrome, log in like a human (Turnstile passes because you really are one), and the
harness attaches over the DevTools protocol and drives your logged-in session. No bot browser
is ever launched.

    uv run --no-sync python scripts/chrome_debug.py          # launches Chrome on port 9222

Then, in that Chrome window: log into Leonardo (solve the Cloudflare checkbox), and LEAVE THE
WINDOW OPEN. In another terminal:

    uv run --no-sync python scripts/leonardo_generate.py "your prompt"

The adapter reads LEONARDO_CDP_URL (default http://localhost:9222) and attaches.

Notes:
- Uses a DEDICATED profile dir (var/browser/leonardo-chrome). Chrome (v136+) disables the
  debug port on your *default* profile for security, so a separate --user-data-dir is required
  and keeps this fully isolated from your everyday Chrome.
- If Cloudflare still blocks with the debug port on, log in ONCE in the same profile WITHOUT
  the port (plain `open -a "Google Chrome" --args --user-data-dir=<that dir>`), then re-run this
  — the saved session skips the login wall entirely.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PORT = 9222
_PROFILE = Path("var/browser/leonardo-chrome").resolve()
_START_URL = "https://app.leonardo.ai/"
_BUNDLE_ID = "com.google.Chrome"

# Direct-binary fallbacks if the bundle-id launch is unavailable (Linux / odd installs).
_CHROME_CANDIDATES = [
    str(Path.home() / "Desktop" / "Google Chrome.app/Contents/MacOS/Google Chrome"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/opt/google/chrome/chrome",
]

_CHROME_FLAGS = [
    f"--remote-debugging-port={_PORT}",
    f"--user-data-dir={_PROFILE}",
    "--no-first-run",
    "--no-default-browser-check",
    _START_URL,
]


def _launch() -> bool:
    """Launch a fresh, real Chrome instance with the debug port. Prefer `open -b <bundle>`
    (finds Chrome wherever it's installed — Desktop, /Applications, anywhere); fall back to a
    direct binary. Returns True if a launch was issued."""
    # macOS: bundle-id launch is install-location-independent.
    try:
        rc = subprocess.run(  # noqa: S603,S607 - fixed args, our own flags
            ["open", "-n", "-b", _BUNDLE_ID, "--args", *_CHROME_FLAGS],
            capture_output=True,
            timeout=20,
        )
        if rc.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    for path in _CHROME_CANDIDATES:
        if Path(path).exists():
            subprocess.Popen([path, *_CHROME_FLAGS])  # noqa: S603 - fixed local Chrome binary
            return True
    return False


def main() -> int:
    _PROFILE.mkdir(parents=True, exist_ok=True)
    if not _launch():
        print(
            "Could not find Google Chrome. Launch it manually:\n"
            f'  open -n -b {_BUNDLE_ID} --args --remote-debugging-port={_PORT} '
            f'--user-data-dir="{_PROFILE}" {_START_URL}',
            file=sys.stderr,
        )
        return 2
    print(
        f"✓ Chrome launched on debug port {_PORT} (profile: {_PROFILE}).\n"
        f"  1. In that window, log into Leonardo (solve the Cloudflare checkbox).\n"
        f"  2. LEAVE THE WINDOW OPEN.\n"
        f"  3. Run:  uv run --no-sync python scripts/leonardo_generate.py \"your prompt\"\n"
        f"     (the adapter attaches via LEONARDO_CDP_URL=http://localhost:{_PORT})\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
