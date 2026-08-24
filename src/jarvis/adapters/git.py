"""Adapters implementing jarvis.ports.git.GitPort.

:class:`GitCliAdapter` runs real ``git`` CLI subprocess calls, one
fixed, non-shell-interpolated invocation per method -- the same
"test for real, no mocking" pattern ``adapters/workspace.py``'s
``LocalWorkspaceAdapter`` already established: ``git`` is a reliable,
ubiquitous CI dependency (this repo is itself a git checkout), not a
live service that may or may not be present. No injectable seam here,
deliberately, matching ``LocalWorkspaceAdapter``'s own shape exactly:
the point of this adapter is to run real git commands, tested for real.

**Never exercised against a real, non-scratch repository during this
pass**: this run's own tests exercise every method here for real, but
always against a fresh, disposable temp-directory repository (and a
disposable local bare "remote" for ``push``/``force_push``) created
solely for that test -- never this repository's own history, per this
run's hard-stop rule against real git commit/push against real repos.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from jarvis.ports.git import GitCommandFailedError

if TYPE_CHECKING:
    from pathlib import Path


def _run_git(repo_dir: Path, argv: tuple[str, ...]) -> str:
    """Run a real ``git`` subprocess call in ``repo_dir`` and return its stdout, stripped.

    Raises:
        GitCommandFailedError: If the command exits non-zero.
    """
    # "git" resolved via PATH deliberately, matching adapters/workspace.py's identical
    # precedent; argv beyond it is a fixed subcommand plus typed arguments, never
    # caller-supplied shell text.
    result = subprocess.run(  # noqa: S603
        ("git", *argv),  # noqa: S607
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"git {' '.join(argv)} failed (exit {result.returncode}): {result.stderr}"
        raise GitCommandFailedError(msg)
    return result.stdout.strip()


class GitCliAdapter:
    """Runs real, typed ``git`` CLI subprocess calls -- no shell interpolation, ever."""

    def status(self, repo_dir: Path) -> str:
        """Return ``git status``'s real output for ``repo_dir``."""
        return _run_git(repo_dir, ("status",))

    def create_branch(self, repo_dir: Path, branch_name: str) -> None:
        """Create and switch to ``branch_name`` via a real ``git checkout -b`` call."""
        _run_git(repo_dir, ("checkout", "-b", branch_name))

    def commit(self, repo_dir: Path, message: str) -> None:
        """Commit every already-tracked, modified file via a real ``git commit -a -m`` call."""
        _run_git(repo_dir, ("commit", "-a", "-m", message))

    def push(self, repo_dir: Path, remote: str, branch: str) -> None:
        """Push ``branch`` to ``remote`` via a real ``git push`` call."""
        _run_git(repo_dir, ("push", remote, branch))

    def force_push(self, repo_dir: Path, remote: str, branch: str) -> None:
        """Force-push ``branch`` to ``remote`` via a real ``git push --force`` call."""
        _run_git(repo_dir, ("push", "--force", remote, branch))
