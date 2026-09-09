"""tasks: a real, persistent Task/TaskStore atop planning.run_plan and the real memory store.

WP-107, built on a real, direct user decision (2026-09-09): fold
``jarvis.kernel.project``'s own logic into this module rather than
maintaining two parallel mechanisms. ``jarvis project start``/``jarvis
project status`` keep their own exact, already-tested, already-live-
verified public contract (``ProjectStartOutcome``/``ProjectStatusOutcome``,
unchanged) -- ``project.py`` becomes a thin wrapper delegating its own
real writes to this module's shared helpers, sharing the same
underlying ``"kind": "task"`` storage marker rather than its own,
separate ``"project_goal"`` one. See ``project.py``'s own module
docstring for the one real, deliberate vocabulary seam this fold
leaves open (project.py's own public ``state`` stays ``"stuck"``, not
``"failed"`` -- a real, stated choice, not an oversight).

**Not a new planning/execution engine**, matching ``project.py``'s own
founding constraint exactly: ``authorize_and_run_task`` wraps the
already-real, already-Accepted ``planning.run_plan`` (ADR-0062)
unmodified. The real, new thing this module adds is a genuine
*create, then run, then look up by id* lifecycle, split into separate
functions on purpose -- not because today's synchronous CLI needs it
split, but because a later background-execution layer (the UI design
proposal's own WP-108) needs to return a real ``task_id`` to a caller
*before* a plan finishes running, which a single, monolithic
"create-and-run" function structurally cannot support. Splitting this
now costs nothing extra today and avoids a real, breaking rework of
this module's own public shape later.

**Real, new storage primitives this module depends on (WP-107)**:
``MemoryWritePort.update_value()`` and ``RetrievalPort.get_by_identifier()``
-- see those ports' own docstrings. Investigated before building:
``SqliteMemoryAdapter.pin()`` already ran a real
``UPDATE ... WHERE identifier = ?``, so the real storage engine already
supported in-place mutation by key; only the public port/composition
surface for updating a record's own *value* (not just its
``expires_at``) was missing. No new storage engine, no schema break.

**Effect/Tier, stated precisely per function**: task creation
(``authorize_and_create_task``) reuses ``memory.write``'s own
``Effect.WRITE_LOCAL``/``Tier.CONFIRM`` (ADR-0049, ``Classification.PUBLIC``
-- a goal string is not SECRET-class data). Every status transition
(``authorize_and_run_task``'s own internal updates) reuses the new
``memory.update`` (the identical classification reasoning, its own
distinct capability id so the audit chain can tell "a new task was
created" apart from "an existing one's status changed"). A by-id
lookup (``authorize_and_get_task``) reuses the new, static
``memory.get`` (``Effect.READ_LOCAL``/``Tier.ALLOW``). A list
(``authorize_and_list_tasks``) reuses ``memory.retrieve`` exactly like
``job_application.list``/the old ``project.status`` did, inheriting
the identical, already-named broad-recall-then-filter approximation
limit for *listing* -- not a new gap, and not present at all in
``authorize_and_get_task``'s own exact, by-id lookup.

**A real, named state not yet reachable, stated honestly, not
silently implied**: ``"waiting_approval"`` exists in
``VALID_TASK_STATUSES`` because a real UI/router design explicitly
wants it (a future planner extension past today's ``Tier.ALLOW``-only
ceiling would need somewhere to land it), but no real code path
produces it yet -- ``application/planning/executor.py``'s own
``Tier.ALLOW``-only v1 restriction means no plan step can pause for
confirmation today (see ``project.py``'s own, unchanged explanation of
this exact finding). Likewise ``"cancelled"``: the state exists for a
future cancel verb this module does not yet implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.application.planning.executor import PlanValidationError
from jarvis.application.planning.planner import PlanningError
from jarvis.kernel.memory import authorize_and_get, authorize_and_recall, authorize_and_remember
from jarvis.kernel.memory import authorize_and_update as _authorize_and_update_memory
from jarvis.kernel.planning import authorize_and_run_plan

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.application.planning.executor import PlanExecutionResult
    from jarvis.domain.memory import MemoryRecord
    from jarvis.domain.policy import Decision
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort
    from jarvis.ports.reasoning import ReasoningPort

TASK_KIND = "task"
"""The real, fixed marker value stored under each task record's own "kind" key,
mirroring ``jarvis.kernel.job_application``'s own identical convention."""

