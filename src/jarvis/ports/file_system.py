"""The filesystem port: the seam between an authorized read/write and a real file.

:class:`FileSystemPort` is the one abstract boundary between "some
real file on disk" and the ``fs.*`` capabilities. It says nothing
about *which* paths are acceptable to touch -- that is a kernel-level
policy decision (see ``jarvis.kernel.files``), not a property of how
bytes move on disk.

**Updated 2026-09-04**: ``list_dir``/``move``/``delete`` join
``read_text`` -- the real gap this project's own charter names ("file
management") and `docs/threat-model/v0.md`'s own charter-completeness
re-check confirmed as the one real, missing capability. `delete`
removes a single real file only -- recursive directory deletion is
deliberately out of scope for this pass, a real, separate, more
consequential decision this port does not make speculatively. `move`
handles both real files and real directories (`shutil.move`'s own
native behavior), a real asymmetry stated plainly, not hidden: moving
is reversible, recursive deletion is not.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.file_system`` for the
concrete local-filesystem adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.file_system import DirEntry


@runtime_checkable
class FileSystemPort(Protocol):
    """A real filesystem a capability can read, list, move, and delete real files on."""

    def read_text(self, path: Path) -> str:
        """Return the text content of the file at ``path``.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            IsADirectoryError: If ``path`` is a directory.
            PermissionError: If the file cannot be read.
            UnicodeDecodeError: If the file is not valid UTF-8 text.
        """
        ...

    def list_dir(self, path: Path) -> tuple[DirEntry, ...]:
        """Return every real entry directly inside the directory at ``path`` (not recursive).

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            NotADirectoryError: If ``path`` is not a directory.
            PermissionError: If the directory cannot be listed.
        """
        ...

    def move(self, source: Path, destination: Path) -> None:
        """Move the real file or directory at ``source`` to ``destination``.

        Mirrors ``shutil.move``'s own real, documented behavior exactly
        -- including that an existing file at ``destination`` is
        overwritten, and an existing directory at ``destination`` moves
        ``source`` inside it. No new, hidden safety logic here.

        Raises:
            FileNotFoundError: If ``source`` does not exist.
            PermissionError: If either path cannot be accessed.
            OSError: For other real, underlying filesystem failures
                (e.g. moving across an unsupported filesystem boundary).
        """
        ...

    def delete(self, path: Path) -> None:
        """Permanently delete the real file at ``path``. Files only -- see module docstring.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            IsADirectoryError: If ``path`` is a directory.
            PermissionError: If the file cannot be deleted.
        """
        ...
