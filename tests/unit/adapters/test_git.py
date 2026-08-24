"""Unit tests for jarvis.adapters.git.GitCliAdapter.

Nothing here is mocked: matching ``tests/unit/test_workspace_adapter.py``'s
own precedent exactly, ``git`` is a reliable CI dependency, so every
test runs real ``git`` subprocess calls -- against a fresh, disposable
temp-directory repository (``tmp_path``) created solely for that test,
never this repository's own history. ``push``/``force_push`` are
exercised against a second, disposable local *bare* repository
(``tmp_path``-backed too) standing in for a remote -- fully real,
fully contained, no network involved.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.git import GitCliAdapter
from jarvis.ports.git import GitCommandFailedError

if TYPE_CHECKING:
    from pathlib import Path


def _run(repo_dir: Path, *args: str) -> None:
    """Run a real git setup command in repo_dir, failing loudly if it doesn't succeed."""
    result = subprocess.run(
        ["git", *args], cwd=repo_dir, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def _init_repo(repo_dir: Path) -> None:
    """Initialize a real, empty git repo at repo_dir with a local commit identity configured."""
    repo_dir.mkdir(exist_ok=True)
    _run(repo_dir, "init")
    _run(repo_dir, "config", "user.email", "test@example.com")
    _run(repo_dir, "config", "user.name", "Test")


def _init_repo_with_one_commit(repo_dir: Path) -> None:
    """Initialize a real git repo with one tracked file and one real commit."""
    _init_repo(repo_dir)
    (repo_dir / "hello.txt").write_text("original\n", encoding="utf-8")
    _run(repo_dir, "add", "hello.txt")
    _run(repo_dir, "commit", "-m", "initial commit")


def _init_repo_with_two_commits(repo_dir: Path) -> None:
    """Initialize a real git repo with two real commits, so HEAD~1 resolves to a real parent."""
    _init_repo(repo_dir)
    (repo_dir / "hello.txt").write_text("root\n", encoding="utf-8")
    _run(repo_dir, "add", "hello.txt")
    _run(repo_dir, "commit", "-m", "root commit")
    (repo_dir / "hello.txt").write_text("original\n", encoding="utf-8")
    _run(repo_dir, "add", "hello.txt")
    _run(repo_dir, "commit", "-m", "initial commit")


def test_status_returns_real_output_for_a_clean_repo(tmp_path: Path) -> None:
    """status() returns git status's real output -- a clean tree mentions "nothing to commit"."""
    _init_repo_with_one_commit(tmp_path)
    adapter = GitCliAdapter()

    result = adapter.status(tmp_path)

    assert "nothing to commit" in result


def test_status_reflects_a_real_modified_file(tmp_path: Path) -> None:
    """status() reflects a genuinely modified, tracked file."""
    _init_repo_with_one_commit(tmp_path)
    (tmp_path / "hello.txt").write_text("changed\n", encoding="utf-8")
    adapter = GitCliAdapter()

    result = adapter.status(tmp_path)

    assert "hello.txt" in result


def test_status_raises_on_a_directory_that_is_not_a_git_repository(tmp_path: Path) -> None:
    """A real, non-git directory raises GitCommandFailedError, not a silent empty result."""
    adapter = GitCliAdapter()

    with pytest.raises(GitCommandFailedError):
        adapter.status(tmp_path)


def test_create_branch_really_creates_and_switches(tmp_path: Path) -> None:
    """create_branch() really creates a new branch and switches the real repo to it."""
    _init_repo_with_one_commit(tmp_path)
    adapter = GitCliAdapter()

    adapter.create_branch(tmp_path, "feature/real-branch")

    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == "feature/real-branch"


def test_create_branch_raises_when_the_branch_already_exists(tmp_path: Path) -> None:
    """A real duplicate-branch attempt raises GitCommandFailedError."""
    _init_repo_with_one_commit(tmp_path)
    adapter = GitCliAdapter()
    adapter.create_branch(tmp_path, "feature/dup")
    _run(tmp_path, "checkout", "-")  # back to whatever branch was checked out before

    with pytest.raises(GitCommandFailedError):
        adapter.create_branch(tmp_path, "feature/dup")


def test_commit_really_commits_a_modified_tracked_file(tmp_path: Path) -> None:
    """commit() really stages already-tracked, modified files and commits them."""
    _init_repo_with_one_commit(tmp_path)
    (tmp_path / "hello.txt").write_text("changed\n", encoding="utf-8")
    adapter = GitCliAdapter()

    adapter.commit(tmp_path, "a real commit message")

    log = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert log.stdout.strip() == "a real commit message"
    status = adapter.status(tmp_path)
    assert "nothing to commit" in status


def test_commit_does_not_stage_a_new_untracked_file(tmp_path: Path) -> None:
    """commit()'s real, documented scope limit: new, untracked files are not included."""
    _init_repo_with_one_commit(tmp_path)
    (tmp_path / "new_file.txt").write_text("brand new\n", encoding="utf-8")
    adapter = GitCliAdapter()

    with pytest.raises(GitCommandFailedError):
        adapter.commit(tmp_path, "nothing tracked changed")


def test_commit_raises_when_there_is_nothing_to_commit(tmp_path: Path) -> None:
    """A real commit attempt against a clean tree raises GitCommandFailedError."""
    _init_repo_with_one_commit(tmp_path)
    adapter = GitCliAdapter()

    with pytest.raises(GitCommandFailedError):
        adapter.commit(tmp_path, "nothing changed")


def _init_bare_remote(remote_dir: Path) -> None:
    """Create a real, local, disposable bare repo to stand in for a remote."""
    remote_dir.mkdir()
    _run(remote_dir, "init", "--bare")


def test_push_really_pushes_to_a_real_local_remote(tmp_path: Path) -> None:
    """push() really updates a real (local, disposable) remote's branch."""
    repo_dir = tmp_path / "repo"
    remote_dir = tmp_path / "remote.git"
    _init_repo_with_one_commit(repo_dir)
    _init_bare_remote(remote_dir)
    _run(repo_dir, "remote", "add", "origin", str(remote_dir))
    _run(repo_dir, "branch", "-M", "main")
    adapter = GitCliAdapter()

    adapter.push(repo_dir, "origin", "main")

    remote_log = subprocess.run(
        ["git", "log", "-1", "--format=%s", "main"],
        cwd=remote_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert remote_log.stdout.strip() == "initial commit"


def test_push_raises_on_a_non_fast_forward_push(tmp_path: Path) -> None:
    """A real, genuinely rejected non-fast-forward push raises GitCommandFailedError."""
    repo_dir = tmp_path / "repo"
    remote_dir = tmp_path / "remote.git"
    _init_repo_with_two_commits(repo_dir)
    _init_bare_remote(remote_dir)
    _run(repo_dir, "remote", "add", "origin", str(remote_dir))
    _run(repo_dir, "branch", "-M", "main")
    adapter = GitCliAdapter()
    adapter.push(repo_dir, "origin", "main")
    # Real history divergence: reset local main back before the pushed commit, then
    # make a different commit -- origin/main can no longer fast-forward to this.
    _run(repo_dir, "reset", "--hard", "HEAD~1")
    (repo_dir / "hello.txt").write_text("diverged\n", encoding="utf-8")
    _run(repo_dir, "add", "hello.txt")
    _run(repo_dir, "commit", "-m", "diverged commit")

    with pytest.raises(GitCommandFailedError):
        adapter.push(repo_dir, "origin", "main")


def test_force_push_really_overwrites_diverged_remote_history(tmp_path: Path) -> None:
    """force_push() really succeeds where an ordinary push would be rejected."""
    repo_dir = tmp_path / "repo"
    remote_dir = tmp_path / "remote.git"
    _init_repo_with_two_commits(repo_dir)
    _init_bare_remote(remote_dir)
    _run(repo_dir, "remote", "add", "origin", str(remote_dir))
    _run(repo_dir, "branch", "-M", "main")
    adapter = GitCliAdapter()
    adapter.push(repo_dir, "origin", "main")
    _run(repo_dir, "reset", "--hard", "HEAD~1")
    (repo_dir / "hello.txt").write_text("diverged\n", encoding="utf-8")
    _run(repo_dir, "add", "hello.txt")
    _run(repo_dir, "commit", "-m", "diverged commit")

    adapter.force_push(repo_dir, "origin", "main")

    remote_log = subprocess.run(
        ["git", "log", "-1", "--format=%s", "main"],
        cwd=remote_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert remote_log.stdout.strip() == "diverged commit"


def test_git_is_available_in_this_environment() -> None:
    """A sanity check the other tests here silently assume -- fails loudly if git is missing."""
    result = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
