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
