"""GoogleDriveOAuthArchive: config human-gate, refresh-token grant shape, folder chain +
upload, token caching, and backend selection — all with ZERO network (seams monkeypatched).

This is the WORKING prod path: it archives as the user (files owned by the user, using the
user's quota), unlike the service-account backend which 403s on My-Drive folders.
"""

from __future__ import annotations

import pytest

from creative.archive import get_archive_backend
from creative.archive import google_drive as gd
from creative.archive.base import ArchiveError

_OAUTH_ENV = {
    "GOOGLE_OAUTH_CLIENT_ID": "cid.apps.googleusercontent.com",
    "GOOGLE_OAUTH_CLIENT_SECRET": "secret-xyz",
    "GOOGLE_OAUTH_REFRESH_TOKEN": "1//refresh-abc",
    "DRIVE_ROOT_FOLDER_ID": "root-000",
}


def _oauth() -> gd.GoogleDriveOAuthArchive:
    return gd.GoogleDriveOAuthArchive(
        client_id="cid.apps.googleusercontent.com",
        client_secret="secret-xyz",
        refresh_token="1//refresh-abc",
        root_folder_id="root-000",
    )


def _set_oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _OAUTH_ENV.items():
        monkeypatch.setenv(key, value)


def test_from_env_raises_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _OAUTH_ENV:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ArchiveError):
        gd.GoogleDriveOAuthArchive.from_env()


def test_from_env_raises_when_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_oauth_env(monkeypatch)
    monkeypatch.delenv("GOOGLE_OAUTH_REFRESH_TOKEN", raising=False)  # one missing = fail loud
    with pytest.raises(ArchiveError):
        gd.GoogleDriveOAuthArchive.from_env()


def test_from_env_builds_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_oauth_env(monkeypatch)
    backend = gd.GoogleDriveOAuthArchive.from_env()
    assert backend.name == "google_drive_oauth"
    assert backend._root_folder_id == "root-000"
    assert backend._refresh_token == "1//refresh-abc"


async def test_refresh_grant_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """The token exchange must be a refresh_token grant carrying the client creds + token."""
    archive = _oauth()
    captured: dict = {}

    def fake_post_form(url: str, fields: dict) -> dict:
        captured["url"] = url
        captured["fields"] = fields
        return {"access_token": "ya29.tok", "expires_in": 3599}

    monkeypatch.setattr(gd, "_post_form", fake_post_form)
    token = await archive._get_access_token()
    assert token == "ya29.tok"
    assert captured["fields"] == {
        "grant_type": "refresh_token",
        "client_id": "cid.apps.googleusercontent.com",
        "client_secret": "secret-xyz",
        "refresh_token": "1//refresh-abc",
    }
    assert "oauth2.googleapis.com/token" in captured["url"]


async def test_archive_creates_chain_and_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    archive = _oauth()
    upload_capture: dict = {}
    folder_ids = iter(["id-clients", "id-client", "id-ym", "id-job"])

    monkeypatch.setattr(gd, "_post_form", lambda url, fields: {"access_token": "t", "expires_in": 3600})
    monkeypatch.setattr(gd, "_api_get", lambda url, token: {"files": []})
    monkeypatch.setattr(gd, "_api_post_json", lambda url, token, body: {"id": next(folder_ids)})

    def fake_upload(url, token, metadata, data, content_type) -> dict:
        upload_capture.update(
            data=data, content_type=content_type, parent=metadata["parents"][0]
        )
        return {"id": "file123", "webViewLink": "https://drive.google.com/file/d/file123/view"}

    monkeypatch.setattr(gd, "_upload", fake_upload)

    stored = await archive.archive(
        client_name="Glo2Go Aesthetics",
        year_month="2026-07",
        job_id="job-1",
        filename="polynucleotides.png",
        data=b"PNGDATA",
    )
    assert stored.backend == "google_drive_oauth"
    assert "file123" in stored.ref
    assert stored.path == "Mimik Clients/Glo2Go-Aesthetics/2026-07/job-1/polynucleotides.png"
    assert upload_capture["data"] == b"PNGDATA"
    assert upload_capture["content_type"] == "image/png"
    assert upload_capture["parent"] == "id-job"  # uploaded under the deepest created folder


async def test_token_is_cached_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    archive = _oauth()
    calls = 0

    def fake_post_form(url: str, fields: dict) -> dict:
        nonlocal calls
        calls += 1
        return {"access_token": "t", "expires_in": 3600}

    monkeypatch.setattr(gd, "_post_form", fake_post_form)
    monkeypatch.setattr(gd, "_api_get", lambda url, token: {"files": [{"id": "f", "name": "x"}]})
    monkeypatch.setattr(gd, "_upload", lambda *a, **k: {"id": "f"})

    kwargs = dict(client_name="C", year_month="2026-07", job_id="j", filename="f.png", data=b"x")
    await archive.archive(**kwargs)
    await archive.archive(**kwargs)
    assert calls == 1  # refresh grant ran once; the access token was reused


def test_get_archive_backend_selects_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_oauth_env(monkeypatch)
    monkeypatch.setenv("ARCHIVE_BACKEND", "google_drive_oauth")
    backend = get_archive_backend()
    assert backend.name == "google_drive_oauth"


def test_get_archive_backend_oauth_unconfigured_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _OAUTH_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ARCHIVE_BACKEND", "google_drive_oauth")
    with pytest.raises(ArchiveError):
        get_archive_backend()
