"""Manual smoke test for the Leonardo browser adapter — generate ONE image, print its path.

Runs LeonardoBrowserAdapter headful against the logged-in burner Chromium profile, so you can
watch the flow and see exactly which step (and which guessed selector) needs tuning on the
live UI. No API key, no paid-spend gate — this is the subscription browser path.

    LOG IN FIRST (one time):
        uv run --no-sync python scripts/leonardo_login.py
    THEN generate:
        uv run --no-sync python scripts/leonardo_generate.py "a serene minimalist clinic interior"

If the session isn't logged in, the adapter raises a clear RuntimeError telling you to run
leonardo_login.py first. Selectors are best-guesses (see leonardo_browser.py's ⚠ block) — on
the first real run expect to adjust them; the error names the step that failed.

Reads .env for LEONARDO_BROWSER_PROFILE_DIR (default var/browser/leonardo).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

# Make the repo root importable when run as `python scripts/leonardo_generate.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_dotenv() -> None:
    """Populate os.environ from the repo-root .env (real shell env wins). Tolerant loader,
    mirroring scripts/drive_oauth.py — handles inline ` # comments` and surrounding quotes."""
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
    from creative.adapters.leonardo_browser import LeonardoBrowserAdapter

    adapter = LeonardoBrowserAdapter(artifacts_dir=Path("artifacts"))
    request = ImageRequest(prompt=prompt, width=1024, height=1024)
    print(f"Generating on Leonardo (profile: {adapter.profile_dir}) …")
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
        print('usage: python scripts/leonardo_generate.py "<prompt>"', file=sys.stderr)
        return 2
    return asyncio.run(_run(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
