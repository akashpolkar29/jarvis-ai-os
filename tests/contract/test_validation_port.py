"""Contract test: adapters must structurally satisfy jarvis.ports.validation.ValidationPort.

WP-33 added the five real adapters (``BuildValidator``,
``PytestValidator``, ``StaticAnalysisValidator``,
``RuntimeCheckValidator``, ``UserScriptValidator``) this file's own
WP-31 docstring said should land here "alongside (not necessarily
replacing)" the fake-based tests below -- both now coexist, matching
how ``tests/contract/test_reasoning_port.py`` handled the same
situation in WP-32.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.adapters.validation import (
    BuildValidator,
    PytestValidator,
    RuntimeCheckValidator,
    StaticAnalysisValidator,
    UserScriptValidator,
)
from jarvis.adapters.workspace import LocalWorkspaceAdapter
from jarvis.domain.evidence import Candidate, Evidence, EvidenceKind, Verdict
from jarvis.ports.validation import ValidationPort

_SOME_COMMAND = ("true",)


class _FakeValidator:
    """A minimal stand-in ValidationPort, satisfying the Protocol's shape only."""

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        """Always report PASSED, ignoring ``candidate`` -- a fake, not a real check."""
        evidence = Evidence(
            kind=EvidenceKind.VALIDATION_RESULT,
            author="fake-validator",
            weight=1.0,
            description=f"Fake validation of {candidate.author}'s candidate.",
        )
        return (Verdict.PASSED, (evidence,))


def test_fake_validator_satisfies_validation_port() -> None:
    """_FakeValidator is structurally a ValidationPort."""
    validator = _FakeValidator()

    assert isinstance(validator, ValidationPort)


def test_an_object_missing_validate_does_not_satisfy_validation_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAValidator:
        """Deliberately lacks validate()."""

    assert isinstance(NotAValidator(), ValidationPort) is False


def test_build_validator_satisfies_validation_port() -> None:
    """BuildValidator is structurally a ValidationPort.

    Safe to construct with a nonexistent path here: __init__ does zero
    I/O (it only stores the workspace and command), so no real
    directory or subprocess is required.
    """
    workspace = LocalWorkspaceAdapter(Path("/nonexistent"))

    assert isinstance(BuildValidator(workspace), ValidationPort)


def test_pytest_validator_satisfies_validation_port() -> None:
    """PytestValidator is structurally a ValidationPort."""
    workspace = LocalWorkspaceAdapter(Path("/nonexistent"))

    assert isinstance(PytestValidator(workspace), ValidationPort)


def test_static_analysis_validator_satisfies_validation_port() -> None:
    """StaticAnalysisValidator is structurally a ValidationPort."""
    workspace = LocalWorkspaceAdapter(Path("/nonexistent"))

    assert isinstance(StaticAnalysisValidator(workspace), ValidationPort)


def test_runtime_check_validator_satisfies_validation_port() -> None:
    """RuntimeCheckValidator is structurally a ValidationPort."""
    workspace = LocalWorkspaceAdapter(Path("/nonexistent"))

    assert isinstance(RuntimeCheckValidator(workspace, _SOME_COMMAND), ValidationPort)


def test_user_script_validator_satisfies_validation_port() -> None:
    """UserScriptValidator is structurally a ValidationPort."""
    workspace = LocalWorkspaceAdapter(Path("/nonexistent"))

    assert isinstance(UserScriptValidator(workspace, _SOME_COMMAND), ValidationPort)
