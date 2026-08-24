"""Shared command-running for jarvis.adapters.validation.*.

Not a port and not part of any public API -- factored out so
``build.py``/``static.py``/``runtime.py``/``user_script.py`` don't each
duplicate the same apply-patch-then-run-command-then-judge-by-exit-code
logic. ``pytest_validator.py`` reuses :func:`run_command` too, but
layers its own exit-code interpretation on top (pytest's exit code 5
means "no tests collected," a genuinely different outcome from
``FAILED`` -- see that module's own docstring).

``CommandResult`` itself now lives in ``jarvis.domain.process`` (M3,
WP-45) -- re-exported here under its original name so nothing in M2
had to change. See that module's docstring for why: ``ports.sandbox``
(M3's ``SandboxPort``) needed the identical shape but cannot import
from ``adapters`` under C1's layering, so the definition moved to
``domain`` rather than being duplicated.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import TYPE_CHECKING

from jarvis.domain.evidence import Evidence, EvidenceKind, Verdict
from jarvis.domain.process import CommandResult
from jarvis.ports.workspace import PatchApplicationFailedError

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Candidate
    from jarvis.ports.workspace import WorkspacePort

__all__ = [
    "CommandResult",
    "apply_candidate_or_report_unverifiable",
    "judge_by_exit_code",
    "run_command",
]


def _run_command_sync(command: tuple[str, ...], root: Path) -> CommandResult:
    """Run ``command`` in ``root``, synchronously, and capture its real outcome.

    The one real, untested-by-design piece of this module: it requires
    whatever real tool ``command`` names (a build script, pytest, a
    static analyzer, a user script) to actually be installed and
    runnable, which not every command a caller supplies can be relied
    on to be, in every environment. Each validator's own tests inject
    a real, always-available command (matching
    ``adapters/workspace.py``'s own "``git`` is a reliable CI
    dependency" reasoning) rather than mocking this function.
    """
    result = subprocess.run(  # noqa: S603 -- command is caller-supplied config, not untrusted input
        command, cwd=root, capture_output=True, text=True, check=False
    )
    return CommandResult(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


async def run_command(command: tuple[str, ...], root: Path) -> CommandResult:
    """Run ``command`` in ``root``, off the event loop thread."""
    return await asyncio.to_thread(_run_command_sync, command, root)


def apply_candidate_or_report_unverifiable(
    workspace: WorkspacePort, candidate: Candidate, author: str
) -> tuple[Verdict, tuple[Evidence, ...]] | None:
    """Apply ``candidate.content`` to ``workspace``; report UNVERIFIABLE if it doesn't apply.

    Returns ``None`` on success, meaning the caller should proceed to
    run its real check. Returns a ready-made ``(Verdict, Evidence)``
    result on failure: a patch that does not apply is "no way to judge
    this candidate at all" (:class:`~jarvis.domain.evidence.Verdict.UNVERIFIABLE`'s
    own documented meaning), never a stand-in for ``FAILED`` (ADR-0043).
    """
    try:
        workspace.apply_patch(candidate.content)
    except PatchApplicationFailedError as exc:
        evidence = Evidence(
            kind=EvidenceKind.VALIDATION_RESULT,
            author=author,
            weight=1.0,
            description=f"{candidate.author}'s candidate did not apply as a patch: {exc}",
        )
        return (Verdict.UNVERIFIABLE, (evidence,))
    return None


def judge_by_exit_code(
    result: CommandResult, author: str, command_label: str
) -> tuple[Verdict, tuple[Evidence, ...]]:
    """Report PASSED/FAILED from ``result``'s exit code, with an Evidence describing it."""
    verdict = Verdict.PASSED if result.exit_code == 0 else Verdict.FAILED
    description = (
        f"{command_label} exited {result.exit_code}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    evidence = Evidence(
        kind=EvidenceKind.VALIDATION_RESULT, author=author, weight=1.0, description=description
    )
    return (verdict, (evidence,))
