"""project.start / project.status: a thin, backward-compatible wrapper over jarvis.kernel.tasks.

**Folded into ``jarvis.kernel.tasks`` (WP-107), by a real, direct user
decision (2026-09-09)**: this module no longer has its own write path
-- it delegates every real write to ``tasks.py``'s own shared helpers
(:func:`~jarvis.kernel.tasks.write_task_record`), sharing the same
``"kind": "task"`` storage marker tasks.py's own new, more general
``authorize_and_create_task``/``authorize_and_run_task`` use, rather
than maintaining a separate, parallel ``"project_goal"`` convention.

**Every real, already-tested, already-live-verified public contract
this module exposes is unchanged**: ``jarvis project start "<goal>"``/
``jarvis project status "<goal>"`` behave byte-for-byte the same as
before this fold -- same ``ProjectStartOutcome``/``ProjectStatusOutcome``
shapes, same ``decision`` semantics (``planning.run_plan``'s own outer
gate, ``Effect.EXECUTE``/``Tier.CONFIRM`` -- never the task-record
write's own gate), same "a denied outer gate writes nothing" rule, same
``state`` vocabulary (``"completed"``/``"stuck"``). This was a real,
deliberate constraint on the fold, not an oversight: changing any of
these would be a real, user-facing breaking change to a capability
that shipped and was live-smoke-tested against a real local model only
days before this fold.

**One real, stated vocabulary seam this fold leaves open, not hidden**:
``tasks.py``'s own ``authorize_and_create_task``/``authorize_and_run_task``
write ``"failed"`` for the identical real situation this module's own
``authorize_and_start_project`` still writes ``"stuck"`` for -- both
land in the same ``"kind": "task"`` storage, so ``jarvis task list``
will show a mix of the two words for what is, underneath, the same
real outcome, depending on which entry point created the task. Not
unified here: doing so would mean changing this module's own public
``state`` value, the exact breaking change the paragraph above rules
out. Left as a real, visible, explained inconsistency rather than
silently smoothed over -- a future pass may revisit ``project.py``'s
own vocabulary directly, with the user's own sign-off, the same way
this fold itself was.

See ``jarvis.kernel.tasks``'s own module docstring for the real
"stuck" investigation this module's docstring used to carry in full --
preserved there now, not duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.application.planning.executor import PlanValidationError
from jarvis.application.planning.planner import PlanningError
from jarvis.kernel.memory import authorize_and_recall
from jarvis.kernel.planning import authorize_and_run_plan
from jarvis.kernel.tasks import TASK_KIND, write_task_record

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.application.planning.executor import PlanExecutionResult
    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort
    from jarvis.ports.reasoning import ReasoningPort

VALID_PROJECT_STATES = ("completed", "stuck")
"""Unchanged by the fold -- this module's own public vocabulary, distinct
from tasks.py's own "completed"/"failed" (see module docstring)."""

_LIST_QUERY = "project goal state reason plan status stuck completed"
"""Unchanged by the fold."""

_RECALL_LIST_LIMIT = 1000
"""Unchanged by the fold."""


def _state_for_result(result: PlanExecutionResult) -> tuple[str, str | None]:
    """Derive (state, reason) from a granted, attempted plan's own real result.

    This module's own, narrower mapping -- "stuck", not tasks.py's
    "failed" -- preserving the exact public vocabulary
    ``authorize_and_start_project`` has always used. A pure function,
    exercised directly by a unit test against a hand-constructed
    ``PlanExecutionResult``, no real registry/orchestrator involved.
    """
    if not result.aborted:
        return "completed", None
    last = result.step_records[-1]
    reason = (
        f"Plan step {last.step.capability_id.value!r} was denied "
        f"(reasons={last.decision.reasons!r})."
    )
    return "stuck", reason


