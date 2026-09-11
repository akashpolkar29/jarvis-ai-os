"""tasks: a real, persistent Task/TaskStore atop planning.run_plan and the real memory store.

WP-107, built on a real, direct user decision (2026-09-09): fold
``jarvis.kernel.project``'s own logic into this module rather than
maintaining two parallel mechanisms. ``jarvis project start``/``jarvis
project status`` keep their own exact, already-tested, already-live-
verified public contract (``ProjectStartOutcome``/``ProjectStatusOutcome``,
unchanged) -- ``project.py`` becomes a thin wrapper delegating its own
real writes to this module's shared helpers, sharing the same
underlying ``"kind": "task"`` storage marker rather than its own,
separate ``"project_goal"`` one.

**WP-109 (2026-09-09) closed the real vocabulary seam WP-107 first left
open**: the stored, canonical status for "the planner did not complete
successfully" is ``"failed"`` everywhere, for every real caller,
unconditionally -- ``project.py`` no longer writes its own, separate
``"stuck"`` literal to storage. :func:`derive_result_status` (this
module's own, single, now-shared copy -- ``project.py``'s former,
near-duplicate private copy was deleted) is the one real place this
derivation happens. ``project.py``'s own public ``ProjectStartOutcome.state``
and ``jarvis project status``'s own printed CLI text still say
``"stuck"`` -- a real, narrow, deliberate translation at that module's
own public boundary, preserving its already-shipped, already-tested
contract, not a second source of truth for what's actually stored. See
``project.py``'s own module docstring for the full account, including
the one real, explained exception this leaves: a raw
``ProjectStatusOutcome.record`` now faithfully shows ``"failed"``,
since this module will not fabricate a record claiming ``"stuck"`` was
literally persisted when it was not.

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

**WP-111 (2026-09-10): real task-lifecycle events.** ``write_task_record``/
``update_task_status`` -- the two, and only two, real places this
module's own stored task state ever changes -- each now publish a real
``jarvis.domain.events.TaskCreated``/``TaskStatusChanged`` event to an
injected ``EventBus``, but **only after** the underlying write/update
was actually granted. A denied write never publishes anything -- there
is no real state change for an event to describe. ``event_bus``
defaults to ``None``, resolved to a brand-new, empty ``EventBus()`` per
call exactly like ``clock``/``id_port`` already default -- publishing
to a bus nobody subscribed to is a real, harmless no-op, so every
existing caller that does not pass one behaves byte-for-byte as before
this change. A real, separate ``IdPort``/``ClockPort`` resolution from
the one the underlying ``authorize_and_remember``/``authorize_and_update``
call makes internally -- harmless, since generating one extra real,
independent id/timestamp pair has no real side effect to share or
duplicate. See ``jarvis.domain.events``'s own module docstring for the
full reasoning (why exactly two event types, why no lock, why a
subscriber's own failure never propagates here).

**WP-116 (2026-09-11): real, read-only stale-running-task detection.**
WP-113 (2026-09-10) already fixed every *in-process* way a task's own
stored status could be left at ``"running"`` forever -- a plan step's
own real execution exception now always lands the record at
``"failed"`` first. It could not, and does not claim to, fix the
*process-level* case: if the whole JARVIS process hosting a real
``authorize_and_run_task`` call is killed, crashes, or loses power
while a task is genuinely mid-execution, the stored status is left at
``"running"`` permanently -- there is no later code path, in any
process, that ever revisits it. ``authorize_and_get_task``/
``authorize_and_list_tasks`` now compute a real, **read-only**
``stale`` signal using data the store already has (``updated_at``,
added WP-107/109) -- a ``"running"`` task whose ``updated_at`` is
older than :data:`STALE_RUNNING_THRESHOLD_SECONDS` is reported,
honestly, as likely-stale to the caller.

**Deliberately detection only, never automatic recovery, stated
plainly, not silently narrowed**: this module investigated whether to
also *act* on a detected staleness (e.g. auto-transitioning the record
to ``"failed"``) and chose not to -- a real process that is merely
slow (a genuinely long-running coding task, a loaded machine) is
indistinguishable from a genuinely crashed one using only
``updated_at``'s own age; auto-failing the former would be a real,
incorrect, and irreversible loss of a task a human might still be
waiting on. Surfacing the signal and letting a human decide (mirroring
every other ``Tier.MANUAL_ONLY``-adjacent judgment call this codebase
already defers to a real person for) is the safe, honest choice here.
No new capability, no new ``Effect``/``Tier``, no schema change to
what is actually persisted -- ``stale`` is a derived value computed
fresh on every real read, never written to storage.

**WP-117 (2026-09-11): real task cancellation, the first code path to
ever reach the long-reserved ``"cancelled"`` status.** Closes the
other half of the gap WP-116 could only surface, not act on: a human
who sees a task reported ``stale`` (WP-116) -- or who simply changes
their mind about a task still sitting at ``"created"`` -- had no real
way to retire it. :func:`authorize_and_cancel_task` reuses
:func:`authorize_and_get_task` (to read the current record) and
:func:`update_task_status` (the identical ``memory.update`` transition
every other status change already uses, ADR-0063) completely
unmodified -- no new capability, ``Effect``, ``Tier``, or ADR.

**A real, deliberate, narrow semantic, stated precisely so it is never
mistaken for more than it is**: cancelling a ``"running"`` task does
**not** interrupt any real, in-flight execution. There is no real
in-flight execution to interrupt -- ``authorize_and_run_task`` runs
synchronously to completion within a single call (and, via ``jarvis
ui``'s own deliberately single-threaded server, WP-108, no second
request can even be handled concurrently with it). What cancellation
actually does is let a human retire a task's own stored status by
hand, most usefully for exactly the two real situations where no other
code path ever will: a ``"created"`` task the human no longer wants to
run, and a ``"running"`` task whose owning process has already died
(WP-116's own stale signal) and will never update it again on its own.

Only ``"created"`` and ``"running"`` tasks may be cancelled -- a task
already ``"completed"``, ``"failed"``, or ``"cancelled"`` is refused
with a real, honest reason naming its current status, never silently
accepted or silently ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.identifier import UuidIdAdapter
from jarvis.domain.events import EventBus, TaskCreated, TaskStatusChanged
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

STALE_RUNNING_THRESHOLD_SECONDS = 1800.0
"""WP-116 (2026-09-11): how long a task may sit at `"running"` with no further
`updated_at` progress before it is reported as likely stale -- a real, deliberately
generous default, not a guess: the real local-model reasoning timeout
(`adapters/reasoning/local.py::_REQUEST_TIMEOUT_SECONDS`, 120s) bounds one single
call; even a multi-step plan retrying several times comfortably fits well inside
this 30-minute margin in the ordinary case. Detection only -- see module docstring's
own WP-116 section for why this never mutates a task's own stored status."""


