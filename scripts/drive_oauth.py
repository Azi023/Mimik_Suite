"""One-time Google Drive OAuth consent → a refresh token for the archive backend.

The service-account archive can't upload into a My-Drive folder ("Service Accounts do not
have storage quota"). The fix Google itself points to is OAuth delegation: you authorize
ONCE, and archived files are then owned by YOU and use your Drive quota. This helper runs
that consent and prints the refresh token to paste into .env.

Prerequisites (Google Cloud console, project with the Drive API enabled):
  1. OAuth consent screen configured; PUBLISH it (Production) so the refresh token does not
     expire after 7 days (Testing mode expires external-app refresh tokens weekly).
  2. Create an OAuth 2.0 Client ID (Desktop app OR Web app). If Web app, register the
     redirect URI  http://localhost:8765  on it. (Desktop clients allow loopback already.)
  3. Export the client id + secret, then run this from the REPO ROOT:

     GOOGLE_OAUTH_CLIENT_ID=... GOOGLE_OAUTH_CLIENT_SECRET=... \
       uv run --no-sync python scripts/drive_oauth.py

  (or set them in .env first — this reads the environment). A browser opens; click Allow
  (bypass the "unverified app" warning — it's your own app). The script prints:
     GOOGLE_OAUTH_REFRESH_TOKEN=...
  Paste that into .env alongside ARCHIVE_BACKEND=google_drive_oauth and DRIVE_ROOT_FOLDER_ID.

Stdlib only; no secrets are printed except the refresh token you asked for (never the
client secret).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def _load_dotenv() -> None:
    """Populate os.environ from the repo-root .env (real shell env wins, as usual).

    The app reads .env via pydantic-settings, but a standalone script only sees os.environ —
    so load .env here too. Tolerant of inline ` # comments` and surrounding quotes.
    """
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = re.sub(r"\s+#.*$", "", value.strip()).strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value

_PORT = 8765
_REDIRECT_URI = f"http://localhost:{_PORT}"
_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
# drive.file = least privilege: the app only ever sees files IT creates (the archives).
_SCOPE = "https://www.googleapis.com/auth/drive.file"

_captured: dict[str, str] = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        code = params.get("code", [""])[0]
        error = params.get("error", [""])[0]
        if code:
            _captured["code"] = code
            message = "Authorized. You can close this tab and return to the terminal."
        else:
            _captured["error"] = error or "no code returned"
            message = f"Authorization failed: {_captured['error']}. Close this tab."
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body><h3>{message}</h3></body></html>".encode())

    def log_message(self, *_args: object) -> None:  # silence the default request logging
        pass


def _exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": _REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode()
    req = urllib.request.Request(
        _TOKEN_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed google host)
        return json.loads(resp.read())


def main() -> int:
    _load_dotenv()
    client_id = (os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        print(
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET first "
            "(env or .env). See the module docstring.",
            file=sys.stderr,
        )
        return 2

    auth_url = f"{_AUTH_ENDPOINT}?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": _REDIRECT_URI,
            "response_type": "code",
            "scope": _SCOPE,
            "access_type": "offline",  # ask for a refresh token
            "prompt": "consent",  # force a refresh token even on re-consent
        }
    )

    server = HTTPServer(("localhost", _PORT), _CallbackHandler)
    print(f"\nOpening the consent page (also copy it manually if no window appears):\n{auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:  # noqa: BLE001 — headless/no-browser: the printed URL is the fallback
        pass
    print(f"Waiting for the OAuth redirect on {_REDIRECT_URI} …  (Ctrl-C to abort)")
    try:
        while "code" not in _captured and "error" not in _captured:
            server.handle_request()
    finally:
        server.server_close()

    if "error" in _captured:
        print(f"\nAuthorization failed: {_captured['error']}", file=sys.stderr)
        return 1

    tokens = _exchange_code(client_id, client_secret, _captured["code"])
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print(
            "\nNo refresh_token returned. This usually means consent was already granted "
            "without prompt=consent, or the app is in Testing mode. Revoke the app's access "
            "at https://myaccount.google.com/permissions and run this again.",
            file=sys.stderr,
        )
        return 1

    print("\n✓ Success. Add these to your .env:\n")
    print("ARCHIVE_BACKEND=google_drive_oauth")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={refresh_token}")
    print("(GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / DRIVE_ROOT_FOLDER_ID too)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
