"""Adapters implementing jarvis.ports.file_system.FileSystemPort.

:class:`LocalFileSystemAdapter` is a thin wrapper around ``pathlib``/
``shutil`` -- no new protocol, no new failure modes invented.
``FileNotFoundError``/``IsADirectoryError``/``NotADirectoryError``/
``PermissionError``/``UnicodeDecodeError``/``OSError`` all propagate
exactly as ``pathlib``/``shutil`` raise them: each is already a clear,
specific, well-understood exception, so wrapping them would add a
layer of indirection without adding information, the same reasoning
``jarvis.adapters.audit_storage`` used for malformed-file errors
(WP-12).

This adapter has no opinion about which paths are acceptable to
touch, or whether a real action is authorized at all -- that scoping/
authorization decision belongs to ``jarvis.kernel.files``, which calls
this adapter only after deciding a path is in bounds and the real
action is granted.

**Updated 2026-09-08**: ``find``/``search_content``/``recent`` use
``Path.rglob("*")`` (or a caller-given glob pattern for ``find``) for
real, recursive traversal -- the same stdlib-only mechanism
``list_dir`` already uses one level deep, extended to the whole tree.
Deliberately, this adapter does **not** itself re-check each result
against a scope boundary (that check happens once, at the kernel
layer, on every returned result -- see ``jarvis.kernel.files``): a
glob pattern containing ``..`` segments, or a real symlink inside
``root`` pointing outside it, can make ``rglob`` return a path outside
``root``, and this adapter has no scope opinion of its own to catch
that, matching every other method here.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from jarvis.domain.file_system import DirEntry

if TYPE_CHECKING:
    from pathlib import Path


class LocalFileSystemAdapter:
    """Reads, lists, moves, and deletes real files/directories via pathlib/shutil."""

    def read_text(self, path: Path) -> str:
        """Return the text content of the file at ``path``, decoded as UTF-8."""
        return path.read_text(encoding="utf-8")

    def list_dir(self, path: Path) -> tuple[DirEntry, ...]:
        """Return every real entry directly inside ``path``, sorted by name."""
        entries = sorted(path.iterdir(), key=lambda entry: entry.name)
        return tuple(DirEntry(name=entry.name, is_dir=entry.is_dir()) for entry in entries)

    def move(self, source: Path, destination: Path) -> None:
        """Move the real file or directory at ``source`` to ``destination`` via shutil.move."""
        shutil.move(str(source), str(destination))

    def delete(self, path: Path) -> None:
        """Permanently delete the real file at ``path`` via Path.unlink -- files only."""
        path.unlink()

    def find(self, root: Path, pattern: str) -> tuple[Path, ...]:
        """Return every real path under ``root`` matching ``pattern``, via Path.rglob."""
        return tuple(sorted(root.rglob(pattern)))

    def search_content(
        self, root: Path, query: str, *, max_file_bytes: int, max_files_scanned: int
    ) -> tuple[tuple[tuple[Path, int, str], ...], bool]:
        """Grep-style search via plain, line-by-line substring matching -- no regex, no new dependency."""  # noqa: E501
        matches: list[tuple[Path, int, str]] = []
        scanned = 0
        capped = False
        for candidate in sorted(root.rglob("*")):
            if not candidate.is_file():
                continue
            if scanned >= max_files_scanned:
                capped = True
                break
            scanned += 1
            try:
                if candidate.stat().st_size > max_file_bytes:
                    continue
                text = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if query in line:
                    matches.append((candidate, line_number, line))
        return tuple(matches), capped

    def recent(self, root: Path, limit: int) -> tuple[Path, ...]:
        """Return the ``limit`` most recently modified real files under ``root``, via Path.rglob."""
        files = [candidate for candidate in root.rglob("*") if candidate.is_file()]
        files.sort(key=lambda candidate: candidate.stat().st_mtime, reverse=True)
        return tuple(files[:limit])