VALID_TASK_STATUSES = (
    "created",
    "running",
    "waiting_approval",
    "completed",
    "failed",
    "cancelled",
)
"""The real, fixed state vocabulary this module writes or reserves -- see the
module docstring for exactly which are reachable today."""

_LIST_QUERY = "task goal status reason plan created running completed failed"
"""A fixed query text chosen to score highly against any task record's own
embedded JSON, mirroring job_application.py's/project.py's identical convention."""

_RECALL_LIST_LIMIT = 1000
"""A generous, fixed top-K passed to the underlying memory.retrieve call -- see
job_application.py's own docstring for the real, honest limitation this
implies for authorize_and_list_tasks. Does not apply to authorize_and_get_task,
which looks up by exact identifier, not by this broad recall."""


def _state_for_result(result: PlanExecutionResult) -> tuple[str, str | None]:
    """Derive (status, reason) from a granted, attempted plan's own real result.

    A pure function, deliberately: exercised directly by a unit test
    against a hand-constructed ``PlanExecutionResult``, with no real
    registry/orchestrator involved -- mirrors ``project.py``'s own,
    now-removed identical helper, kept here as the one real copy.
    """
    if not result.aborted:
        return "completed", None
    last = result.step_records[-1]
    reason = (
        f"Plan step {last.step.capability_id.value!r} was denied "
        f"(reasons={last.decision.reasons!r})."
    )
    return "failed", reason


def write_task_record(  # noqa: PLR0913 -- one per composition-function pass-through
    goal: str,
    status: str,
    reason: str | None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None,
    embedding_port: EmbeddingPort | None,
    clock: ClockPort | None,
    id_port: IdPort | None,
) -> tuple[Decision, str | None]:
    """Write one real, new task record. Reuses authorize_and_remember unmodified.

    A real, shared helper -- used both by this module's own
    :func:`authorize_and_create_task` and by ``project.py``'s thin
    compatibility wrapper, so both entry points write into the same
    ``"kind": "task"`` storage rather than two separate conventions.
    Exported (not a private, underscore-prefixed name) specifically so
    ``project.py`` can call it without reimplementing this logic.

    Returns:
        ``(decision, identifier)`` -- ``identifier`` is the new
        record's real, stable id if granted, ``None`` if denied.
    """
    resolved_clock = clock or SystemClockAdapter()
    now = resolved_clock.now().isoformat()
    record: dict[str, object] = {
        "kind": TASK_KIND,
        "goal": goal,
        "status": status,
        "reason": reason,
        "created_at": now,
        "updated_at": now,
    }
    write_outcome = authorize_and_remember(
        record,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=resolved_clock,
        id_port=id_port,
    )
    return write_outcome.decision, write_outcome.identifier


def update_task_status(  # noqa: PLR0913 -- one per composition-function pass-through
    task_id: str,
    goal: str,
    status: str,
    reason: str | None,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None,
    embedding_port: EmbeddingPort | None,
    clock: ClockPort | None,
    id_port: IdPort | None,
) -> Decision:
    """Update an existing task record's status in place. Reuses authorize_and_update.

    A real, shared helper mirroring :func:`write_task_record`'s own
    "exported for project.py to reuse" reasoning.

    **A real read-modify-write, not a blind overwrite**: ``update_value``
    replaces a record's *entire* stored value, it does not merge --
    writing only ``{"status": ..., "reason": ...}`` would silently
    discard the record's own real ``created_at`` (and anything else
    not repeated here) on every single transition, a real bug caught
    during implementation, not a hypothetical one. This function reads
    the record's own current value first (via the ``Tier.ALLOW``
    ``memory.get``, always granted, so this never itself blocks on
    confirmation), preserves every field it does not itself change,
    and only then writes the merged result.
    """
    resolved_clock = clock or SystemClockAdapter()
    get_outcome = authorize_and_get(
        task_id,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=resolved_clock,
        id_port=id_port,
    )
    existing = get_outcome.record.value.value if get_outcome.record is not None else None
    created_at = (
        existing.get("created_at")
        if isinstance(existing, dict)
        else resolved_clock.now().isoformat()
    )
    record: dict[str, object] = {
        "kind": TASK_KIND,
        "goal": goal,
        "status": status,
        "reason": reason,
        "created_at": created_at,
        "updated_at": resolved_clock.now().isoformat(),
    }
    return _authorize_and_update_memory(
        task_id,
        record,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=resolved_clock,
        id_port=id_port,
    )


