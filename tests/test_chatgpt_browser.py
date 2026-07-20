"""ChatGPT browser adapter — driven entirely against a FAKE Playwright context.

NO real browser opens: `stealth_browser.launch_stealth_context` is monkeypatched to return a
stub session whose page exposes just the surface the adapter touches. We assert the happy path
types the image-directive-wrapped prompt, clicks send, saves a PNG, and returns a
CHATGPT_BROWSER ImageResult; and that a login-page landing raises the clear RuntimeError.
Mirrors test_leonardo_browser.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from creative.adapters import chatgpt_browser as gpt_mod
from creative.adapters import stealth_browser
from creative.adapters.base import ImageRequest, ImageResult
from creative.adapters.chatgpt_browser import ChatGPTBrowserAdapter
from mimik_contracts import ImageBackend

_PNG = b"\x89PNG\r\n\x1a\nfake-chatgpt-bytes"


@pytest.fixture(autouse=True)
def _no_cdp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the launch path (not CDP-attach) so the fake launcher is exercised — otherwise the
    adapter would make a real connect_over_cdp attempt to localhost:9222."""
    monkeypatch.setenv("CHATGPT_CDP_URL", "")


# ---------- fake Playwright surface ----------


class _FakeLocator:
    def __init__(self, *, src: str | None = None) -> None:
        self._src = src
        self.typed: list[str] = []
        self.clicked = 0

    @property
    def first(self) -> "_FakeLocator":
        return self

    @property
    def last(self) -> "_FakeLocator":
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

    def __init__(self, *, url: str = "https://chatgpt.com/") -> None:
        self.url = url
        self.request = _FakeRequest()
        self.prompt_box = _FakeLocator()
        self.send_button = _FakeLocator()
        self.result_image = _FakeLocator(
            src="https://files.oaiusercontent.com/result/xyz.png"
        )

    async def goto(self, url: str, *, wait_until: str = "", timeout: int = 0) -> None:
        return None

    def get_by_placeholder(self, pattern: object) -> _FakeLocator:
        return self.prompt_box

    def get_by_role(self, role: str, *, name: object = None) -> _FakeLocator:
        return self.send_button

    def locator(self, css: str) -> _FakeLocator:
        return self.result_image


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.pages = [page]
        self.closed = False

    async def new_page(self) -> _FakePage:
        return self._page

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


async def test_generate_types_directive_prompt_saves_png_and_returns_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _FakePage()
    session = _install_fake(monkeypatch, page)

    adapter = ChatGPTBrowserAdapter(artifacts_dir=tmp_path, profile_dir=str(tmp_path / "profile"))
    result = await adapter.generate(_request())

    # The composer received the image-DIRECTIVE-wrapped prompt (not the raw prompt), and send was clicked.
    expected = gpt_mod._IMAGE_DIRECTIVE.format(prompt="a serene minimalist clinic interior")
    assert page.prompt_box.typed == [expected]
    assert "a serene minimalist clinic interior" in page.prompt_box.typed[0]
    assert page.send_button.clicked == 1

    # Saved a PNG to artifacts_dir with the backend-prefixed name + canned bytes.
    assert isinstance(result, ImageResult)
    assert result.backend is ImageBackend.CHATGPT_BROWSER
    assert result.prompt == "a serene minimalist clinic interior"
    assert result.model == "chatgpt-web"
    artifact = Path(result.artifact_ref)
    assert artifact.parent == tmp_path
    assert artifact.name.startswith("chatgpt_browser_")
    assert artifact.suffix == ".png"
    assert artifact.read_bytes() == _PNG

    # Session was torn down.
    assert session.closed is True


async def test_login_page_landing_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = _FakePage(url="https://auth.openai.com/login")
    _install_fake(monkeypatch, page)

    adapter = ChatGPTBrowserAdapter(artifacts_dir=tmp_path)
    with pytest.raises(RuntimeError, match="not logged in"):
        await adapter.generate(_request())


async def test_profile_dir_defaults_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHATGPT_BROWSER_PROFILE_DIR", "/tmp/gpt-profile-xyz")
    adapter = ChatGPTBrowserAdapter()
    assert adapter.profile_dir == "/tmp/gpt-profile-xyz"


def test_backend_is_registered() -> None:
    from creative.adapters import get_adapter

    adapter = get_adapter(ImageBackend.CHATGPT_BROWSER)
    assert adapter.backend is ImageBackend.CHATGPT_BROWSER


def test_result_image_selector_targets_generation_output() -> None:
    # Generated images live on *.oaiusercontent.com; guard the distinguishing host segment.
    assert "oaiusercontent" in gpt_mod._RESULT_IMAGE_CSS
