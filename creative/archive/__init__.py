"""Archive backend registry + selector.

`get_archive_backend()` resolves the configured backend from `ARCHIVE_BACKEND` (default
`local`). The local backend needs no credentials. `google_drive` (service account, JWT-bearer)
and `google_drive_oauth` (user OAuth refresh-token grant) each fail loud if unconfigured. Prefer
`google_drive_oauth` for ordinary My-Drive folders — a service account has no storage quota.
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import ArchiveBackend, ArchivedFile, ArchiveError, archive_folder, safe_segment
from .local import LocalArchive

__all__ = [
    "ArchiveBackend",
    "ArchivedFile",
    "ArchiveError",
    "LocalArchive",
    "archive_folder",
    "safe_segment",
    "get_archive_backend",
]


def get_archive_backend() -> ArchiveBackend:
    """Resolve the configured archive backend. Fail loud on an unknown name."""
    name = (os.environ.get("ARCHIVE_BACKEND") or "local").strip().lower()
    if name == "local":
        root = os.environ.get("ARCHIVE_LOCAL_ROOT") or "./_archive"
        return LocalArchive(Path(root))
    if name == "google_drive":
        from .google_drive import GoogleDriveArchive  # deferred: needs a service account

        return GoogleDriveArchive.from_env()
    if name == "google_drive_oauth":
        from .google_drive import GoogleDriveOAuthArchive  # deferred: needs OAuth creds

        return GoogleDriveOAuthArchive.from_env()
    raise ArchiveError(
        f"unknown ARCHIVE_BACKEND: {name!r} "
        "(expected 'local', 'google_drive', or 'google_drive_oauth')"
    )
