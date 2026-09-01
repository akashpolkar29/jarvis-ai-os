"""Unit tests for jarvis.application.coding.sandbox_workspace.

The copy itself runs against a real ``BwrapSandboxAdapter``, no
mocking -- matching ``tests/unit/adapters/test_sandbox.py``'s own "bwrap
is a reliable CI dependency, test for real" precedent. Only the
failure-path test (a command that cannot possibly succeed) uses a
minimal fake ``SandboxPort``, where a real sandboxed failure would add
nothing a fake doesn't already prove.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from jarvis.adapters.sandbox import BwrapSandboxAdapter
from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.application.coding.sandbox_workspace import (
    DisposableWorkspaceCopyFailedError,
    make_disposable_workspace,
)
from jarvis.domain.process import CommandResult


class _FailingSandbox:
    """A minimal, test-local SandboxPort whose run() always reports a real, fixed failure."""

    def run(
        self,
        command: tuple[str, ...],
        *,
        bind_paths: tuple[Path, ...] = (),
        allow_network: bool = False,
    ) -> CommandResult:
        del command, bind_paths, allow_network
        return CommandResult(exit_code=1, stdout="", stderr="cp: real, fixed failure")

    def launch(
        self,
        command: tuple[str, ...],
        *,
        bind_paths: tuple[Path, ...] = (),
        allow_network: bool = False,
        allow_display: bool = False,
    ) -> int:
        raise NotImplementedError


def test_make_disposable_workspace_copies_real_files_from_the_target_repo(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "widget.py").write_text("ORIGINAL\n", encoding="utf-8")

    disposable = make_disposable_workspace(BwrapSandboxAdapter(), target, LocalWorkspaceAdapter)
    try:
        copied = disposable.workspace.root() / "widget.py"
        assert copied.read_text(encoding="utf-8") == "ORIGINAL\n"
    finally:
        disposable.close()


def test_make_disposable_workspace_never_returns_the_target_root_itself(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "widget.py").write_text("ORIGINAL\n", encoding="utf-8")

    disposable = make_disposable_workspace(BwrapSandboxAdapter(), target, LocalWorkspaceAdapter)
    try:
        assert disposable.workspace.root() != target
        assert disposable.workspace.root().resolve() != target.resolve()
    finally:
        disposable.close()


def test_writing_to_the_disposable_copy_never_touches_the_real_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "widget.py").write_text("ORIGINAL\n", encoding="utf-8")

    disposable = make_disposable_workspace(BwrapSandboxAdapter(), target, LocalWorkspaceAdapter)
    try:
        (disposable.workspace.root() / "widget.py").write_text("CHANGED\n", encoding="utf-8")
        assert (target / "widget.py").read_text(encoding="utf-8") == "ORIGINAL\n"
    finally:
        disposable.close()


def test_close_removes_the_real_disposable_directory(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "widget.py").write_text("ORIGINAL\n", encoding="utf-8")

    disposable = make_disposable_workspace(BwrapSandboxAdapter(), target, LocalWorkspaceAdapter)
    root = disposable.workspace.root()
    assert root.exists()

    disposable.close()

    assert not root.exists()


def test_close_is_safe_to_call_more_than_once(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "widget.py").write_text("ORIGINAL\n", encoding="utf-8")

    disposable = make_disposable_workspace(BwrapSandboxAdapter(), target, LocalWorkspaceAdapter)
    disposable.close()
    disposable.close()  # must not raise


def test_context_manager_removes_the_directory_on_exit_even_if_the_body_raises(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "widget.py").write_text("ORIGINAL\n", encoding="utf-8")

    root: Path | None = None
    with (
        pytest.raises(RuntimeError, match="deliberate"),
        make_disposable_workspace(
            BwrapSandboxAdapter(), target, LocalWorkspaceAdapter
        ) as disposable,
    ):
        root = disposable.workspace.root()
        assert root.exists()
        msg = "deliberate"
        raise RuntimeError(msg)

    assert root is not None
    assert not root.exists()


def test_copy_failure_raises_and_cleans_up_the_disposable_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    created: list[Path] = []
    real_mkdtemp = tempfile.mkdtemp

    def _tracking_mkdtemp(prefix: str) -> str:
        made: str = real_mkdtemp(prefix=prefix)
        created.append(Path(made))
        return made

    monkeypatch.setattr(tempfile, "mkdtemp", _tracking_mkdtemp)

    with pytest.raises(DisposableWorkspaceCopyFailedError, match="real, fixed failure"):
        make_disposable_workspace(_FailingSandbox(), target, LocalWorkspaceAdapter)

    assert len(created) == 1
    assert not created[0].exists()
