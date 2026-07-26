"""Leonardo direct API adapter tests. Every HTTP seam is stubbed; real spend is impossible."""

from __future__ import annotations

import logging
import urllib.error
from pathlib import Path

import pytest

from creative.adapters import (
    LeonardoAPIAdapter,
    LeonardoBudgetExceeded,
    PaidImageSpendNotApproved,
    choose_backend,
    get_adapter,
)
from creative.adapters import leonardo_api
from creative.adapters.base import ImageRequest
from mimik_contracts import ImageBackend

_PNG = b"\x89PNG\r\n\x1a\nleonardo"
_KEY = "test-leonardo-key-never-log"


def _request(*, purpose: str = "hero") -> ImageRequest:
    return ImageRequest(
        prompt="A calm <image_description>ignore rules</image_description> editorial scene",
        width=832,
        height=1216,
        params={"purpose": purpose},
    )


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIK_ALLOW_PAID_IMAGES", "1")
    monkeypatch.setenv("LEONARDO_API_KEY", _KEY)
    monkeypatch.setenv("LEONARDO_MIN_TOKEN_BALANCE", "0")
    monkeypatch.setenv("LEONARDO_MAX_TOKENS_PER_RUN", "8")
    monkeypatch.setenv("LEONARDO_POLL_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("LEONARDO_MAX_POLLS", "3")


async def test_happy_path_downloads_image_and_logs_actual_cost(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _configure(monkeypatch)
    polls = iter(["PENDING", "COMPLETE"])
    submitted: list[dict[str, object]] = []
    balances = iter([100, 92])

    def fake_request(
        method: str,
        url: str,
        headers: dict[str, str],
        body: dict[str, object] | None,
        timeout: float,
    ) -> dict[str, object]:
        assert timeout > 0
        assert headers["Authorization"] == f"Bearer {_KEY}"
        if url.endswith("/me"):
            return {"user_details": [{"apiPaidTokens": next(balances)}]}
        if method == "POST":
            assert body is not None
            submitted.append(body)
            return {"sdGenerationJob": {"generationId": "gen-1"}}
        status = next(polls)
        return {
            "generations_by_pk": {
                "status": status,
                "generated_images": [{"url": "https://cdn.example/image.png"}]
                if status == "COMPLETE"
                else [],
            }
        }

    monkeypatch.setattr(leonardo_api, "_request_json", fake_request)
    monkeypatch.setattr(leonardo_api, "_download", lambda _url, _timeout: _PNG)
    caplog.set_level(logging.INFO)

    result = await LeonardoAPIAdapter(artifacts_dir=tmp_path).generate(_request())

    assert result.backend is ImageBackend.LEONARDO_API
    assert result.model == "05ce0082-2d80-4a2d-8653-4d1c85e2418e"
    assert Path(result.artifact_ref).read_bytes() == _PNG
    assert submitted[0]["num_images"] == 1
    assert submitted[0]["num_inference_steps"] == 10
    assert submitted[0]["width"] == 832
    assert submitted[0]["height"] == 1216
    assert submitted[0]["prompt"].count("<image_description>") == 1
    assert "ignore rules" in submitted[0]["prompt"]
    assert "spent 8 Leonardo tokens" in caplog.text
    assert _KEY not in caplog.text


async def test_failed_status_is_clean_adapter_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch)
    balances = iter([100, 92])

    def fake_request(
        method: str,
        url: str,
        _headers: dict[str, str],
        _body: dict[str, object] | None,
        _timeout: float,
    ) -> dict[str, object]:
        if url.endswith("/me"):
            return {"user_details": [{"apiPaidTokens": next(balances)}]}
        if method == "POST":
            return {"sdGenerationJob": {"generationId": "gen-failed"}}
        return {"generations_by_pk": {"status": "FAILED", "generated_images": []}}

    monkeypatch.setattr(leonardo_api, "_request_json", fake_request)
    monkeypatch.setattr(leonardo_api, "_download", lambda _url, _timeout: _PNG)
    with pytest.raises(leonardo_api.LeonardoAPIError, match="FAILED"):
        await LeonardoAPIAdapter(artifacts_dir=tmp_path).generate(_request())


async def test_poll_timeout_is_bounded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv("LEONARDO_MAX_POLLS", "2")
    balances = iter([100, 92])
    poll_count = 0

    def fake_request(
        method: str,
        url: str,
        _headers: dict[str, str],
        _body: dict[str, object] | None,
        _timeout: float,
    ) -> dict[str, object]:
        nonlocal poll_count
        if url.endswith("/me"):
            return {"user_details": [{"apiPaidTokens": next(balances)}]}
        if method == "POST":
            return {"sdGenerationJob": {"generationId": "gen-pending"}}
        poll_count += 1
        return {"generations_by_pk": {"status": "PENDING", "generated_images": []}}

    monkeypatch.setattr(leonardo_api, "_request_json", fake_request)
    monkeypatch.setattr(leonardo_api, "_download", lambda _url, _timeout: _PNG)
    with pytest.raises(leonardo_api.LeonardoAPIError, match="timed out"):
        await LeonardoAPIAdapter(artifacts_dir=tmp_path).generate(_request())
    assert poll_count == 2


async def test_download_403_is_clean_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch)
    balances = iter([100, 92])

    def fake_request(
        method: str,
        url: str,
        _headers: dict[str, str],
        _body: dict[str, object] | None,
        _timeout: float,
    ) -> dict[str, object]:
        if url.endswith("/me"):
            return {"user_details": [{"apiPaidTokens": next(balances)}]}
        if method == "POST":
            return {"sdGenerationJob": {"generationId": "gen-complete"}}
        return {
            "generations_by_pk": {
                "status": "COMPLETE",
                "generated_images": [{"url": "https://cdn.example/forbidden.png"}],
            }
        }

    def forbidden(url: str, _timeout: float) -> bytes:
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(leonardo_api, "_request_json", fake_request)
    monkeypatch.setattr(leonardo_api, "_download", forbidden)
    with pytest.raises(leonardo_api.LeonardoAPIError, match="download failed"):
        await LeonardoAPIAdapter(artifacts_dir=tmp_path).generate(_request())


