"""Local-filesystem archive backend — the zero-credential default for dev/test and for
running the full approval→archive flow without any external service.

Writes to `<root>/Mimik Clients/<Client>/<YYYY-MM>/<job>/<file>`. Segments are sanitised by
`base.safe_segment`, and the final resolved path is confirmed to stay under `root` (defence
in depth against traversal even though the segments are already cleaned).
"""

from __future__ import annotations

from pathlib import Path

from .base import ArchiveBackend, ArchivedFile, ArchiveError, archive_folder, safe_segment


class LocalArchive(ArchiveBackend):
    name = "local"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    async def archive(
        self, *, client_name: str, year_month: str, job_id: str, filename: str, data: bytes
    ) -> ArchivedFile:
        folder = self.root / archive_folder(client_name, year_month, job_id)
        target = folder / safe_segment(filename, fallback="creative.png")
        resolved = target.resolve()
        # Confirm the write stays inside the archive root (no traversal escaped the segments).
        if not resolved.is_relative_to(self.root):
            raise ArchiveError(f"refusing to write outside the archive root: {resolved}")
        folder.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(data)
        path = str(resolved.relative_to(self.root))
        return ArchivedFile(path=path, ref=str(resolved), backend=self.name)
