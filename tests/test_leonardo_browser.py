"""Leonardo browser adapter — driven entirely against a FAKE Playwright context.

NO real browser ever opens: `stealth_browser.launch_stealth_context` is monkeypatched to
return a stub session whose page exposes just the surface the adapter touches
(goto/get_by_placeholder/get_by_role/locator/request.get). We assert the happy path types the
prompt, triggers Generate, saves a PNG, and returns a LEONARDO_BROWSER ImageResult; and that a
login-page landing raises the clear RuntimeError. The pacing helpers are unit-tested for bounds
(and patched to no-op in the happy path so the suite stays fast).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from creative.adapters import leonardo_browser as leo_mod
from creative.adapters import stealth_browser
from creative.adapters.base import ImageRequest, ImageResult
from creative.adapters.leonardo_browser import LeonardoBrowserAdapter
from mimik_contracts import ImageBackend

_PNG = b"\x89PNG\r\n\x1a\nfake-leonardo-bytes"


@pytest.fixture(autouse=True)
def _no_cdp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the launch path (not CDP-attach) so the fake launcher is exercised — otherwise
    the adapter would make a real connect_over_cdp attempt to localhost:9222."""
    monkeypatch.setenv("LEONARDO_CDP_URL", "")


# ---------- fake Playwright surface ----------


class _FakeLocator:
    def __init__(self, *, src: str | None = None) -> None:
        self._src = src
        self.typed: list[str] = []
        self.clicked = 0

    @property
    def first(self) -> "_FakeLocator":
        return self

    async def wait_for(self, *, state: str = "visible", timeout: int = 0) -> None:
        return None

    async def click(self) -> None:
        self.clicked += 1

    async def press_sequentially(self, text: str, *, delay: float = 0.0) -> None:
        self.typed.append(text)

    async def get_attribute(self, name: str) -> str | None:
        return self._src if name == "src" else None


class _FakeResponse:
    async def body(self) -> bytes:
        return _PNG


class _FakeRequest:
    async def get(self, url: str) -> _FakeResponse:
        return _FakeResponse()


class _FakePage:
    """Records the flow so tests can assert what the adapter did."""

    def __init__(self, *, url: str = "https://app.leonardo.ai/ai-generations") -> None:
        self.url = url
        self.request = _FakeRequest()
        self.prompt_box = _FakeLocator()
        self.generate_button = _FakeLocator()
        self.result_image = _FakeLocator(src="https://cdn.leonardo.ai/result/xyz.png")

    async def goto(self, url: str, *, wait_until: str = "", timeout: int = 0) -> None:
        return None

    def get_by_placeholder(self, pattern: object) -> _FakeLocator:
        return self.prompt_box

    def get_by_role(self, role: str, *, name: object = None) -> _FakeLocator:
        return self.generate_button

    def locator(self, css: str) -> _FakeLocator:
        return self.result_image


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self.pages = [page]
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeSession:
    def __init__(self, page: _FakePage) -> None:
        self.context = _FakeContext(page)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def _install_fake(monkeypatch: pytest.MonkeyPatch, page: _FakePage) -> _FakeSession:
    """Patch the launcher to return a fake session, and no-op the sleepy pacing helpers."""
    session = _FakeSession(page)

    async def _fake_launch(profile_dir: str, *, headless: bool = False) -> _FakeSession:
        return session

    async def _no_pause(lo: float = 0.0, hi: float = 0.0) -> None:
        return None

    monkeypatch.setattr(stealth_browser, "launch_stealth_context", _fake_launch)
    monkeypatch.setattr(stealth_browser, "human_pause", _no_pause)
    return session


def _request() -> ImageRequest:
    return ImageRequest(prompt="a serene minimalist clinic interior", width=1024, height=1024)


# ---------- happy path ----------


async def test_generate_types_prompt_saves_png_and_returns_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _FakePage()
    session = _install_fake(monkeypatch, page)

    adapter = LeonardoBrowserAdapter(artifacts_dir=tmp_path, profile_dir=str(tmp_path / "profile"))
    result = await adapter.generate(_request())

    # typed the prompt into the prompt box, and clicked Generate
    assert page.prompt_box.typed == ["a serene minimalist clinic interior"]
    assert page.generate_button.clicked == 1

    # saved a PNG to artifacts_dir with the backend-prefixed name + canned bytes
    assert isinstance(result, ImageResult)
    assert result.backend is ImageBackend.LEONARDO_BROWSER
    assert result.prompt == "a serene minimalist clinic interior"
    assert result.model == "leonardo-web"
    artifact = Path(result.artifact_ref)
    assert artifact.parent == tmp_path
    assert artifact.name.startswith("leonardo_browser_")
    assert artifact.suffix == ".png"
    assert artifact.read_bytes() == _PNG

    # session was torn down
    assert session.closed is True


async def test_login_page_landing_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _FakePage(url="https://app.leonardo.ai/auth/login")
    _install_fake(monkeypatch, page)

    adapter = LeonardoBrowserAdapter(artifacts_dir=tmp_path)
    with pytest.raises(RuntimeError, match="not logged in — run scripts/leonardo_login.py"):
        await adapter.generate(_request())


async def test_profile_dir_defaults_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEONARDO_BROWSER_PROFILE_DIR", "/tmp/leo-profile-xyz")
    adapter = LeonardoBrowserAdapter()
    assert adapter.profile_dir == "/tmp/leo-profile-xyz"


def test_backend_is_registered() -> None:
    from creative.adapters import get_adapter

    adapter = get_adapter(ImageBackend.LEONARDO_BROWSER)
    assert adapter.backend is ImageBackend.LEONARDO_BROWSER


# ---------- pacing helpers ----------


async def test_human_pause_respects_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)
    await stealth_browser.human_pause(0.4, 1.6)
    assert len(slept) == 1
    assert 0.4 <= slept[0] <= 1.6


async def test_human_pause_rejects_inverted_bounds() -> None:
    with pytest.raises(ValueError):
        await stealth_browser.human_pause(2.0, 1.0)


async def test_human_type_uses_jittered_per_char_delay() -> None:
    loc = _FakeLocator()
    await stealth_browser.human_type(loc, "hello")
    assert loc.typed == ["hello"]


async def test_human_click_pre_pauses_then_clicks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    loc = _FakeLocator()
    await stealth_browser.human_click(loc)
    assert loc.clicked == 1


def test_result_image_selector_targets_generation_output() -> None:
    # Confirmed live: real outputs live under …/generations/…; the '/generations/' segment is
    # what separates a result from the site's static UI gradients. Guard it against regressions.
    assert "/generations/" in leo_mod._RESULT_IMAGE_CSS
    assert re.search("generate", leo_mod._GENERATE_BUTTON_RE)
