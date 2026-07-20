"""Manual smoke test for the ChatGPT browser adapter — generate ONE image, print its path.

Runs ChatGPTBrowserAdapter against the operator's logged-in ChatGPT session. Preferred path:
ATTACH over CDP to the real debug Chrome (the same one the Leonardo harness uses — ChatGPT is
logged in there too), so Cloudflare/human-verification was already cleared by the actual person.

    START the debug Chrome + log into chatgpt.com in it (one time):
        uv run --no-sync python scripts/chrome_debug.py
    THEN generate:
        uv run --no-sync python scripts/chatgpt_generate.py "a serene minimalist clinic interior"

If no debug Chrome is listening on :9222, the adapter falls back to launching a hardened
persistent profile (CHATGPT_BROWSER_PROFILE_DIR, default var/browser/chatgpt) — log in there once.
Selectors are best-guesses (see chatgpt_browser.py's ⚠ block); on the first real run expect to
adjust them — the raised error names the step that failed.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

# Make the repo root importable when run as `python scripts/chatgpt_generate.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_dotenv() -> None:
    """Populate os.environ from the repo-root .env (real shell env wins). Tolerant loader,
    mirroring scripts/leonardo_generate.py — handles inline ` # comments` and surrounding quotes."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = re.sub(r"\s+#.*$", "", value.strip()).strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value


async def _run(prompt: str) -> int:
    from creative.adapters.base import ImageRequest
    from creative.adapters.chatgpt_browser import ChatGPTBrowserAdapter

    adapter = ChatGPTBrowserAdapter(artifacts_dir=Path("artifacts"))
    request = ImageRequest(prompt=prompt, width=1024, height=1024)
    print(f"Generating on ChatGPT (profile: {adapter.profile_dir}) …")
    try:
        result = await adapter.generate(request)
    except RuntimeError as exc:
        print(f"\n✗ {exc}", file=sys.stderr)
        return 1
    print(f"\n✓ saved: {result.artifact_ref}")
    print(f"  backend={result.backend.value} model={result.model}")
    return 0


def main() -> int:
    _load_dotenv()
    args = sys.argv[1:]
    if len(args) != 1 or not args[0].strip():
        print('usage: python scripts/chatgpt_generate.py "<prompt>"', file=sys.stderr)
        return 2
    return asyncio.run(_run(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