def derive_result_status(result: PlanExecutionResult) -> tuple[str, str | None]:
    """Derive (status, reason) from a granted, attempted plan's own real result.

    A pure function, deliberately: exercised directly by a unit test
    against a hand-constructed ``PlanExecutionResult``, with no real
    registry/orchestrator involved. **The one, real, canonical copy
    (WP-109)** -- ``project.py`` no longer keeps its own, separate,
    near-duplicate private copy; it imports this function directly and
    translates its canonical ``"completed"``/``"failed"`` result to its
    own public ``"completed"``/``"stuck"`` vocabulary only at its own
    return boundary, never by re-deriving the status a second way.
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
    event_bus: EventBus | None = None,
) -> tuple[Decision, str | None]:
    """Write one real, new task record. Reuses authorize_and_remember unmodified.

    A real, shared helper -- used both by this module's own
    :func:`authorize_and_create_task` and by ``project.py``'s thin
    compatibility wrapper, so both entry points write into the same
    ``"kind": "task"`` storage rather than two separate conventions.
    Exported (not a private, underscore-prefixed name) specifically so
    ``project.py`` can call it without reimplementing this logic.

    Publishes a real ``TaskCreated`` to ``event_bus`` -- but only if
    ``authorize_and_remember`` actually granted the write (see module
    docstring: no event for a state change that did not happen).

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
    if write_outcome.decision.granted and write_outcome.identifier is not None:
        (event_bus or EventBus()).publish(
            TaskCreated(
                event_id=(id_port or UuidIdAdapter()).new_id(),
                task_id=write_outcome.identifier,
                goal=goal,
                status=status,
                timestamp=now,
            )
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
    event_bus: EventBus | None = None,
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

    Publishes a real ``TaskStatusChanged`` to ``event_bus`` -- again,
    only if the update was actually granted, and carrying the real
    ``previous_status`` this same read already retrieved (never a
    second, separate guess at what it must have been).
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
    raw_previous_status = existing.get("status") if isinstance(existing, dict) else None
    previous_status = raw_previous_status if isinstance(raw_previous_status, str) else None
    created_at = (
        existing.get("created_at")
        if isinstance(existing, dict)
        else resolved_clock.now().isoformat()
    )
    now = resolved_clock.now().isoformat()
    record: dict[str, object] = {
        "kind": TASK_KIND,
        "goal": goal,
        "status": status,
        "reason": reason,
        "created_at": created_at,
        "updated_at": now,
    }
    update_decision = _authorize_and_update_memory(
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
    if update_decision.granted:
        (event_bus or EventBus()).publish(
            TaskStatusChanged(
                event_id=(id_port or UuidIdAdapter()).new_id(),
                task_id=task_id,
                goal=goal,
                previous_status=previous_status,
                new_status=status,
                reason=reason,
                timestamp=now,
            )
        )
    return update_decision


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
    event_bus: EventBus | None = None,
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
        event_bus=event_bus,
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
    event_bus: EventBus | None = None,
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
        event_bus: A real, shared ``EventBus`` every real status
            transition this call makes publishes to, if supplied.
            Defaults to a fresh, empty ``EventBus()`` per transition
            (a harmless no-op) -- see module docstring.

    Returns:
        A ``TaskRunOutcome`` -- see its own docstring.

    Raises:
        Exception: Any real exception raised either by plan validation
            (``jarvis.application.planning.planner.PlanningError``,
            ``jarvis.application.planning.executor.PlanValidationError``)
            or by a plan step's own wrapped ``authorize_and_*`` call
            during real execution (e.g. ``PathOutsideAllowedScopeError``,
            ``GitCommandFailedError``, ``OSError``, ``sqlite3.Error`` --
            see ``kernel.capability_dispatch.PLAN_STEP_EXECUTORS`` for
            which capabilities are currently wired and what each one
            can really raise). In every case the task's own status is
            updated to "failed" first, with the real exception's own
            type and message as the stored reason -- the caller still
            sees the identical, unmodified exception re-raised
            afterward, exactly like ``jarvis plan run``/``jarvis task
            run`` already do for the two plan-validation cases. WP-113
            (2026-09-10) widened this from a narrow
            ``(PlanningError, PlanValidationError)`` catch specifically
            because a step-execution exception previously propagated
            all the way out of this function uncaught, leaving the
            task's own stored status at "running" permanently -- see
            this module's own docstring for the full account.
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
        event_bus=event_bus,
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
    except Exception as exc:
        # WP-113: deliberately broad, not narrowed to (PlanningError,
        # PlanValidationError) -- execute_plan's own per-step loop calls
        # into a plan-step executor's real, wrapped authorize_and_* call
        # (kernel.capability_dispatch.PLAN_STEP_EXECUTORS), which can
        # raise its own real exception (PathOutsideAllowedScopeError,
        # GitCommandFailedError, OSError, sqlite3.Error, ...) that a
        # narrower catch here would let propagate uncaught, leaving the
        # task's own stored status at "running" permanently -- the real
        # bug this widening fixes. Re-raised unmodified below, so the
        # caller still sees the identical, real exception either way.
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
            event_bus=event_bus,
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
        # derive_result_status docstring already gives for its own
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
            event_bus=event_bus,
        )
        return TaskRunOutcome(decision=plan_decision, status="failed", reason=reason)

    status, reason = derive_result_status(result)
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
        event_bus=event_bus,
    )
    return TaskRunOutcome(decision=plan_decision, status=status, reason=reason)


