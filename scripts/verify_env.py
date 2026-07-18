"""Verify the .env credentials are live — prints ONLY verdicts, never the secret values.

    uv run --no-sync python scripts/verify_env.py

Checks whatever is present: Gemini TEXT key, Supabase reachability. Safe to run anytime.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        print("! no .env found — copy .env.example to .env first")
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def check_gemini() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        print("· GEMINI_API_KEY: not set (skip)")
        return
    try:
        from creative.copy import generate_text

        out = generate_text("Reply with exactly: Mimik online").strip()
        print(f"✓ Gemini TEXT: OK — model replied {out[:40]!r}")
    except Exception as exc:  # noqa: BLE001 — report any failure verdict, don't crash
        print(f"✗ Gemini TEXT: FAILED — {type(exc).__name__}: {str(exc)[:120]}")


def check_supabase() -> None:
    url = os.environ.get("SUPABASE_URL")
    anon = os.environ.get("SUPABASE_ANON_KEY")
    if not url or not anon:
        print("· Supabase: URL/anon key not set (skip)")
        return
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/auth/v1/health", headers={"apikey": anon}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (operator-provided host)
            body = json.loads(resp.read())
        print(f"✓ Supabase: reachable — {body.get('name', 'auth')} healthy")
    except urllib.error.HTTPError as exc:
        print(f"✗ Supabase: HTTP {exc.code} — check URL/keys")
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Supabase: FAILED — {type(exc).__name__}: {str(exc)[:120]}")


if __name__ == "__main__":
    load_env()
    print("--- .env verification (no secrets printed) ---")
    check_gemini()
    check_supabase()
    for var in ("CHATGPT_BROWSER_PROFILE_DIR", "AISTUDIO_BROWSER_PROFILE_DIR"):
        val = os.environ.get(var)
        state = "set" if val and Path(val).exists() else ("set but path missing" if val else "not set")
        print(f"· {var}: {state}")