@dataclass(frozen=True)
class TaskCreateOutcome:
    """The result of one authorize_and_create_task() call.

    Attributes:
        decision: The real ``memory.write``-shaped ``Decision`` for
            creating this task record.
        task_id: The new task's real, stable identifier, if granted.
            ``None`` if denied -- nothing was written.
    """

    decision: Decision
    task_id: str | None


def authorize_and_create_task(  # noqa: PLR0913 -- one per composition-function pass-through
    goal: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> TaskCreateOutcome:
    """Create a new real task record, status "created". Does not run any plan.

    Deliberately separate from :func:`authorize_and_run_task` -- see
    the module docstring for why a later background-execution layer
    needs this split, not today's synchronous CLI.

    Returns:
        A ``TaskCreateOutcome`` -- see its own docstring.
    """
    decision, task_id = write_task_record(
        goal,
        "created",
        None,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    return TaskCreateOutcome(decision=decision, task_id=task_id)


@dataclass(frozen=True)
class TaskRunOutcome:
    """The result of one authorize_and_run_task() call.

    Attributes:
        decision: The real ``Decision`` that most directly gated this
            specific run attempt -- the ``memory.update`` transition to
            "running" if that alone was denied (nothing further was
            attempted, the task stays at its prior status); otherwise
            ``planning.run_plan``'s own outer-gate ``Decision``.
        status: The task's real, final status after this call
            (``"completed"``/``"failed"``), or ``None`` if the
            transition to "running" was itself denied -- the task's
            own stored status is unchanged in that case.
        reason: The real reason, if ``status == "failed"``; ``None``
            otherwise.
    """

    decision: Decision
    status: str | None
    reason: str | None


async def authorize_and_run_task(  # noqa: PLR0913 -- one per composition-function pass-through
    task_id: str,
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
) -> TaskRunOutcome:
    """Run planning.run_plan for an already-created task, updating its status in place.

    See the module docstring for the exact real, current meaning of
    "failed" this reuses -- not a mid-plan-confirmation-pause signal,
    since that cannot occur given today's Tier.ALLOW-only planner
    ceiling (the identical finding ``project.py`` first made, unchanged
    here).

    Args:
        task_id: A real identifier from a prior, granted
            :func:`authorize_and_create_task` call.
        goal: The same real goal that task was created for.
        provider: As ``authorize_and_run_plan``'s own identical
            parameter.
        physical_confirmation_available: Passed straight through to
            every real decision this call makes.
        remote_confirmation_available: As above.
        chain_path: Where every real decision this call makes lands.
        database_path: Where the real memory store lives. Overridable
            for tests.
        embedding_port: Overridable for tests.
        clock: Defaults to a real ``SystemClockAdapter``.
        id_port: Defaults to a real ``UuidIdAdapter``.

    Returns:
        A ``TaskRunOutcome`` -- see its own docstring.

    Raises:
        jarvis.application.planning.planner.PlanningError: If the
            provider's proposed plan fails real, structural validation.
            The task's own status is updated to "failed" first --
            the caller still sees the same real exception ``jarvis
            plan run`` already surfaces identically.
        jarvis.application.planning.executor.PlanValidationError: As
            above.
    """
    reason: str | None = None
    running_decision = update_task_status(
        task_id,
        goal,
        "running",
        None,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    if not running_decision.granted:
        return TaskRunOutcome(decision=running_decision, status=None, reason=None)

    try:
        plan_decision, result = await authorize_and_run_plan(
            goal,
            provider,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
        )
    except (PlanningError, PlanValidationError) as exc:
        reason = f"{type(exc).__name__}: {exc}"
        update_task_status(
            task_id,
            goal,
            "failed",
            reason,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
            clock=clock,
            id_port=id_port,
        )
        raise

    if not plan_decision.granted or result is None:
        # A real, defensive branch, not currently reachable by any real
        # caller: the "running" transition just above and this call both
        # wrap their own content as Tainted(..., Provenance.user()) with
        # no escalation path, and both are Tier.CONFIRM -- evaluate() is
        # a deterministic function of (tier, confirmation booleans), so
        # given the identical confirmation inputs threaded through both
        # calls, one cannot grant while the other denies. Handled anyway,
        # the same "don't ignore a real field" reasoning project.py's own
        # _state_for_result docstring already gives for its own
        # aborted=True branch.
        reason = f"planning.run_plan denied (reasons={plan_decision.reasons!r})."
        update_task_status(
            task_id,
            goal,
            "failed",
            reason,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
            clock=clock,
            id_port=id_port,
        )
        return TaskRunOutcome(decision=plan_decision, status="failed", reason=reason)

    status, reason = _state_for_result(result)
    update_task_status(
        task_id,
        goal,
        status,
        reason,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    return TaskRunOutcome(decision=plan_decision, status=status, reason=reason)


@dataclass(frozen=True)
class TaskGetOutcome:
    """The result of one authorize_and_get_task() call.

    Attributes:
        decision: The ``memory.get`` ``Decision`` -- always granted
            (``Tier.ALLOW``).
        record: The real, current task record at ``task_id``, or
            ``None`` if no such task exists.
    """

    decision: Decision
    record: MemoryRecord | None


def authorize_and_get_task(  # noqa: PLR0913 -- one per composition-function pass-through
    task_id: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> TaskGetOutcome:
    """Look up one real task by its own identifier. Reuses authorize_and_get (memory.get).

    A real, exact, O(1)-by-key lookup -- not a broad recall-then-filter
    approximation. See ``ports/retrieval.py::RetrievalPort.get_by_identifier``'s
    own docstring for why this is a genuine improvement over the
    ``project.status``/``job_application.list`` pattern, for a caller
    that already has the real identifier (as a UI tracking a task it
    itself created would).

    Returns:
        A ``TaskGetOutcome`` -- see its own docstring.
    """
    get_outcome = authorize_and_get(
        task_id,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    record = get_outcome.record
    if record is not None and (
        not isinstance(record.value.value, dict) or record.value.value.get("kind") != TASK_KIND
    ):
        record = None
    return TaskGetOutcome(decision=get_outcome.decision, record=record)


@dataclass(frozen=True)
class TaskListOutcome:
    """The result of one authorize_and_list_tasks() call.

    Attributes:
        decision: The ``memory.retrieve`` ``Decision`` -- always
            granted (``Tier.ALLOW``).
        records: The real, matching task records, filtered by the
            "kind" marker (and by ``status``, if given). See the
            module docstring for the real, honest broad-recall-then-
            filter limitation this shares with ``job_application.list``.
    """

    decision: Decision
    records: tuple[MemoryRecord, ...]


def authorize_and_list_tasks(  # noqa: PLR0913 -- one per composition-function pass-through
    *,
    status: str | None = None,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> TaskListOutcome:
    """List real task records, optionally filtered by status. Reuses authorize_and_recall.

    Returns:
        A ``TaskListOutcome`` -- see its own docstring.
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
    matching = tuple(
        record
        for record in recall_outcome.records
        if isinstance(record.value.value, dict)
        and record.value.value.get("kind") == TASK_KIND
        and (status is None or record.value.value.get("status") == status)
    )
    return TaskListOutcome(decision=recall_outcome.decision, records=matching)
