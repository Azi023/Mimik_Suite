"""Archive adapter interface — the seam that makes "local dev now, Google Drive later" a
config change, not a rewrite (same pattern as the image adapters).

On approval, a creative is archived to a stable, organized path
`Mimik Clients/<Client>/<YYYY-MM>/<job>/<file>` — enforced in code, never a human remembering
to upload. The default backend writes to the local filesystem (zero credentials); the Google
Drive backend plugs into this same interface once a service account is configured.
"""

from __future__ import annotations

import abc
import re

from pydantic import BaseModel

_ROOT_FOLDER = "Mimik Clients"
# Path-segment sanitiser: collapse anything that could traverse or break a path into a hyphen.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class ArchiveError(RuntimeError):
    """Archival failed (backend not configured, upload error, ...)."""


class ArchivedFile(BaseModel):
    """Where a creative landed. `path` is the human-readable location; `ref` is the
    backend-specific handle (a filesystem path, or a Drive file id/URL)."""

    path: str
    ref: str
    backend: str


def safe_segment(value: str, *, fallback: str = "item") -> str:
    """One path segment, stripped of anything that could traverse or escape the tree."""
    cleaned = _UNSAFE.sub("-", value.strip()).strip("-.")
    return cleaned or fallback


def archive_folder(client_name: str, year_month: str, job_id: str) -> str:
    """The canonical per-creative folder path (segments individually sanitised)."""
    return "/".join(
        (
            _ROOT_FOLDER,
            safe_segment(client_name, fallback="client"),
            safe_segment(year_month, fallback="undated"),
            safe_segment(job_id, fallback="job"),
        )
    )


class ArchiveBackend(abc.ABC):
    """A destination for approved creatives."""

    name: str

    @abc.abstractmethod
    async def archive(
        self, *, client_name: str, year_month: str, job_id: str, filename: str, data: bytes
    ) -> ArchivedFile:
        """Store `data` at the canonical folder for this creative and return where it landed."""
        raise NotImplementedError
