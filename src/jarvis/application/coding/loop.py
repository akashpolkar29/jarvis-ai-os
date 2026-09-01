"""WP-71: the real coding-loop wrapper, tying WP-70 and WP-73 together (ADR-0055, as amended).

:func:`run_coding_task` is ADR-0055's own "new, minimal orchestration"
piece, built exactly to the shape its "Amendment 2026-09-01" requires:

* Every `Dispatcher.run()` climb runs against a **fresh**
  :class:`~jarvis.application.coding.sandbox_workspace.DisposableWorkspace`
  (WP-73) -- never the real target repository directly, and never the
  same disposable copy reused across climbs (a stale copy could carry
  over an earlier, rejected attempt's own changes).
* The wrapper's own retry budget -- "how many full `Dispatcher.run()`
  climbs may this task attempt" (ADR-0055's own Decision, deliberately
  left unfixed until this work package) -- is a real, finite, checked
  integer, ``DEFAULT_MAX_CLIMBS`` unless a caller overrides it. Once
  exhausted with no `Verdict.PASSED` anywhere, the loop stops and
  returns ``CodingLoopOutcome.RETRY_BUDGET_EXHAUSTED`` -- it never
  loops indefinitely.
* Only once a climb's winning `Attempt` reaches `Verdict.PASSED` does
  this module perform any real write to the **real** target
  repository: every path the winning patch touches
  (:func:`~jarvis.application.coding.patch_paths.touched_paths`) is
  authorized individually through
  :class:`~jarvis.application.coding.writer.CodeWriteAuthorizer`
  (WP-70/ADR-0056) -- if even one touched path is denied (most
  plausibly `Effect.PROTECTED_PATH_WRITE`'s own unconditional DENY
  floor), the *whole* patch is rejected, matching ADR-0056's own
  "reject the whole patch, don't apply it partially" rule. Only if
  every touched path is granted does exactly one real
  `WorkspacePort.apply_patch` call happen, against a real
  `WorkspacePort` pointed at the actual target repository -- never the
  disposable copy.

**Deliberately not fixed here, named rather than silently resolved**:
the real, pre-existing gap ADR-0055's own amendment already named --
multiple candidates tried within one rung (the real `SECOND_PROVIDER`
default tries two providers) are each applied to the *same* disposable
workspace in sequence, with no revert between them. This module does
not attempt to fix that (it would mean modifying `Dispatcher`, which
ADR-0055's own Decision declines to do) -- WP-73's disposable-workspace
mechanism already contains the fallout to a copy that is discarded
after every climb regardless of outcome, which is the real, complete
fix this module's own scope requires.

**No real caller yet, deliberately** -- this module's own real
integration with a kernel composition root (`kernel/coding.py`, WP-72)
is explicitly out of this work package's own scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from jarvis.application.coding.classification import resolve_protected_patterns
from jarvis.application.coding.patch_paths import touched_paths
from jarvis.application.coding.sandbox_workspace import make_disposable_workspace
from jarvis.domain.evidence import Verdict
from jarvis.domain.reasoning import TaskBudget

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from jarvis.application.coding.writer import CodeWriteAuthorizer
    from jarvis.application.reasoning.dispatcher import Dispatcher, DispatchResult
    from jarvis.domain.policy import Decision, PolicyContext
    from jarvis.domain.provenance import Tainted
    from jarvis.ports.sandbox import SandboxPort
    from jarvis.ports.workspace import WorkspacePort

    WorkspaceFactory = Callable[[Path], WorkspacePort]
    DispatcherFactory = Callable[[WorkspacePort], Dispatcher]

DEFAULT_MAX_CLIMBS = 3
"""A real, finite default, not arbitrary: enough for one climb to fail,
one retry to fail on genuinely different grounds (this wrapper's own
task-seeding, see :func:`_seed_next_climb_task`, feeds the prior
failure's real evidence back in, so a second climb is not simply a
repeat of the first), and one final retry -- beyond which further
unattended climbs are diminishing-returns spend against a task that has
already shown it needs a human, not more automatic attempts. Callers
needing a different bound pass `max_climbs` explicitly; this is a
default, not a hard ceiling."""

_LADDER_SPENDING_RUNGS = 2
"""EscalationLadder has three rungs total (DETERMINISTIC_FIX,
SELF_REPAIR, SECOND_PROVIDER), but DETERMINISTIC_FIX is dispatcher.py's
own free, no-op stub ("spending no budget -- nothing real happened",
per that module's own docstring). Only SELF_REPAIR and SECOND_PROVIDER
spend a real TaskBudget unit each, so a limit of exactly 2 is already
sufficient for one climb to reach the ladder's own natural termination
-- never a silent additional constraint beyond what EscalationLadder
already bounds on its own."""


class CodingLoopOutcome(Enum):
    """How one `run_coding_task` call ended -- never silently ambiguous."""

    WRITTEN = "written"
    RETRY_BUDGET_EXHAUSTED = "retry_budget_exhausted"
    WRITE_DENIED = "write_denied"


@dataclass(frozen=True)
class CodingLoopDependencies:
    """The real collaborators one `run_coding_task` call is wired against.

    Grouped separately from :class:`CodingTaskRequest` because these
    are composition-root-level choices (which sandbox, which real
    `WorkspacePort`/`Dispatcher` construction, which authorizer) that
    stay fixed across many different real coding tasks -- unlike
    `CodingTaskRequest`'s own fields, which genuinely vary per call.

    Attributes:
        sandbox: The real `SandboxPort` used to make each climb's own
            disposable workspace copy (WP-73).
        workspace_factory: Builds a real `WorkspacePort` given a root
            directory -- used both for each climb's own disposable
            copy and, exactly once, for the final, authorized write
            against the real target repository.
        dispatcher_factory: Builds a real, fully-wired `Dispatcher`
            given the `WorkspacePort` this climb's own `ValidationPort`
            should apply candidates to. Called once per climb, fresh --
            this wrapper never reuses one `Dispatcher` (or the
            `WorkspacePort` bound to its validator) across climbs.
        authorizer: Authorizes the winning patch's own touched paths
            (WP-70/ADR-0056) before any real write.
    """

    sandbox: SandboxPort
    workspace_factory: WorkspaceFactory
    dispatcher_factory: DispatcherFactory
    authorizer: CodeWriteAuthorizer


@dataclass(frozen=True)
class CodingTaskRequest:
    """One real coding task's own inputs -- everything that varies per `run_coding_task` call.

    Attributes:
        task: The coding task's own text and real provenance.
        target_repo: The real target repository. Never handed to
            `CodingLoopDependencies.dispatcher_factory` directly --
            only a fresh disposable copy of it ever is.
        context: Facts about the environment authorization decisions
            (both `Dispatcher.run()`'s own provider-call authorizations
            and this wrapper's own write authorization) are made in.
        max_climbs: The real, finite ceiling on how many full
            `Dispatcher.run()` climbs this task may attempt. See
            `DEFAULT_MAX_CLIMBS`'s own docstring for why 3 is a
            reasonable default.
        protected_patterns: A real, explicit override for which paths
            are protected -- if `None`, resolved for real from
            `target_repo`'s own detected test convention
            (`resolve_protected_patterns`, ADR-0056's own amendment).
    """

    task: Tainted[str]
    target_repo: Path
    context: PolicyContext
    max_climbs: int = DEFAULT_MAX_CLIMBS
    protected_patterns: tuple[str, ...] | None = None


@dataclass(frozen=True)
class CodingLoopResult:
    """The real outcome of one `run_coding_task` call.

    Attributes:
        outcome: How the run ended.
        climbs: Every real `DispatchResult` from every climb attempted,
            in order -- the "partial results, never silently discarded"
            discipline `DispatchResult` itself already follows,
            inherited here at the wrapper level.
        write_decisions: Every real `Decision` made while authorizing
            the winning patch's own touched paths, in the order
            `touched_paths` returned them -- empty when `outcome` is
            `RETRY_BUDGET_EXHAUSTED` (no winning candidate was ever
            found to authorize), or when the winning patch's own
            touched paths could not even be determined (empty or
            repo-escaping) -- a real, honest "nothing was authorized"
            outcome, not a fabricated denial.
    """

    outcome: CodingLoopOutcome
    climbs: tuple[DispatchResult, ...]
    write_decisions: tuple[Decision, ...] = ()


def _seed_next_climb_task(task: Tainted[str], failed_result: DispatchResult) -> Tainted[str]:
    """Feed a failed climb's own real evidence back into the next climb's task framing.

    ADR-0055's own Decision: a retried climb seeds "its own
    prior_attempts/task framing with the failure just observed."
    `Dispatcher.run()` exposes no `prior_attempts` parameter of its
    own (that is internal to one call's own ladder state) -- the only
    real channel this wrapper has to carry a prior failure's own real
    evidence into the next, fresh `Dispatcher.run()` call is the task
    text itself.
    """
    lines = [
        f"[{attempt.rung.name}] {evidence.description}"
        for attempt in failed_result.attempts
        for evidence in attempt.evidence
    ]
    if not lines:
        return task
    feedback = "\n".join(lines)
    return task.map(lambda text: f"{text}\n\nA previous attempt's own real evidence:\n{feedback}")


def _authorize_patch_write(
    authorizer: CodeWriteAuthorizer,
    repo_root: Path,
    patch: str,
    protected_patterns: tuple[str, ...],
    context: PolicyContext,
) -> tuple[Decision, ...] | None:
    """Authorize every real path `patch` touches; `None` if it cannot even be attempted.

    Returns `None` -- never an empty-but-"granted" tuple -- when
    `touched_paths` finds nothing to authorize (an empty or malformed
    patch) or when any touched path escapes `repo_root` entirely (a
    real path-traversal/symlink-escape attempt, ``patch_paths``'s own
    absolute-path signal): both are real denial conditions, not cases
    where "authorize nothing, so nothing was denied" should be read as
    permission. `code_write_effect_for` itself is never called on an
    escaping absolute path -- it has no notion of "outside the
    repository," and an absolute path checked against a pattern like
    ``tests/*`` would simply never match, silently falling through to
    an ordinary, granted `Effect.CODE_WRITE`.
    """
    paths = touched_paths(patch, repo_root)
    if not paths or any(path.is_absolute() for path in paths):
        return None
    return tuple(authorizer.authorize_write(path, protected_patterns, context) for path in paths)


async def run_coding_task(
    request: CodingTaskRequest, dependencies: CodingLoopDependencies
) -> CodingLoopResult:
    """Run a real coding task, writing to its real target repository only once, if ever.

    Args:
        request: This specific task's own inputs -- see
            `CodingTaskRequest`'s own docstring.
        dependencies: The real collaborators this call is wired
            against -- see `CodingLoopDependencies`'s own docstring.

    Returns:
        A real `CodingLoopResult` -- see its own docstring for what
        each field means for each real outcome.

    Raises:
        UnrecognizedTestConventionError: If `request.protected_patterns`
            is `None` and `request.target_repo`'s own real test
            convention could not be detected
            (`resolve_protected_patterns`'s own documented fail-closed
            behavior). Resolved once, before any climb, so this is
            raised immediately -- never after spending real retry
            budget on a task whose eventual write could never have been
            authorized anyway.
        PatchApplicationFailedError: In the rare, genuine race where
            the winning patch -- already proven to apply cleanly
            against its own disposable copy -- does not apply cleanly
            against `request.target_repo` itself (it changed in the
            meantime). Left to propagate uncaught, deliberately: this
            is a real, distinct failure this wrapper does not silently
            absorb into an ordinary result.
    """
    target_repo = request.target_repo
    resolved_patterns = resolve_protected_patterns(target_repo, request.protected_patterns)

    climbs: list[DispatchResult] = []
    current_task = request.task
    for _ in range(request.max_climbs):
        disposable = make_disposable_workspace(
            dependencies.sandbox, target_repo, dependencies.workspace_factory
        )
        try:
            dispatcher = dependencies.dispatcher_factory(disposable.workspace)
            result = await dispatcher.run(
                current_task, TaskBudget(limit=_LADDER_SPENDING_RUNGS), request.context
            )
        finally:
            disposable.close()
        climbs.append(result)

        winner = result.attempts[-1] if result.attempts else None
        if winner is not None and winner.verdict is Verdict.PASSED:
            write_decisions = _authorize_patch_write(
                dependencies.authorizer,
                target_repo,
                winner.candidate.content,
                resolved_patterns,
                request.context,
            )
            if write_decisions is not None and all(
                decision.granted for decision in write_decisions
            ):
                real_workspace = dependencies.workspace_factory(target_repo)
                real_workspace.apply_patch(winner.candidate.content)
                return CodingLoopResult(CodingLoopOutcome.WRITTEN, tuple(climbs), write_decisions)
            return CodingLoopResult(
                CodingLoopOutcome.WRITE_DENIED, tuple(climbs), write_decisions or ()
            )

        current_task = _seed_next_climb_task(current_task, result)

    return CodingLoopResult(CodingLoopOutcome.RETRY_BUDGET_EXHAUSTED, tuple(climbs))
