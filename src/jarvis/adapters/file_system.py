"""Adapters implementing jarvis.ports.file_system.FileSystemPort.

:class:`LocalFileSystemAdapter` is a thin wrapper around
``pathlib.Path.read_text`` -- no new protocol, no new failure modes
invented. ``FileNotFoundError``/``IsADirectoryError``/``PermissionError``/
``UnicodeDecodeError`` all propagate exactly as ``pathlib`` raises
them: each is already a clear, specific, well-understood exception, so
wrapping them would add a layer of indirection without adding
information, the same reasoning ``jarvis.adapters.audit_storage`` used
for malformed-file errors (WP-12).

This adapter has no opinion about which paths are acceptable to read
-- that scoping decision belongs to ``jarvis.kernel.files``, which
calls this adapter only after deciding a path is in bounds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class LocalFileSystemAdapter:
    """Reads files directly from the local filesystem via pathlib."""

    def read_text(self, path: Path) -> str:
        """Return the text content of the file at ``path``, decoded as UTF-8."""
        return path.read_text(encoding="utf-8")
