"""The draft storage port: the seam between a drafted document's content and a real file.

:class:`DraftStoragePort` is M6b's own new write surface (WP-82,
`docs/architecture/m6b-job-assistance.md`) -- mirroring
:class:`~jarvis.ports.memory_write.MemoryWritePort`'s and
:class:`~jarvis.ports.workspace.WorkspacePort`'s own "one new port per
genuinely new write shape" precedent (ADR-0048, ADR-0043). Checked
against both of those existing write-shaped ports before adding a
third: ``WorkspacePort.apply_patch`` is ``git apply``-backed and
expects real unified-diff text against an existing repository -- a
drafted cover letter is plain prose with no repository to diff
against, a real, honest mismatch, not forced into that shape. This
port is the minimal, honest answer instead: one method, no diff
format, no repository concept at all.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.draft_storage`` (WP-83)
for the concrete, local-filesystem-backed adapter that satisfies this
port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path


@runtime_checkable
class DraftStoragePort(Protocol):
    """A real, writable location a drafted document's content can be saved to as a new file."""

    def save(self, filename_hint: str, content: str) -> Path:
        """Persist ``content`` as a new, real file, named from ``filename_hint``.

        No authorization happens inside this method -- matching every
        other port in this repo, this is a pure mechanism. The
        composition root resolves the real ``Effect``/``Tier`` for a
        drafting invocation and checks ``AuthorizationOrchestrator``'s
        real ``Decision`` *before* ever calling this method at all.

        Args:
            filename_hint: A real, human-meaningful name to derive the
                real filename from (e.g. ``"cover-letter"``). Not
                itself the real filename -- see the uniqueness
                guarantee below.
            content: The real, already-selected text to persist
                verbatim.

        Returns:
            The real path ``content`` was written to.

        Raises:
            OSError: If the real write fails for any real filesystem
                reason (permissions, no space, etc.) -- matching
                :meth:`~jarvis.ports.file_system.FileSystemPort.read_text`'s
                own precedent of letting real OS-level exceptions
                propagate rather than wrapping them in a new type.

        Note:
            Never overwrites an existing file that already has
            ``filename_hint``'s own derived name -- a real,
            adapter-level uniqueness guarantee (e.g. a timestamp or
            counter suffix), the same "never silently clobber"
            discipline :class:`~jarvis.adapters.audit_storage.JsonFileAuditStorageAdapter`'s
            own append-only file handling already follows for a
            different real file. Two calls with the same
            ``filename_hint`` therefore always produce two distinct
            real files, never one overwriting the other.
        """
        ...
