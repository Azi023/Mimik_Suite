"""Archive backend registry + selector.

`get_archive_backend()` resolves the configured backend from `ARCHIVE_BACKEND` (default
`local`). The local backend needs no credentials; the Google Drive backend is selected only
when `ARCHIVE_BACKEND=google_drive` AND a service account is configured (else it fails loud).
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
    raise ArchiveError(f"unknown ARCHIVE_BACKEND: {name!r} (expected 'local' or 'google_drive')")
