"""Adapters implementing jarvis.ports.workspace.WorkspacePort.

:class:`LocalWorkspaceAdapter` applies patches to a real directory via
``git apply``, run as a real subprocess. Unlike the D-Bus and
cloud-provider adapters elsewhere in this ring, this one is testable
for real with no mocking: ``git`` is a reliable, ubiquitous CI
dependency (this repo is itself a git checkout), not a live service or
piece of hardware that may or may not be present --
``tests/unit/test_workspace_adapter.py`` exercises a real ``git apply``
against real temp directories, no fakes involved, matching how
``tests/meta/test_import_contracts.py`` already runs the real
``lint-imports`` binary rather than mocking it.

See ADR-0043 for why this port exists at all, and why a workspace need
not itself be a git repository -- confirmed live during that ADR's own
drafting (a real patch, generated in one git-initialized temp
directory, applied cleanly to a second, plain, non-git temp directory
containing only the pre-patch file).
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from jarvis.ports.workspace import PatchApplicationFailedError

if TYPE_CHECKING:
    from pathlib import Path


class LocalWorkspaceAdapter:
    """A real, writable directory on local disk, with patches applied via `git apply`."""

    def __init__(self, root: Path) -> None:
        """Store the real directory this workspace operates on.

        Args:
            root: An existing, real, writable directory. Not required
                to be a git repository itself (ADR-0043).
        """
        self._root = root

    def root(self) -> Path:
        """Return this workspace's real filesystem root directory."""
        return self._root

    def apply_patch(self, patch: str) -> None:
        """Apply ``patch`` via a real ``git apply`` subprocess call, in place.

        Raises:
            PatchApplicationFailedError: If ``git apply`` exits non-zero.
        """
        result = subprocess.run(
            ["git", "apply", "-"],  # noqa: S607 -- resolved via PATH deliberately, matching every
            # other subprocess-based tool invocation in this repo's own tooling (uv, ruff, etc.)
            cwd=self._root,
            input=patch,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            msg = f"git apply failed (exit {result.returncode}): {result.stderr}"
            raise PatchApplicationFailedError(msg)
