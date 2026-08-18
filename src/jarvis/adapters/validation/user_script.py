"""Adapter implementing jarvis.ports.validation.ValidationPort as a real user-supplied check.

:class:`UserScriptValidator` applies a Candidate's content as a patch
to a real :class:`~jarvis.ports.workspace.WorkspacePort` (ADR-0043),
then runs a real, constructor-supplied user script in it, reporting
``PASSED``/``FAILED`` by the script's real exit code. Distinct from
:class:`~jarvis.adapters.validation.runtime.RuntimeCheckValidator` in
purpose, not mechanics: this is an arbitrary, human-authored gate (a
custom acceptance check, a manual QA script) rather than "run the
candidate itself" -- deliverable #3's own vocabulary
(``m2-reasoning-layer.md`` section 5).
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

_AUTHOR = "user_script"


class UserScriptValidator:
    """Judges a Candidate by running a real, user-supplied script against a real workspace."""

    def __init__(self, workspace: WorkspacePort, command: tuple[str, ...]) -> None:
        """Store the workspace to check in and the real user-supplied command to run.

        Args:
            workspace: The real, already-prepared working directory
                this validator applies ``candidate.content`` to before
                running the script (ADR-0043).
            command: The real, user-supplied command to run. Required,
                not defaulted: by definition, this validator's whole
                purpose is running whatever a human supplied.
        """
        self._workspace = workspace
        self._command = command

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        """Apply ``candidate`` to the workspace and report the user script's real outcome.

        See ``jarvis.ports.validation.ValidationPort.validate`` for the
        full contract this implements.
        """
        unverifiable = apply_candidate_or_report_unverifiable(self._workspace, candidate, _AUTHOR)
        if unverifiable is not None:
            return unverifiable
        result = await run_command(self._command, self._workspace.root())
        return judge_by_exit_code(result, _AUTHOR, "user script")
