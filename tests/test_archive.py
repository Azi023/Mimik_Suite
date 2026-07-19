"""Archive adapter: the local backend writes to the canonical per-client tree and refuses
to escape its root."""

from __future__ import annotations

from pathlib import Path

import pytest

from creative.archive import ArchiveError, LocalArchive, archive_folder, get_archive_backend, safe_segment


def test_archive_folder_is_canonical_and_sanitised() -> None:
    folder = archive_folder("RCD Central", "2026-08", "job-123")
    assert folder == "Mimik Clients/RCD-Central/2026-08/job-123"
    # Traversal + separators in a client name collapse to safe segments.
    dirty = archive_folder("../../etc", "2026-08", "j")
    assert ".." not in dirty
    assert dirty.startswith("Mimik Clients/")


def test_safe_segment_never_empty() -> None:
    assert safe_segment("", fallback="x") == "x"
    assert safe_segment("///", fallback="x") == "x"
    assert safe_segment("a b/c") == "a-b-c"


async def test_local_archive_writes_expected_path(tmp_path: Path) -> None:
    archive = LocalArchive(tmp_path)
    stored = await archive.archive(
        client_name="RCD Central",
        year_month="2026-08",
        job_id="job-1",
        filename="launch.png",
        data=b"PNGDATA",
    )
    assert stored.backend == "local"
    assert stored.path == "Mimik Clients/RCD-Central/2026-08/job-1/launch.png"
    written = tmp_path / stored.path
    assert written.read_bytes() == b"PNGDATA"


async def test_local_archive_blocks_traversal_filename(tmp_path: Path) -> None:
    archive = LocalArchive(tmp_path)
    stored = await archive.archive(
        client_name="C", year_month="2026-08", job_id="j",
        filename="../../escape.png", data=b"x",
    )
    # The filename is sanitised to a single safe segment — nothing escapes the root.
    assert (tmp_path / stored.path).resolve().is_relative_to(tmp_path.resolve())
    assert ".." not in stored.path


def test_backend_selector_defaults_to_local(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ARCHIVE_BACKEND", raising=False)
    monkeypatch.setenv("ARCHIVE_LOCAL_ROOT", str(tmp_path))
    backend = get_archive_backend()
    assert backend.name == "local"


def test_backend_selector_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIVE_BACKEND", "dropbox")
    with pytest.raises(ArchiveError):
        get_archive_backend()
