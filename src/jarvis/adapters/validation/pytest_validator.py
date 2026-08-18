"""Adapter implementing jarvis.ports.validation.ValidationPort as a real pytest run.

:class:`PytestValidator` applies a Candidate's content as a patch to a
real :class:`~jarvis.ports.workspace.WorkspacePort` (ADR-0043), then
runs real ``pytest`` in it, reporting ``PASSED``/``FAILED`` by its
real exit code -- except exit code 5 ("no tests were collected"),
which is reported ``UNVERIFIABLE`` instead: a validator that found
nothing to run is "no way to judge this candidate at all"
(:class:`~jarvis.domain.evidence.Verdict.UNVERIFIABLE`'s own
documented meaning), not a stand-in for ``FAILED``.

**Named ``pytest_validator.py``, not ``pytest.py``**, a deliberate,
flagged deviation from ``m2-reasoning-layer.md`` section 7's recovered
package layout (``adapters/validation/ - build, pytest, static,
runtime, user_script``), which names this module literally ``pytest``.
Python 3's absolute-import-by-default makes a same-named module safe
in practice (nothing in this file needs to import the real ``pytest``
package, and nothing here is added to ``sys.path`` in a way that would
shadow it) -- confirmed, not merely assumed. The rename is about
clarity for a human reader encountering ``jarvis.adapters.validation.pytest``
in a stack trace or import statement, not a real technical necessity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.validation._command import (
    apply_candidate_or_report_unverifiable,
    judge_by_exit_code,
    run_command,
)
from jarvis.domain.evidence import Evidence, EvidenceKind, Verdict

if TYPE_CHECKING:
    from jarvis.domain.evidence import Candidate
    from jarvis.ports.workspace import WorkspacePort

_AUTHOR = "pytest"
_DEFAULT_COMMAND = ("pytest",)
_NO_TESTS_COLLECTED_EXIT_CODE = 5


class PytestValidator:
    """Judges a Candidate by running real pytest against a real workspace."""

    def __init__(
        self, workspace: WorkspacePort, command: tuple[str, ...] = _DEFAULT_COMMAND
    ) -> None:
        """Store the workspace to test in and the real pytest invocation to use.

        Args:
            workspace: The real, already-prepared working directory
                this validator applies ``candidate.content`` to before
                testing (ADR-0043).
            command: The real command to run, e.g. ``("pytest",)`` or
                ``("pytest", "-x", "tests/unit")``. Defaults to
                ``("pytest",)``.
        """
        self._workspace = workspace
        self._command = command

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        """Apply ``candidate`` to the workspace and report real pytest's outcome.

        See ``jarvis.ports.validation.ValidationPort.validate`` for the
        full contract this implements.
        """
        unverifiable = apply_candidate_or_report_unverifiable(self._workspace, candidate, _AUTHOR)
        if unverifiable is not None:
            return unverifiable
        result = await run_command(self._command, self._workspace.root())
        if result.exit_code == _NO_TESTS_COLLECTED_EXIT_CODE:
            evidence = Evidence(
                kind=EvidenceKind.VALIDATION_RESULT,
                author=_AUTHOR,
                weight=1.0,
                description="pytest collected no tests to run.",
            )
            return (Verdict.UNVERIFIABLE, (evidence,))
        return judge_by_exit_code(result, _AUTHOR, "pytest")
