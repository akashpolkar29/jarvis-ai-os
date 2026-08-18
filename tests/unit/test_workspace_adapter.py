"""Unit tests for jarvis.adapters.workspace.LocalWorkspaceAdapter.

Unlike the D-Bus and network adapters elsewhere in this ring, nothing
here is mocked: ``git`` is a reliable CI dependency, so every test runs
a real ``git apply`` subprocess against a real temporary directory --
see this adapter's own module docstring for why that is safe to rely
on here specifically.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.ports.workspace import PatchApplicationFailedError

if TYPE_CHECKING:
    from pathlib import Path


def test_root_returns_the_constructor_supplied_path(tmp_path: Path) -> None:
    adapter = LocalWorkspaceAdapter(tmp_path)

    assert adapter.root() == tmp_path


def test_apply_patch_changes_a_file_on_disk(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    target.write_text("line1\nline2\nline3\n", encoding="utf-8")

    patch = (
        "--- a/hello.txt\n"
        "+++ b/hello.txt\n"
        "@@ -1,3 +1,3 @@\n"
        " line1\n"
        "-line2\n"
        "+line2-changed\n"
        " line3\n"
    )

    adapter = LocalWorkspaceAdapter(tmp_path)
    adapter.apply_patch(patch)

    assert target.read_text(encoding="utf-8") == "line1\nline2-changed\nline3\n"


def test_apply_patch_works_on_a_directory_that_is_not_a_git_repository(tmp_path: Path) -> None:
    """The workspace itself need not be a git repo -- ADR-0043's own live-verified finding."""
    assert not (tmp_path / ".git").exists()
    (tmp_path / "hello.txt").write_text("original\n", encoding="utf-8")

    patch = "--- a/hello.txt\n+++ b/hello.txt\n@@ -1 +1 @@\n-original\n+patched\n"

    adapter = LocalWorkspaceAdapter(tmp_path)
    adapter.apply_patch(patch)

    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "patched\n"


def test_apply_patch_raises_patch_application_failed_on_a_conflicting_patch(tmp_path: Path) -> None:
    conflicting = "does not match the patch context at all\n"
    (tmp_path / "hello.txt").write_text(conflicting, encoding="utf-8")

    patch = "--- a/hello.txt\n+++ b/hello.txt\n@@ -1 +1 @@\n-line2\n+line2-changed\n"

    adapter = LocalWorkspaceAdapter(tmp_path)

    with pytest.raises(PatchApplicationFailedError):
        adapter.apply_patch(patch)


def test_apply_patch_raises_on_a_target_file_that_does_not_exist(tmp_path: Path) -> None:
    patch = "--- a/does_not_exist.txt\n+++ b/does_not_exist.txt\n@@ -1 +1 @@\n-a\n+b\n"

    adapter = LocalWorkspaceAdapter(tmp_path)

    with pytest.raises(PatchApplicationFailedError):
        adapter.apply_patch(patch)


def test_git_is_available_in_this_environment() -> None:
    """A sanity check the other tests here silently assume -- fails loudly if git is missing."""
    result = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
