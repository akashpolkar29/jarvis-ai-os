"""The workspace port: the seam between a Candidate's content and real files on disk.

:class:`WorkspacePort` is the one abstract boundary between "some real,
writable working directory" and the validators in
``jarvis.adapters.validation`` that need one -- see ADR-0043 for the
full gap this closes and why it surfaced during WP-33, not earlier.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.workspace`` for the
concrete ``git apply``-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path


class PatchApplicationFailedError(Exception):
    """Raised when a patch does not apply cleanly to a workspace.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: this is
    an adapter-level, real-world operational condition (the patch
    conflicts with the workspace's current content), not a domain-level
    security/policy concern. Defined on the port rather than the
    adapter so that any future, non-``git``-backed implementation of
    this port raises the same, technology-independent type, matching
    :class:`~jarvis.ports.media_player.NoMediaPlayerRunningError`'s
    reasoning.
    """


@runtime_checkable
class WorkspacePort(Protocol):
    """A real, writable working directory a validator can apply a Candidate's patch to."""

    def root(self) -> Path:
        """Return this workspace's real filesystem root directory."""
        ...

    def apply_patch(self, patch: str) -> None:
        """Apply ``patch`` (unified diff text) to the files in this workspace, in place.

        Args:
            patch: Unified diff text, the same shape
                :class:`~jarvis.domain.evidence.Candidate.content` takes
                for any candidate judged against a real workspace
                (ADR-0043).

        Raises:
            PatchApplicationFailedError: If ``patch`` does not apply cleanly.
        """
        ...