def _is_stale_running(data: object, now: datetime) -> bool:
    """Return whether a real task record's own dict is `"running"` and stale (WP-116).

    A pure function of the record's own already-stored content plus a
    real, caller-supplied `now` -- never calls a wall clock itself
    (this module is not `domain`, but still follows the identical
    discipline everywhere it reasonably can). `False` for anything
    that isn't a well-formed task dict at all, or whose own
    `updated_at` cannot be parsed -- a malformed record is a separate,
    real problem this function does not paper over by guessing.
    """
    if not isinstance(data, dict) or data.get("status") != "running":
        return False
    raw_updated_at = data.get("updated_at")
    if not isinstance(raw_updated_at, str):
        return False
    try:
        updated_at = datetime.fromisoformat(raw_updated_at)
    except ValueError:
        return False
    return (now - updated_at).total_seconds() > STALE_RUNNING_THRESHOLD_SECONDS


@dataclass(frozen=True)
class TaskGetOutcome:
    """The result of one authorize_and_get_task() call.

    Attributes:
        decision: The ``memory.get`` ``Decision`` -- always granted
            (``Tier.ALLOW``).
        record: The real, current task record at ``task_id``, or
            ``None`` if no such task exists.
        stale: WP-116, real, read-only, computed fresh on every call,
            never persisted. ``True`` only if ``record`` is real,
            currently ``"running"``, and has not been updated in over
            :data:`STALE_RUNNING_THRESHOLD_SECONDS` -- a real, honest
            signal that the process running it may have crashed, never
            an automatic verdict (see module docstring's own WP-116
            section for why this is detection only).
    """

    decision: Decision
    record: MemoryRecord | None
    stale: bool = False


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
    stale = record is not None and _is_stale_running(
        record.value.value, (clock or SystemClockAdapter()).now()
    )
    return TaskGetOutcome(decision=get_outcome.decision, record=record, stale=stale)


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
        stale_task_ids: WP-116, real, read-only, computed fresh on
            every call, never persisted -- the identifiers (matching
            ``records[i].identifier``) of every returned record that
            is currently ``"running"`` and has not been updated in
            over :data:`STALE_RUNNING_THRESHOLD_SECONDS`. A separate
            field, not a mutation of ``records`` itself, so the raw,
            real, stored record content stays exactly what was stored
            -- see module docstring's own WP-116 section.
    """

    decision: Decision
    records: tuple[MemoryRecord, ...]
    stale_task_ids: frozenset[str] = frozenset()


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
    now = (clock or SystemClockAdapter()).now()
    stale_task_ids = frozenset(
        record.identifier for record in matching if _is_stale_running(record.value.value, now)
    )
    return TaskListOutcome(
        decision=recall_outcome.decision, records=matching, stale_task_ids=stale_task_ids
    )


_CANCELLABLE_STATUSES = frozenset({"created", "running"})
"""The only two real statuses authorize_and_cancel_task() will transition out of.

