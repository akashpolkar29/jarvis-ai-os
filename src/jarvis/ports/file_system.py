"""The filesystem port: the seam between an authorized read and a real file.

:class:`FileSystemPort` is the one abstract boundary between "some
real file on disk" and the ``fs.read_file`` capability. It says
nothing about *which* paths are acceptable to read -- that is a
kernel-level policy decision (see ``jarvis.kernel.files``), not a
property of how bytes get off disk.

Only ``read_text`` exists for now, matching what ``fs.read_file``
actually needs; write/list/delete methods would join this port later
if a capability needs them, not built speculatively here.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.file_system`` for the
concrete local-filesystem adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path


@runtime_checkable
class FileSystemPort(Protocol):
    """A real filesystem a capability can read files from."""

    def read_text(self, path: Path) -> str:
        """Return the text content of the file at ``path``.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            IsADirectoryError: If ``path`` is a directory.
            PermissionError: If the file cannot be read.
            UnicodeDecodeError: If the file is not valid UTF-8 text.
        """
        ...