@dataclass(frozen=True)
class ProjectStartOutcome:
    """The result of one authorize_and_start_project() call. Unchanged by the fold.

    Attributes:
        decision: The ``planning.run_plan`` outer gate's own real
            ``Decision``. If not granted, nothing else in this outcome
            is meaningful -- the planner never ran at all.
        state: ``"completed"`` or ``"stuck"`` if the outer gate was
            granted and the planner was attempted and returned
            normally; ``None`` if the outer gate was denied.
        reason: The real, human-readable reason the plan is stuck, if
            ``state == "stuck"``; ``None`` otherwise.
        record_identifier: The real task record's own identifier
            (usable with ``jarvis task status`` too, since it shares
            tasks.py's own storage), if a status record was
            successfully written; ``None`` otherwise.
    """

    decision: Decision
    state: str | None
    reason: str | None
    record_identifier: str | None


async def authorize_and_start_project(  # noqa: PLR0913 -- one per composition-function pass-through
    goal: str,
    provider: ReasoningPort | None = None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> ProjectStartOutcome:
    """Wire up planning.run_plan for `goal`, then record a real, durable status.

    Sequencing is unchanged by the fold, on purpose: ``planning.run_plan``
    is still called first, directly, so this function's own ``decision``
    keeps carrying exactly its own outer-gate classification, never the
    task-record write's. See module docstring for the real, deliberate
    reason this differs from ``tasks.authorize_and_run_task``'s own,
    newer create-then-run sequencing.

    Raises:
        jarvis.application.planning.planner.PlanningError: If the
            provider's proposed plan fails real, structural validation.
            A real "stuck" status record is written first.
        jarvis.application.planning.executor.PlanValidationError: As
            above.
    """
    try:
        decision, result = await authorize_and_run_plan(
            goal,
            provider,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
        )
    except (PlanningError, PlanValidationError) as exc:
        write_task_record(
            goal,
            "stuck",
            f"{type(exc).__name__}: {exc}",
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
            clock=clock,
            id_port=id_port,
        )
        raise

    if not decision.granted or result is None:
        return ProjectStartOutcome(
            decision=decision, state=None, reason=None, record_identifier=None
        )

    state, reason = _state_for_result(result)
    _write_decision, record_identifier = write_task_record(
        goal,
        state,
        reason,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    return ProjectStartOutcome(
        decision=decision, state=state, reason=reason, record_identifier=record_identifier
    )


@dataclass(frozen=True)
class ProjectStatusOutcome:
    """The result of one authorize_and_get_project_status() call. Unchanged by the fold.

    Attributes:
        decision: The ``Decision`` for the underlying ``memory.retrieve``
            call this reuses -- always granted (``Tier.ALLOW``).
        record: The most recent real task ``MemoryRecord`` whose own
            ``goal`` field exactly matches the queried goal, or
            ``None`` if no such record exists yet.
    """

    decision: Decision
    record: MemoryRecord | None


def authorize_and_get_project_status(  # noqa: PLR0913 -- one per composition-function pass-through
    goal: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> ProjectStatusOutcome:
    """Retrieve the most recent real status record for `goal`. Reuses authorize_and_recall.

    Filters on ``tasks.TASK_KIND`` now (the fold's one, real, shared
    storage marker), not the old, separate ``"project_goal"`` marker --
    see module docstring for the real, honest broad-recall-then-filter
    approximation this shares with ``job_application.list``/
    ``tasks.authorize_and_list_tasks``, unchanged by the fold.
    """
    recall_outcome = authorize_and_recall(
        _LIST_QUERY,
        limit=_RECALL_LIST_LIMIT,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    matching = [
        record
        for record in recall_outcome.records
        if isinstance(record.value.value, dict)
        and record.value.value.get("kind") == TASK_KIND
        and record.value.value.get("goal") == goal
    ]
    latest = max(matching, key=lambda record: record.written_at) if matching else None
    return ProjectStatusOutcome(decision=recall_outcome.decision, record=latest)