A task already `"completed"`/`"failed"`/`"cancelled"` is a terminal,
already-decided outcome -- cancelling it would not reflect anything
real, so it is refused rather than silently accepted.
"""


@dataclass(frozen=True)
class TaskCancelOutcome:
    """The result of one authorize_and_cancel_task() call.

    Attributes:
        decision: The most directly gating real ``Decision``. If no
            task was found, or its current status is not cancellable,
            this is the ``memory.get`` lookup's own ``Decision``
            (always granted, ``Tier.ALLOW``) -- nothing past that
            point was attempted. Otherwise it is the real
            ``memory.update`` ``Decision`` for the actual "cancelled"
            transition.
        cancelled: ``True`` only if a real write transitioning the
            task to ``"cancelled"`` was attempted and granted.
        reason: A real, human-readable explanation whenever
            ``cancelled`` is ``False`` -- "no such task," or naming
            the task's own current, non-cancellable status, or that
            the transition itself was not authorized. ``None`` when
            ``cancelled`` is ``True``.
    """

    decision: Decision
    cancelled: bool
    reason: str | None


def authorize_and_cancel_task(  # noqa: PLR0913 -- one per composition-function pass-through
    task_id: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
    event_bus: EventBus | None = None,
) -> TaskCancelOutcome:
    """Cancel a real task currently "created" or "running" (WP-117).

    See the module docstring's own WP-117 section for the real,
    deliberate limit this has: cancelling a `"running"` task does not
    interrupt any in-flight execution (there is none to interrupt in
    this architecture) -- it only retires a task's own stored status
    for a human who has decided not to run it, or given up waiting on
    one whose owning process has already died.

    Returns:
        A ``TaskCancelOutcome`` -- see its own docstring.
    """
    get_outcome = authorize_and_get_task(
        task_id,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    if get_outcome.record is None:
        return TaskCancelOutcome(
            decision=get_outcome.decision,
            cancelled=False,
            reason="No task found for this identifier.",
        )
    data = get_outcome.record.value.value
    current_status = data.get("status") if isinstance(data, dict) else None
    goal = data.get("goal") if isinstance(data, dict) else None
    if current_status not in _CANCELLABLE_STATUSES or not isinstance(goal, str):
        return TaskCancelOutcome(
            decision=get_outcome.decision,
            cancelled=False,
            reason=f"Task is already {current_status!r} and cannot be cancelled.",
        )
    update_decision = update_task_status(
        task_id,
        goal,
        "cancelled",
        None,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
        event_bus=event_bus,
    )
    return TaskCancelOutcome(
        decision=update_decision,
        cancelled=update_decision.granted,
        reason=None if update_decision.granted else "Cancellation was not authorized.",
    )
