"""Adapter implementing jarvis.ports.validation.ValidationPort as a real runtime-behavior check.

:class:`RuntimeCheckValidator` applies a Candidate's content as a
patch to a real :class:`~jarvis.ports.workspace.WorkspacePort`
(ADR-0043), then runs a real, constructor-supplied command that
actually executes the resulting code, reporting ``PASSED``/``FAILED``
by the command's real exit code. Distinct from
:class:`~jarvis.adapters.validation.build.BuildValidator` (does it
compile/build at all) and
:class:`~jarvis.adapters.validation.static.StaticAnalysisValidator`
(does it lint clean without running): this is "does the program
actually behave correctly when run" -- deliverable #3's own vocabulary
(``m2-reasoning-layer.md`` section 5), even though the mechanics here
(run a command, judge by exit code) are structurally identical to
``build``/``static``/``user_script``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.validation._command import (
    apply_candidate_or_report_unverifiable,
    judge_by_exit_code,
    run_command,
)

if TYPE_CHECKING:
    from jarvis.domain.evidence import Candidate, Evidence, Verdict
    from jarvis.ports.workspace import WorkspacePort

_AUTHOR = "runtime"


class RuntimeCheckValidator:
    """Judges a Candidate by actually running it against a real workspace."""

    def __init__(self, workspace: WorkspacePort, command: tuple[str, ...]) -> None:
        """Store the workspace to run in and the real command that executes the candidate.

        Args:
            workspace: The real, already-prepared working directory
                this validator applies ``candidate.content`` to before
                running it (ADR-0043).
            command: The real command that executes the resulting
                program, e.g. ``("python", "main.py")``. Required, not
                defaulted: unlike a build or a lint pass, there is no
                universal "run this" command -- it is inherently
                task-specific.
        """
        self._workspace = workspace
        self._command = command

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        """Apply ``candidate`` to the workspace and report whether it runs correctly.

        See ``jarvis.ports.validation.ValidationPort.validate`` for the
        full contract this implements.
        """
        unverifiable = apply_candidate_or_report_unverifiable(self._workspace, candidate, _AUTHOR)
        if unverifiable is not None:
            return unverifiable
        result = await run_command(self._command, self._workspace.root())
        return judge_by_exit_code(result, _AUTHOR, "runtime check")