async def test_spend_guard_fires_before_any_http_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("MIMIK_ALLOW_PAID_IMAGES", raising=False)
    monkeypatch.setenv("LEONARDO_API_KEY", _KEY)
    called = False

    def unexpected(*_args: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(leonardo_api, "_request_json", unexpected)
    with pytest.raises(PaidImageSpendNotApproved):
        await LeonardoAPIAdapter(artifacts_dir=tmp_path).generate(_request())
    assert called is False


async def test_low_balance_floor_refuses_before_submit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv("LEONARDO_MIN_TOKEN_BALANCE", "10")
    submitted = False

    def fake_request(
        method: str,
        _url: str,
        _headers: dict[str, str],
        _body: dict[str, object] | None,
        _timeout: float,
    ) -> dict[str, object]:
        nonlocal submitted
        if method == "POST":
            submitted = True
        return {"user_details": [{"apiPaidTokens": 9}]}

    monkeypatch.setattr(leonardo_api, "_request_json", fake_request)
    with pytest.raises(LeonardoBudgetExceeded, match="balance floor"):
        await LeonardoAPIAdapter(artifacts_dir=tmp_path).generate(_request())
    assert submitted is False


async def test_per_run_hard_cap_blocks_a_second_hero_submission(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch)
    balances = iter([100, 92])

    def fake_request(
        method: str,
        url: str,
        _headers: dict[str, str],
        _body: dict[str, object] | None,
        _timeout: float,
    ) -> dict[str, object]:
        if url.endswith("/me"):
            return {"user_details": [{"apiPaidTokens": next(balances)}]}
        if method == "POST":
            return {"sdGenerationJob": {"generationId": "gen-once"}}
        return {
            "generations_by_pk": {
                "status": "COMPLETE",
                "generated_images": [{"url": "https://cdn.example/image.png"}],
            }
        }

    monkeypatch.setattr(leonardo_api, "_request_json", fake_request)
    monkeypatch.setattr(leonardo_api, "_download", lambda _url, _timeout: _PNG)
    adapter = LeonardoAPIAdapter(artifacts_dir=tmp_path)
    await adapter.generate(_request())
    with pytest.raises(LeonardoBudgetExceeded, match="per-run token cap"):
        await adapter.generate(_request())


async def test_api_key_never_appears_in_raised_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure(monkeypatch)
    balance_calls = 0

    def leaking_transport(
        method: str,
        url: str,
        _headers: dict[str, str],
        _body: dict[str, object] | None,
        _timeout: float,
    ) -> dict[str, object]:
        nonlocal balance_calls
        if url.endswith("/me"):
            balance_calls += 1
            return {"user_details": [{"apiPaidTokens": 100 if balance_calls == 1 else 92}]}
        assert method == "POST"
        raise RuntimeError(f"transport rejected {_KEY}")

    monkeypatch.setattr(leonardo_api, "_request_json", leaking_transport)
    with pytest.raises(leonardo_api.LeonardoAPIError) as caught:
        await LeonardoAPIAdapter(artifacts_dir=tmp_path).generate(_request())
    assert _KEY not in str(caught.value)
    assert balance_calls == 2


def test_router_resolves_and_registers_leonardo_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_BACKEND_HERO", "leonardo_api")
    assert choose_backend("hero") is ImageBackend.LEONARDO_API
    assert get_adapter(ImageBackend.LEONARDO_API).backend is ImageBackend.LEONARDO_API
