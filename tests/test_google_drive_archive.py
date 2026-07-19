"""GoogleDriveArchive: config human-gate, RS256 assertion signing, folder chain build/reuse,
multipart upload, and token caching — all with ZERO network (every seam monkeypatched)."""

from __future__ import annotations

import json
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from creative.archive import google_drive as gd
from creative.archive.base import ArchiveError

_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _keypair() -> tuple[str, str]:
    """Throwaway RSA keypair → (private_key_pem, public_key_pem) as PEM strings."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def _sa_info(private_pem: str) -> dict:
    return {
        "client_email": "svc@mimik-suite.iam.gserviceaccount.com",
        "private_key": private_pem,
        "token_uri": _TOKEN_URI,
    }


def _archive(private_pem: str) -> gd.GoogleDriveArchive:
    return gd.GoogleDriveArchive(
        service_account_info=_sa_info(private_pem), root_folder_id="root-000"
    )


def test_from_env_raises_when_service_account_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("DRIVE_ROOT_FOLDER_ID", "root-000")
    with pytest.raises(ArchiveError):
        gd.GoogleDriveArchive.from_env()


def test_from_env_raises_when_root_folder_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.delenv("DRIVE_ROOT_FOLDER_ID", raising=False)
    with pytest.raises(ArchiveError):
        gd.GoogleDriveArchive.from_env()


def test_from_env_parses_json_string(monkeypatch: pytest.MonkeyPatch) -> None:
    private_pem, _ = _keypair()
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps(_sa_info(private_pem)))
    monkeypatch.setenv("DRIVE_ROOT_FOLDER_ID", "root-abc")
    backend = gd.GoogleDriveArchive.from_env()
    assert backend.name == "google_drive"
    assert backend._client_email == "svc@mimik-suite.iam.gserviceaccount.com"
    assert backend._root_folder_id == "root-abc"


def test_from_env_parses_file_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    private_pem, _ = _keypair()
    sa_file = tmp_path / "sa.json"
    sa_file.write_text(json.dumps(_sa_info(private_pem)), encoding="utf-8")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", str(sa_file))
    monkeypatch.setenv("DRIVE_ROOT_FOLDER_ID", "root-file")
    backend = gd.GoogleDriveArchive.from_env()
    assert backend._root_folder_id == "root-file"
    assert backend._token_uri == _TOKEN_URI


def test_make_assertion_verifies_with_public_key() -> None:
    private_pem, public_pem = _keypair()
    archive = _archive(private_pem)
    assertion = archive._make_assertion()
    decoded = jwt.decode(
        assertion, public_pem, algorithms=["RS256"], audience=_TOKEN_URI
    )
    assert decoded["iss"] == "svc@mimik-suite.iam.gserviceaccount.com"
    assert decoded["scope"] == "https://www.googleapis.com/auth/drive.file"
    assert decoded["exp"] - decoded["iat"] == 3600


async def test_archive_happy_path_creates_chain_and_uploads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_pem, _ = _keypair()
    archive = _archive(private_pem)

    token_calls: list[tuple[str, dict]] = []
    upload_capture: dict = {}
    folder_ids = iter(["id-clients", "id-client", "id-ym", "id-job"])

    def fake_post_form(url: str, fields: dict) -> dict:
        token_calls.append((url, fields))
        return {"access_token": "tok", "expires_in": 3600}

    def fake_api_get(url: str, token: str) -> dict:
        return {"files": []}  # nothing exists yet → creation path runs for every segment

    def fake_api_post_json(url: str, token: str, body: dict) -> dict:
        return {"id": next(folder_ids)}

    def fake_upload(url, token, metadata, data, content_type) -> dict:
        upload_capture["metadata"] = metadata
        upload_capture["data"] = data
        upload_capture["content_type"] = content_type
        upload_capture["parent"] = metadata["parents"][0]
        return {"id": "file123"}

    monkeypatch.setattr(gd, "_post_form", fake_post_form)
    monkeypatch.setattr(gd, "_api_get", fake_api_get)
    monkeypatch.setattr(gd, "_api_post_json", fake_api_post_json)
    monkeypatch.setattr(gd, "_upload", fake_upload)

    stored = await archive.archive(
        client_name="RCD Central",
        year_month="2026-08",
        job_id="job-1",
        filename="launch.png",
        data=b"PNGDATA",
    )

    assert stored.backend == "google_drive"
    assert "file123" in stored.ref
    assert stored.path == "Mimik Clients/RCD-Central/2026-08/job-1/launch.png"
    # The exact PNG bytes reached the upload seam, under the deepest created folder.
    assert upload_capture["data"] == b"PNGDATA"
    assert upload_capture["content_type"] == "image/png"
    assert upload_capture["parent"] == "id-job"
    assert len(token_calls) == 1


async def test_archive_reuses_existing_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    private_pem, _ = _keypair()
    archive = _archive(private_pem)

    created_names: list[str] = []

    def fake_post_form(url: str, fields: dict) -> dict:
        return {"access_token": "tok", "expires_in": 3600}

    def fake_api_get(url: str, token: str) -> dict:
        return {"files": [{"id": "existing-folder", "name": "found"}]}  # always found

    def fake_api_post_json(url: str, token: str, body: dict) -> dict:
        created_names.append(body["name"])  # must NOT be reached for reused folders
        return {"id": "should-not-happen"}

    def fake_upload(url, token, metadata, data, content_type) -> dict:
        return {"id": "fileZZZ"}

    monkeypatch.setattr(gd, "_post_form", fake_post_form)
    monkeypatch.setattr(gd, "_api_get", fake_api_get)
    monkeypatch.setattr(gd, "_api_post_json", fake_api_post_json)
    monkeypatch.setattr(gd, "_upload", fake_upload)

    await archive.archive(
        client_name="C", year_month="2026-08", job_id="j", filename="f.png", data=b"x"
    )
    assert created_names == []  # every segment was reused → creation seam never called


async def test_token_is_cached_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    private_pem, _ = _keypair()
    archive = _archive(private_pem)

    post_form_calls = 0

    def fake_post_form(url: str, fields: dict) -> dict:
        nonlocal post_form_calls
        post_form_calls += 1
        return {"access_token": "tok", "expires_in": 3600}

    def fake_api_get(url: str, token: str) -> dict:
        return {"files": [{"id": "folder", "name": "x"}]}

    def fake_upload(url, token, metadata, data, content_type) -> dict:
        return {"id": "f"}

    monkeypatch.setattr(gd, "_post_form", fake_post_form)
    monkeypatch.setattr(gd, "_api_get", fake_api_get)
    monkeypatch.setattr(gd, "_upload", fake_upload)

    kwargs = dict(client_name="C", year_month="2026-08", job_id="j", filename="f.png", data=b"x")
    await archive.archive(**kwargs)
    await archive.archive(**kwargs)
    assert post_form_calls == 1  # token from the first call was reused on the second
