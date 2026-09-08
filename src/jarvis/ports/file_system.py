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

**Updated 2026-09-08**: ``find``/``search_content``/``recent`` join
the four above -- real filename search (glob), bounded grep-style
content search, and a real-mtime-sorted recent-files view, all
recursive beneath a given root. Each real result is re-validated
against the caller's own scope boundary at the kernel layer (see
``jarvis.kernel.files``), not here -- this port has no scope opinion
of its own, same as every other method above.

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

    def find(self, root: Path, pattern: str) -> tuple[Path, ...]:
        """Return every real path under ``root`` (recursive) matching the glob ``pattern``.

        Args:
            root: The real directory to search, recursively, beneath.
            pattern: A real glob pattern (``pathlib``'s own syntax --
                e.g. ``"*.py"``, ``"**/test_*.py"``).

        Returns:
            Every real matching path, sorted. The caller (see
            ``jarvis.kernel.files``) is responsible for re-validating
            each result against its own scope boundary -- a pattern
            containing ``..`` segments, or a symlink inside ``root``
            pointing outside it, can otherwise cause a match outside
            ``root`` to be returned.
        """
        ...

    def search_content(
        self, root: Path, query: str, *, max_file_bytes: int, max_files_scanned: int
    ) -> tuple[tuple[tuple[Path, int, str], ...], bool]:
        """Grep-style search: every real ``(path, line_number, line)`` match under ``root``.

        Bounded, real, and honest about it: a file larger than
        ``max_file_bytes`` is skipped entirely (never partially read),
        and scanning stops once ``max_files_scanned`` real files have
        been examined. The returned ``capped`` flag is the real,
        honest signal for that second case -- the caller (see
        ``jarvis.kernel.files``) must surface it, never silently
        returning a partial result as if it were complete.

        Args:
            root: The real directory to search, recursively, beneath.
            query: A real, literal substring to search for, per line.
            max_file_bytes: Files larger than this are skipped.
            max_files_scanned: Stop after examining this many real
                files, whether or not the whole tree was covered.

        Returns:
            ``(matches, capped)`` -- every real matching
            ``(path, line_number, line)`` triple, in real traversal
            order, and whether ``max_files_scanned`` was reached
            before the whole tree was covered.
        """
        ...

    def recent(self, root: Path, limit: int) -> tuple[Path, ...]:
        """Return the ``limit`` most recently modified real files under ``root`` (recursive).

        Directories are not returned -- files only, real modification
        time (``st_mtime``), most recent first.

        Args:
            root: The real directory to search, recursively, beneath.
            limit: The maximum number of real files to return.

        Returns:
            Up to ``limit`` real file paths, most recently modified
            first.
        """
        ...
