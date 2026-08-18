"""Unit tests for jarvis.adapters.validation._command.

Nothing is mocked: ``sys.executable`` (the real Python interpreter
running this test) is a reliable, always-available command, matching
``adapters/workspace.py``'s own "no need to fake a real, reliable
local tool" reasoning.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from jarvis.adapters.validation._command import (
    CommandResult,
    apply_candidate_or_report_unverifiable,
    judge_by_exit_code,
    run_command,
)
from jarvis.domain.evidence import Candidate, Verdict
from jarvis.ports.workspace import PatchApplicationFailedError

if TYPE_CHECKING:
    from pathlib import Path


class _FakeWorkspace:
    """A minimal stand-in WorkspacePort that always fails to apply a patch."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def root(self) -> Path:
        return self._root

    def apply_patch(self, patch: str) -> None:
        msg = f"no patch applies cleanly: {patch!r}"
        raise PatchApplicationFailedError(msg)


class _AlwaysAppliesWorkspace:
    """A minimal stand-in WorkspacePort that always applies successfully."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self.applied: list[str] = []

    def root(self) -> Path:
        return self._root

    def apply_patch(self, patch: str) -> None:
        self.applied.append(patch)


def test_apply_candidate_or_report_unverifiable_returns_none_on_success(tmp_path: Path) -> None:
    workspace = _AlwaysAppliesWorkspace(tmp_path)
    candidate = Candidate(author="local", content="a patch")

    result = apply_candidate_or_report_unverifiable(workspace, candidate, "build")

    assert result is None
    assert workspace.applied == ["a patch"]


def test_apply_candidate_or_report_unverifiable_reports_unverifiable_on_failure(
    tmp_path: Path,
) -> None:
    workspace = _FakeWorkspace(tmp_path)
    candidate = Candidate(author="local", content="a bad patch")

    result = apply_candidate_or_report_unverifiable(workspace, candidate, "build")

    assert result is not None
    verdict, evidence = result
    assert verdict == Verdict.UNVERIFIABLE
    assert len(evidence) == 1
    assert "local" in evidence[0].description


def test_judge_by_exit_code_passes_on_zero() -> None:
    result = CommandResult(exit_code=0, stdout="ok", stderr="")

    verdict, evidence = judge_by_exit_code(result, "build", "build")

    assert verdict == Verdict.PASSED
    assert len(evidence) == 1


def test_judge_by_exit_code_fails_on_nonzero() -> None:
    result = CommandResult(exit_code=1, stdout="", stderr="boom")

    verdict, evidence = judge_by_exit_code(result, "build", "build")

    assert verdict == Verdict.FAILED
    assert "boom" in evidence[0].description


_ARBITRARY_NONZERO_EXIT_CODE = 3


async def test_run_command_runs_a_real_subprocess_and_captures_its_exit_code(
    tmp_path: Path,
) -> None:
    result = await run_command((sys.executable, "-c", "import sys; sys.exit(0)"), tmp_path)

    assert result.exit_code == 0


async def test_run_command_captures_a_nonzero_exit_code(tmp_path: Path) -> None:
    command = (sys.executable, "-c", f"import sys; sys.exit({_ARBITRARY_NONZERO_EXIT_CODE})")

    result = await run_command(command, tmp_path)

    assert result.exit_code == _ARBITRARY_NONZERO_EXIT_CODE


async def test_run_command_captures_stdout(tmp_path: Path) -> None:
    command = (sys.executable, "-c", "print('hello from a real subprocess')")

    result = await run_command(command, tmp_path)

    assert "hello from a real subprocess" in result.stdout
