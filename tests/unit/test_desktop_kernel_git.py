"""Unit tests for jarvis.kernel.desktop's Git authorize_and_* composition-root functions.

What's mocked and why: a small stub GitPort (with call tracking) is
injected in place of a real GitCliAdapter -- these tests are about the
authorization wiring (which tier grants/denies which call), not about
git itself; GitCliAdapter's own real-git behavior is covered directly
in tests/unit/adapters/test_git.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.kernel.desktop import (
    authorize_and_commit_git,
    authorize_and_create_git_branch,
    authorize_and_force_push_git,
    authorize_and_get_git_status,
    authorize_and_push_git,
)
from jarvis.ports.git import GitCommandFailedError

if TYPE_CHECKING:
    from pathlib import Path

_GRANTED_CALLS = 1


class _StubGit:
    """A GitPort test double that records every call, in order."""

    def __init__(self, *, raise_on_call: bool = False) -> None:
        """Start with an empty call log; optionally raise GitCommandFailedError on any call."""
        self.calls: list[tuple[str, ...]] = []
        self._raise_on_call = raise_on_call

    def _record(self, *args: str) -> None:
        self.calls.append(args)
        if self._raise_on_call:
            msg = "git command failed"
            raise GitCommandFailedError(msg)

    def status(self, repo_dir: Path) -> str:
        """Record a status() call and return fixed real-shaped output."""
        self._record("status", str(repo_dir))
        return "nothing to commit, working tree clean"

    def create_branch(self, repo_dir: Path, branch_name: str) -> None:
        """Record a create_branch() call."""
        self._record("create_branch", str(repo_dir), branch_name)

    def commit(self, repo_dir: Path, message: str) -> None:
        """Record a commit() call."""
        self._record("commit", str(repo_dir), message)

    def push(self, repo_dir: Path, remote: str, branch: str) -> None:
        """Record a push() call."""
        self._record("push", str(repo_dir), remote, branch)

    def force_push(self, repo_dir: Path, remote: str, branch: str) -> None:
        """Record a force_push() call."""
        self._record("force_push", str(repo_dir), remote, branch)


def test_status_is_always_granted_and_returns_real_output(tmp_path: Path) -> None:
    """git.status floors ALLOW -- granted unconditionally, output returned."""
    git = _StubGit()

    outcome = authorize_and_get_git_status(
        tmp_path / "repo",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert outcome.decision.granted is True
    assert outcome.status == "nothing to commit, working tree clean"
    assert git.calls == [("status", str(tmp_path / "repo"))]


def test_granted_create_branch_call_creates_the_branch(tmp_path: Path) -> None:
    """A granted call (physical or remote confirmation, CONFIRM tier) creates the branch."""
    git = _StubGit()
    repo_dir = tmp_path / "repo"

    decision = authorize_and_create_git_branch(
        repo_dir,
        "feature/x",
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert decision.granted is True
    assert git.calls == [("create_branch", str(repo_dir), "feature/x")]


def test_denied_create_branch_call_never_touches_git(tmp_path: Path) -> None:
    """No confirmation at all: CONFIRM-tier git.create_branch is denied, untouched."""
    git = _StubGit()

    decision = authorize_and_create_git_branch(
        tmp_path / "repo",
        "feature/x",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert decision.granted is False
    assert git.calls == []


def test_granted_commit_call_commits_with_the_message(tmp_path: Path) -> None:
    """A granted call commits with exactly the given message."""
    git = _StubGit()
    repo_dir = tmp_path / "repo"

    decision = authorize_and_commit_git(
        repo_dir,
        "a real commit message",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert decision.granted is True
    assert git.calls == [("commit", str(repo_dir), "a real commit message")]


def test_granted_push_call_pushes_remote_and_branch(tmp_path: Path) -> None:
    """A granted call pushes exactly the given remote/branch."""
    git = _StubGit()
    repo_dir = tmp_path / "repo"

    decision = authorize_and_push_git(
        repo_dir,
        "origin",
        "main",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert decision.granted is True
    assert git.calls == [("push", str(repo_dir), "origin", "main")]


def test_denied_push_call_never_touches_git(tmp_path: Path) -> None:
    """No confirmation at all: CONFIRM-tier git.push is denied, untouched."""
    git = _StubGit()

    decision = authorize_and_push_git(
        tmp_path / "repo",
        "origin",
        "main",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert decision.granted is False
    assert git.calls == []


def test_granted_force_push_call_force_pushes_remote_and_branch(tmp_path: Path) -> None:
    """A granted call (physical confirmation) force-pushes exactly the given remote/branch."""
    git = _StubGit()
    repo_dir = tmp_path / "repo"

    decision = authorize_and_force_push_git(
        repo_dir,
        "origin",
        "main",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert decision.granted is True
    assert git.calls == [("force_push", str(repo_dir), "origin", "main")]


def test_denied_force_push_call_never_touches_git(tmp_path: Path) -> None:
    """No physical confirmation: MANUAL_ONLY-tier git.force_push is denied, untouched."""
    git = _StubGit()

    decision = authorize_and_force_push_git(
        tmp_path / "repo",
        "origin",
        "main",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert decision.granted is False
    assert git.calls == []


def test_remote_confirmation_alone_cannot_grant_force_push(tmp_path: Path) -> None:
    """Unlike push's CONFIRM tier, force_push needs physical presence, not just remote."""
    git = _StubGit()

    decision = authorize_and_force_push_git(
        tmp_path / "repo",
        "origin",
        "main",
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=tmp_path / "audit_chain.json",
        git=git,
    )

    assert decision.granted is False
    assert git.calls == []


def test_git_audit_record_is_saved_even_when_force_push_raises(tmp_path: Path) -> None:
    """A granted decision is persisted even if the subsequent real-world action fails."""
    chain_path = tmp_path / "audit_chain.json"
    git = _StubGit(raise_on_call=True)

    with pytest.raises(GitCommandFailedError):
        authorize_and_force_push_git(
            tmp_path / "repo",
            "origin",
            "main",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
            git=git,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain[0].decision.granted is True
