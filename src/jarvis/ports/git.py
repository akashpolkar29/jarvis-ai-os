"""The Git port: the seam between an authorized command and the real ``git`` CLI.

:class:`GitPort` is the one abstract boundary between "some real,
local git repository" and the five typed capabilities M3 registers
(``git.status``, ``git.create_branch``, ``git.commit``, ``git.push``,
``git.force_push``). Every method maps to exactly one, non-shell-
interpolated ``git`` CLI invocation -- the same subprocess-with-a-
fixed-argv pattern ``adapters/workspace.py``'s real ``git apply`` call
(ADR-0043) already uses, though this is a new ``GitPort`` rather than
an extension of ``WorkspacePort`` itself: ``WorkspacePort``'s own scope
is deliberately narrowed to "apply a patch for M2 validation"
(ADR-0043), a real but different concern from general-purpose git
porcelain operations on an arbitrary repository.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.git`` for the concrete
CLI-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path


class GitCommandFailedError(Exception):
    """Raised when a real ``git`` CLI invocation exits non-zero.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: an
    adapter-level, real-world operational condition (no changes to
    commit, a non-fast-forward push rejected by the remote, a branch
    that already exists), not a domain-level security/policy concern
    -- matching
    :class:`~jarvis.ports.workspace.PatchApplicationFailedError`'s own
    reasoning.
    """


@runtime_checkable
class GitPort(Protocol):
    """A real, local git repository, reachable via fixed, typed CLI invocations."""

    def status(self, repo_dir: Path) -> str:
        """Return ``git status``'s real, human-readable output for ``repo_dir``, read-only.

        Raises:
            GitCommandFailedError: If the underlying call fails (e.g.
                ``repo_dir`` is not a git repository).
        """
        ...

    def create_branch(self, repo_dir: Path, branch_name: str) -> None:
        """Create and switch to a new branch named ``branch_name`` in ``repo_dir``.

        Raises:
            GitCommandFailedError: If the underlying call fails (e.g.
                ``branch_name`` already exists).
        """
        ...

    def commit(self, repo_dir: Path, message: str) -> None:
        """Commit every already-tracked, modified file in ``repo_dir`` with ``message``.

        Stages only already-tracked files -- new, untracked files are
        not included. Staging new files is real, deliberately
        out-of-scope future work, not built speculatively here (no
        ``git.add`` capability exists in this milestone).

        Raises:
            GitCommandFailedError: If the underlying call fails (e.g.
                nothing to commit).
        """
        ...

    def push(self, repo_dir: Path, remote: str, branch: str) -> None:
        """Push ``branch`` to ``remote`` from ``repo_dir``, ordinary (non-force).

        Raises:
            GitCommandFailedError: If the underlying call fails (e.g.
                a non-fast-forward push rejected by the remote).
        """
        ...

    def force_push(self, repo_dir: Path, remote: str, branch: str) -> None:
        """Force-push ``branch`` to ``remote`` from ``repo_dir``, discarding remote history.

        A separate capability from :meth:`push` -- never a boolean flag
        on it (see ``kernel/desktop.py``'s own docstring for why).

        Raises:
            GitCommandFailedError: If the underlying call fails.
        """
        ...
