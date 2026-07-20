"""Google Drive archive backends — the production destination for approved creatives.

Two auth strategies share ONE folder/upload implementation (`_DriveArchiveBase`); only how the
access token is acquired differs:

- `GoogleDriveArchive` (name ``google_drive``): a Google **service account** authenticates via
  the OAuth2 JWT-bearer flow (RS256-signed assertion → access token). Note: a service account
  has NO Drive storage quota of its own, so it cannot upload into a My-Drive folder (Google
  returns 403 "Service Accounts do not have storage quota") — it only works against a Shared
  Drive it has been granted access to.
- `GoogleDriveOAuthArchive` (name ``google_drive_oauth``): authenticates AS THE USER via the
  OAuth2 **refresh-token grant** (client_id + client_secret + refresh_token → access token).
  Archived files are owned by that user and use the user's storage quota — the working path for
  ordinary My-Drive folders. Obtain the refresh token once via ``scripts/drive_oauth.py``.

Both store the file under `Mimik Clients/<Client>/<YYYY-MM>/<job>/<file>` — the same canonical
tree as the local backend, so switching backends is a config change, not a rewrite.

No google-api-python-client dependency: every network call goes through a small module-level
seam (`_post_form`, `_api_get`, `_api_post_json`, `_upload`) built on stdlib urllib and wrapped
in `asyncio.to_thread`. Tests monkeypatch those seams, so nothing here ever hits the network in
dev/test. The service-account private key, the OAuth client secret / refresh token, and the
resulting access tokens are never logged.
"""

from __future__ import annotations

import abc
import asyncio
import json
import os
import time
import urllib.parse
import urllib.request

import jwt

from .base import ArchiveBackend, ArchivedFile, ArchiveError, archive_folder, safe_segment

_SCOPE = "https://www.googleapis.com/auth/drive.file"
_JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"
_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
_FOLDER_MIME = "application/vnd.google-apps.folder"
_DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
_DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
_TOKEN_TTL = 3600  # service-account assertions and Google access tokens both live one hour
# Refresh a little before the hard expiry so an in-flight request never races the boundary.
_TOKEN_SKEW = 60


def _post_form(url: str, fields: dict[str, str]) -> dict:
    """POST an application/x-www-form-urlencoded body (the OAuth token exchange)."""
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed google host)
        return json.loads(resp.read())


def _api_get(url: str, token: str) -> dict:
    """GET a Drive JSON endpoint with a bearer token."""
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"}, method="GET"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed google host)
        return json.loads(resp.read())


def _api_post_json(url: str, token: str, body: dict) -> dict:
    """POST a JSON body to a Drive JSON endpoint (folder creation)."""
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed google host)
        return json.loads(resp.read())


def _upload(url: str, token: str, metadata: dict, data: bytes, content_type: str) -> dict:
    """Multipart-upload file metadata + bytes to the Drive upload endpoint (uploadType=multipart)."""
    boundary = "mimik-boundary-a7f3c9e1b2d4"
    delimiter = f"--{boundary}".encode()
    closing = f"--{boundary}--".encode()
    parts = [
        delimiter,
        b"Content-Type: application/json; charset=UTF-8",
        b"",
        json.dumps(metadata).encode(),
        delimiter,
        f"Content-Type: {content_type}".encode(),
        b"",
        data,
        closing,
    ]
    payload = b"\r\n".join(parts)
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (fixed google host)
        return json.loads(resp.read())


