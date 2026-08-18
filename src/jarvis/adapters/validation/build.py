"""Adapter implementing jarvis.ports.validation.ValidationPort as a real build check.

:class:`BuildValidator` applies a Candidate's content as a patch to a
real :class:`~jarvis.ports.workspace.WorkspacePort` (ADR-0043), then
runs a real, constructor-supplied build command in it, reporting
``PASSED``/``FAILED`` by the command's real exit code.
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

_AUTHOR = "build"
_DEFAULT_COMMAND = ("make",)


class BuildValidator:
    """Judges a Candidate by running a real build command against a real workspace."""

    def __init__(
        self, workspace: WorkspacePort, command: tuple[str, ...] = _DEFAULT_COMMAND
    ) -> None:
        """Store the workspace to build in and the real command to build with.

        Args:
            workspace: The real, already-prepared working directory
                this validator applies ``candidate.content`` to before
                building (ADR-0043).
            command: The real build command to run, e.g. ``("make",)``
                or ``("npm", "run", "build")``. Defaults to ``("make",)``
                -- real, deployment-specific build tooling is not
                decided further than that here.
        """
        self._workspace = workspace
        self._command = command

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        """Apply ``candidate`` to the workspace and report whether the real build passes.

        See ``jarvis.ports.validation.ValidationPort.validate`` for the
        full contract this implements.
        """
        unverifiable = apply_candidate_or_report_unverifiable(self._workspace, candidate, _AUTHOR)
        if unverifiable is not None:
            return unverifiable
        result = await run_command(self._command, self._workspace.root())
        return judge_by_exit_code(result, _AUTHOR, "build")