def _load_service_account_info(raw: str) -> dict:
    """Resolve GOOGLE_SERVICE_ACCOUNT_JSON: a filesystem path to a JSON file, or the JSON itself."""
    candidate = raw.strip()
    if os.path.isfile(candidate):
        with open(candidate, encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(candidate)


class _DriveArchiveBase(ArchiveBackend):
    """Shared folder-ensure + multipart-upload + token-cache logic for every Drive backend.

    Subclasses differ ONLY in how they mint an access token — override `_fetch_access_token`.
    """

    def __init__(self, *, root_folder_id: str) -> None:
        self._root_folder_id = root_folder_id
        # In-memory access-token cache: (token, unix_expiry). Refreshed on demand.
        self._token: str | None = None
        self._token_expiry: float = 0.0

    @abc.abstractmethod
    async def _fetch_access_token(self) -> tuple[str, int]:
        """Mint a fresh access token. Return (token, expires_in_seconds)."""
        raise NotImplementedError

    async def _get_access_token(self) -> str:
        """Return a cached access token, minting a fresh one via `_fetch_access_token` when expired."""
        if self._token is not None and time.time() < self._token_expiry - _TOKEN_SKEW:
            return self._token
        token, expires_in = await self._fetch_access_token()
        if not token:
            raise ArchiveError("token exchange returned no access_token")
        self._token = token
        self._token_expiry = time.time() + expires_in
        return token

    async def _ensure_folder(self, name: str, parent_id: str, token: str) -> str:
        """Return the id of the folder `name` under `parent_id`, creating it if it doesn't exist."""
        # Sanitize HERE too — never trust the caller to have cleaned `name` before it lands in
        # the Drive query string. safe_segment strips everything that could break the quoting.
        name = safe_segment(name)
        query = (
            f"name = '{name}' and '{parent_id}' in parents "
            f"and mimeType = '{_FOLDER_MIME}' and trashed = false"
        )
        params = urllib.parse.urlencode({"q": query, "fields": "files(id,name)"})
        found = await asyncio.to_thread(_api_get, f"{_DRIVE_FILES}?{params}", token)
        files = found.get("files") or []
        if files:
            return files[0]["id"]
        body = {"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]}
        created = await asyncio.to_thread(_api_post_json, _DRIVE_FILES, token, body)
        return created["id"]

    async def archive(
        self, *, client_name: str, year_month: str, job_id: str, filename: str, data: bytes
    ) -> ArchivedFile:
        token = await self._get_access_token()
        # Walk/create the canonical folder chain: Mimik Clients / <client> / <ym> / <job>.
        parent_id = self._root_folder_id
        for segment in archive_folder(client_name, year_month, job_id).split("/"):
            parent_id = await self._ensure_folder(safe_segment(segment), parent_id, token)
        safe_name = safe_segment(filename, fallback="creative.png")
        metadata = {"name": safe_name, "parents": [parent_id]}
        created = await asyncio.to_thread(
            _upload, _DRIVE_UPLOAD, token, metadata, data, "image/png"
        )
        ref = created.get("webViewLink") or created.get("id") or ""
        path = f"{archive_folder(client_name, year_month, job_id)}/{safe_name}"
        return ArchivedFile(path=path, ref=ref, backend=self.name)


class GoogleDriveArchive(_DriveArchiveBase):
    """Service-account backend (OAuth2 JWT-bearer flow). Works only against a Shared Drive —
    a service account has no My-Drive storage quota."""

    name = "google_drive"

    def __init__(self, *, service_account_info: dict, root_folder_id: str) -> None:
        super().__init__(root_folder_id=root_folder_id)
        self._client_email: str = service_account_info["client_email"]
        self._private_key: str = service_account_info["private_key"]
        self._token_uri: str = service_account_info.get("token_uri") or _DEFAULT_TOKEN_URI

    @classmethod
    def from_env(cls) -> GoogleDriveArchive:
        """Build from the environment. Missing config is the graceful human-gate, not a crash."""
        raw = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
        root_folder_id = (os.environ.get("DRIVE_ROOT_FOLDER_ID") or "").strip()
        if not raw or not root_folder_id:
            raise ArchiveError(
                "Google Drive archive is not configured — "
                "set GOOGLE_SERVICE_ACCOUNT_JSON and DRIVE_ROOT_FOLDER_ID"
            )
        return cls(
            service_account_info=_load_service_account_info(raw),
            root_folder_id=root_folder_id,
        )

    def _make_assertion(self) -> str:
        """Build the RS256-signed JWT-bearer assertion for the token exchange."""
        now = int(time.time())
        claims = {
            "iss": self._client_email,
            "scope": _SCOPE,
            "aud": self._token_uri,
            "iat": now,
            "exp": now + _TOKEN_TTL,
        }
        return jwt.encode(claims, self._private_key, algorithm="RS256")

    async def _fetch_access_token(self) -> tuple[str, int]:
        fields = {"grant_type": _JWT_BEARER, "assertion": self._make_assertion()}
        data = await asyncio.to_thread(_post_form, self._token_uri, fields)
        token = data.get("access_token")
        expires_in = int(data.get("expires_in", _TOKEN_TTL))
        return token, expires_in


class GoogleDriveOAuthArchive(_DriveArchiveBase):
    """User-owned backend (OAuth2 refresh-token grant).

    Authenticates AS THE USER, so archived files are owned by the user and use the user's
    storage quota — fixing the service-account "no storage quota" 403 for My-Drive folders.
    """

    name = "google_drive_oauth"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        root_folder_id: str,
        token_uri: str = _DEFAULT_TOKEN_URI,
    ) -> None:
        super().__init__(root_folder_id=root_folder_id)
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._token_uri = token_uri

    @classmethod
    def from_env(cls) -> GoogleDriveOAuthArchive:
        """Build from the environment. Missing config is the graceful human-gate, not a crash."""
        client_id = (os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or "").strip()
        client_secret = (os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()
        refresh_token = (os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN") or "").strip()
        root_folder_id = (os.environ.get("DRIVE_ROOT_FOLDER_ID") or "").strip()
        if not (client_id and client_secret and refresh_token and root_folder_id):
            raise ArchiveError(
                "Google Drive OAuth archive is not configured — set "
                "GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, "
                "GOOGLE_OAUTH_REFRESH_TOKEN, and DRIVE_ROOT_FOLDER_ID "
                "(obtain the refresh token via scripts/drive_oauth.py)"
            )
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            root_folder_id=root_folder_id,
        )

    async def _fetch_access_token(self) -> tuple[str, int]:
        fields = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }
        data = await asyncio.to_thread(_post_form, self._token_uri, fields)
        token = data.get("access_token")
        expires_in = int(data.get("expires_in", _TOKEN_TTL))
        return token, expires_in
