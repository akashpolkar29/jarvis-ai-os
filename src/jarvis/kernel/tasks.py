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

**WP-118 (2026-09-11): closing the one real gap WP-117 itself opened.**
Before WP-117, no task could ever reach ``"cancelled"``, so
``authorize_and_run_task``'s own unconditional transition to
``"running"`` (it never checked the task's prior status) was harmless
-- there was no status it could silently override that mattered. The
moment ``"cancelled"`` became real and reachable, that same
unconditional behavior became a real bug: calling ``jarvis task run``
directly on a task a human had just cancelled would silently resume
it, completely undoing the cancellation with no real signal that
anything unusual had happened. ``authorize_and_run_task`` now checks
the task's current stored status first (the identical, unmodified
``memory.get`` lookup ``authorize_and_cancel_task`` already uses) and
refuses to run a ``"cancelled"`` task, returning its real current
status and a reason, never attempting the "running" transition or any
plan execution. Deliberately narrow: a ``"completed"``/``"failed"``
task is still freely re-runnable -- that is legitimate retry behavior,
not a gap, and changing it was out of this work package's own scope.

**WP-120 (2026-09-11): a real, process-safe claim mechanism, closing
the one gap every prior work package on this module left open.**
Before this, the "created" -> "running" transition
``authorize_and_run_task`` makes was a blind, unconditional
read-then-write -- nothing stopped two genuinely independent callers
(two direct ``jarvis task run`` invocations, or, with WP-120's own new
``jarvis.kernel.worker``, two real worker processes) from both reading
the same "created" task, both transitioning it to "running," and both
then actually running ``planning.run_plan`` concurrently for the same
task id. This was always a real, reachable architectural hazard, not
merely a hypothetical one made worse by adding a worker -- a worker
only makes the race *likely*, not newly *possible*.

The fix: this one transition now passes ``atomic=True`` to
:func:`update_task_status`, which performs a real compare-and-swap
(:func:`~jarvis.kernel.memory.authorize_and_compare_and_update`, backed
by :meth:`~jarvis.adapters.memory.SqliteMemoryAdapter.compare_and_update_value`'s
own ``BEGIN IMMEDIATE``-based, empirically cross-process-verified
lock) against the exact value this same call just read. If another
real writer already changed the task's status in the meantime, the
compare-and-swap fails cleanly -- ``authorize_and_run_task`` detects
this (``claimed=False`` on the returned ``TaskRunOutcome``), re-reads
the task's own real, current status, and returns it honestly, having
attempted no plan execution and no further transition whatsoever.
Every other real status transition in this module (running ->
completed/failed, created/running -> cancelled) is deliberately left
as the original, unconditional blind write -- only the one transition
where a genuine claim race is possible needed this; widening it
everywhere would have been unjustified scope, not a safety
requirement (see ``docs/architecture/wp120-background-worker.md`` for
the full reasoning on why this is the narrowest correct fix).

**WP-121 (2026-09-11): safe, explicit task retry + durable execution
history.** Two real, additive features atop everything above.

*Execution history*: every real task record now carries a real
``attempts`` list -- empty for a brand-new task (:func:`write_task_record`),
appended to by :func:`update_task_status` exactly once per real,
*concluded* execution attempt (a "running" -> ``"completed"``/
``"failed"``/``"cancelled"`` transition, never the "start running"
transition itself, since that attempt has not concluded yet). Each
entry records its own ``attempt`` number, ``started_at`` (the prior
record's own ``updated_at`` -- the exact real moment it last became
"running", never re-derived or guessed), ``ended_at``, the concluding
``status``, and ``reason``. **Real backward compatibility, not
assumed**: a task record written before this work package existed has
no ``"attempts"`` key at all -- ``existing.get("attempts")`` defaults
to ``[]`` for it, so its very next transition gains a real, correct
first attempt entry rather than raising or silently losing history
that never existed. The live, current record's own ``reason`` is
still overwritten on every transition (unchanged) -- ``attempts`` is
where a *concluded* attempt's own failure reason survives a later
retry overwriting the live field.

*Explicit retry*: :func:`authorize_and_retry_task` (`jarvis task retry
<task_id>`) permits retrying only a task currently ``"failed"`` --
deliberately narrower than ``jarvis task run``'s own, unchanged
"completed"/"failed" re-run permissiveness (see
:data:`_RETRYABLE_STATUSES`'s own docstring). Once permitted, it
delegates directly to the exact, unmodified :func:`authorize_and_run_task`
for the actual execution -- no new authorization concept, no second
execution path. This means a retry is automatically protected by the
exact same, real, process-safe claim mechanism WP-120 already built:
two independent processes both retrying the same failed task race on
the identical "failed" -> "running" compare-and-swap, and the same
"running" -> "running" refusal closes the identical gap for a slower,
later racer, with zero new locking code.

**WP-122 (2026-09-12): deterministic one-time local scheduling.**
Closes the gap between "a task exists, persisted" and "a task runs at
a future time with nobody typing a command at that exact moment" --
the smallest safe foundation, not a general-purpose workflow engine,
not recurrence, not natural-language scheduling (all explicitly out of
scope for this work package).

**No new task status, deliberately** -- a scheduled task stays
``"created"`` the whole time it is waiting; only one new, additive,
backward-compatible field, ``scheduled_at`` (a real, UTC-canonicalized
ISO-8601 string, or ``None``), is added to the stored record.
``None`` (the default for every task created before or after this
work package, and for every legacy record with no such key at all)
means exactly what "created" already meant before this work package
existed -- immediately eligible, unchanged. A non-``None``
``scheduled_at`` means "eligible once this real time has passed,"
checked by :func:`jarvis.kernel.worker.run_pending_tasks_once` against
a real ``ClockPort.now()`` -- never a second status, never a second
discovery mechanism, just one more, optional filter on top of the
exact same ``"created"`` status the worker already discovers.
:func:`authorize_and_schedule_task` (`jarvis task schedule <task_id>
--at <iso8601>`) is the one, new, explicit write that sets it; only a
task still ``"created"`` may be scheduled (see
:data:`_SCHEDULABLE_STATUSES`'s own docstring for why ``"failed"`` is
deliberately excluded -- scheduling is not a way to auto-retry).
Calling it again on the same still-``"created"`` task simply
overwrites the prior ``scheduled_at`` -- a real, deliberate substitute
for a separate "unschedule" verb, which this work package investigated
and did not find a genuine, independent need for (see
:func:`authorize_and_schedule_task`'s own docstring).

**Timezone policy**: :func:`_parse_aware_iso8601` rejects a naive
(timezone-less) input outright, the identical real correctness fix
``adapters/calendar.py`` already established (10-phase combined pass,
Phase 10) for the identical real hazard -- a naive timestamp would
make "is this due yet" ambiguous against an always-UTC
``ClockPort.now()``. The accepted value is canonicalized to UTC before
storage, so every later due-time comparison is a plain ``<=`` between
two UTC-aware datetimes, never a conversion.

**Missed-schedule policy, the simplest safe deterministic choice**: a
``scheduled_at`` at or before the current real time is due, full stop
-- whether that is because the worker just happens to be checking
promptly, or because the worker was not running at all for hours and
only just started. No catch-up logic, no "this was supposed to run
three times while the laptop was asleep" accounting -- recurrence is
explicitly out of this work package's own scope, so there is only ever
one real due moment to miss or not miss, and a task already executed
once naturally leaves ``"created"`` status, so the worker structurally
cannot re-discover and re-run it on a later pass.

**Duplicate-execution protection, entirely inherited, zero new locking
code**: :func:`jarvis.kernel.worker.run_pending_tasks_once`'s own
due-time check is a pure, local, read-only filter -- it decides which
discovered tasks to *attempt*, nothing more. The actual claim (the
real "created" -> "running" compare-and-swap) is the exact, unmodified
WP-120 mechanism inside :func:`authorize_and_run_task` itself. Two
independent worker processes racing on the same due, scheduled task
both pass the identical due-time check (a benign, idempotent read) but
only one of them wins the real CAS -- proven directly by a new,
dedicated ``multiprocessing.Process`` test mirroring WP-120's/WP-121's
own headline proof exactly.

**Cancellation, retry, and authorization are all completely
unaffected, by construction**: a cancelled task's own status is
``"cancelled"``, not ``"created"``, so the worker's own, unchanged
status filter already excludes it -- no scheduling-specific
cancellation check was needed or added. Retrying a scheduled-then-
failed task (WP-121) delegates directly to ``authorize_and_run_task``,
which does not consult ``scheduled_at`` at all -- an explicit retry
always runs immediately, exactly like retrying any other failed task,
with the original ``scheduled_at`` preserved in the record purely as
historical information. Scheduling a task is never itself
authorization for what it will later do -- the real
``physical_confirmation_available``/``remote_confirmation_available``
flags passed to the *later*, separate worker-triggered
``authorize_and_run_task`` call are what gate that run, completely
independent of whatever flags were used (or not used) at schedule
time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.identifier import UuidIdAdapter
from jarvis.domain.events import EventBus, TaskCreated, TaskStatusChanged
from jarvis.kernel.memory import authorize_and_compare_and_update as _authorize_and_cas_memory
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
        "attempts": [],
        "scheduled_at": None,
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
    atomic: bool = False,
) -> tuple[Decision, bool]:
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
    and only then writes the merged result. **WP-122**: this is why
    ``scheduled_at`` (see :func:`authorize_and_schedule_task`) survives
    every status transition unchanged -- running, retrying, or
    cancelling a scheduled task never silently drops its own real
    scheduled time, the exact same reasoning that already protects
    ``created_at``/``attempts``.

    **WP-120: ``atomic``, deliberately opt-in, default ``False``.**
    When ``True``, the write is a real compare-and-swap
    (:func:`~jarvis.kernel.memory.authorize_and_compare_and_update`)
    against the exact value this same call just read, rather than a
    blind overwrite -- for the one real caller that needs to detect
    "did I win a race against another writer" (the "created" ->
    "running" claim transition, see
    :func:`authorize_and_run_task`'s own docstring). Every other
    caller leaves this at its default, unchanged, blind-write
    behavior -- this is additive, not a change to any existing
    transition's own real semantics.

    Returns:
        ``(decision, applied)``. ``applied`` is ``True`` iff the write
        actually landed -- for the default, non-atomic path this is
        simply ``decision.granted`` (a granted blind write always
        succeeds); for the atomic path it additionally requires the
        real compare-and-swap to have matched, so a granted-but-lost-
        the-race attempt reports ``applied=False`` without raising.

    Publishes a real ``TaskStatusChanged`` to ``event_bus`` -- only if
    the write was both granted *and* actually applied, carrying the
    real ``previous_status`` this same read already retrieved (never a
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
    existing_attempts = existing.get("attempts") if isinstance(existing, dict) else None
    attempts = list(existing_attempts) if isinstance(existing_attempts, list) else []
    existing_scheduled_at = existing.get("scheduled_at") if isinstance(existing, dict) else None
    scheduled_at = existing_scheduled_at if isinstance(existing_scheduled_at, str) else None
    if previous_status == "running" and status in ("completed", "failed", "cancelled"):
        # WP-121: one real, concluded execution attempt -- appended only when
        # a "running" task reaches a terminal status, never for the
        # "created"/"failed"/"completed" -> "running" transition itself (that
        # one is still *in progress*, nothing to append yet). `started_at` is
        # the existing record's own `updated_at` -- the exact real moment it
        # last transitioned *to* "running" -- not re-derived or guessed.
        started_at = existing.get("updated_at") if isinstance(existing, dict) else None
        attempts = [
            *attempts,
            {
                "attempt": len(attempts) + 1,
                "started_at": started_at,
                "ended_at": now,
                "status": status,
                "reason": reason,
            },
        ]
    record: dict[str, object] = {
        "kind": TASK_KIND,
        "goal": goal,
        "status": status,
        "reason": reason,
        "created_at": created_at,
        "updated_at": now,
        "attempts": attempts,
        "scheduled_at": scheduled_at,
    }
    if atomic:
        if existing is None:
            # Nothing to atomically swap against -- the most honest real
            # answer is "this attempt did not apply," never a blind write.
            return get_outcome.decision, False
        if status == "running" and previous_status == "running":
            # WP-120's own real, decisive CI finding: a CAS alone is not
            # enough. A second, later caller that reads the task as
            # already "running" (because an earlier claimant already won)
            # would otherwise have its OWN "running" write's own
            # `expected_value` trivially match what is actually stored --
            # nothing else changed in between its own read and its own
            # write -- so the compare-and-swap itself would correctly
            # succeed, even though "running" -> "running" is never a
            # valid transition for ANY real caller to make. This check
            # closes that gap directly: a "running" claim attempt is
            # refused outright, with no CAS write even attempted, the
            # moment the most recently read prior status is itself
            # already "running" -- regardless of whether that status is
            # fresh or stale. See the module docstring's own WP-120
            # section for the full account of the real, multi-attempt CI
            # investigation this closes.
            return get_outcome.decision, False
        cas_outcome = _authorize_and_cas_memory(
            task_id,
            existing,
            record,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
            clock=resolved_clock,
            id_port=id_port,
        )
        update_decision = cas_outcome.decision
        applied = cas_outcome.applied
    else:
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
        applied = update_decision.granted
    if applied:
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
    return update_decision, applied


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
            specific run attempt. Four real cases (WP-118 added the
            first, WP-120 the fourth): the ``memory.get`` lookup's own
            ``Decision`` (always granted) if the task is currently
            ``"cancelled"`` and nothing further was attempted; the
            ``memory.update``/compare-and-swap transition to "running"
            if that alone was denied (nothing further was attempted,
            the task stays at its prior status); the same transition's
            own ``Decision`` if it was granted but lost a real race to
            another claimant (WP-120 -- see ``claimed``); otherwise
            ``planning.run_plan``'s own outer-gate ``Decision``.
        status: The task's real, final status after this call
            (``"completed"``/``"failed"``), ``"cancelled"`` if the
            task was already cancelled and this run was refused
            (WP-118, its own stored status unchanged), the task's own
            real, current, freshly-re-read status if this attempt lost
            a claim race (WP-120 -- never fabricated), or ``None`` if
            the transition to "running" was itself denied -- the
            task's own stored status is unchanged in that case too.
        reason: The real reason, if ``status == "failed"``,
            ``status == "cancelled"`` (WP-118), or this attempt lost a
            claim race (WP-120); ``None`` otherwise.
        claimed: WP-120. ``True`` only if *this* call's own "running"
            transition was the one that actually landed -- i.e. this
            call genuinely went on to attempt (and, separately,
            succeed or fail at) running the plan. ``False`` if the
            task was already cancelled, the transition was denied by
            policy, or another real claimant won the race first. A
            worker (or any caller) processing many tasks uses this to
            tell "I executed this one" apart from "someone else
            already had it."
    """

    decision: Decision
    status: str | None
    reason: str | None
    claimed: bool = True


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
    if get_outcome.record is not None:
        existing_data = get_outcome.record.value.value
        current_status = existing_data.get("status") if isinstance(existing_data, dict) else None
        if current_status == "cancelled":
            # WP-118: a cancelled task must never be silently resumed by a
            # direct `run` call -- see the module docstring's own WP-118
            # section. Nothing past this point is attempted: no "running"
            # transition, no plan execution.
            return TaskRunOutcome(
                decision=get_outcome.decision,
                status="cancelled",
                reason="Task was cancelled; run refuses to resume a cancelled task.",
                claimed=False,
            )

    reason: str | None = None
    running_decision, claimed = update_task_status(
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
        atomic=True,
    )
    if not running_decision.granted:
        return TaskRunOutcome(decision=running_decision, status=None, reason=None, claimed=False)
    if not claimed:
        # WP-120: granted, but a real, independent claimant (another worker,
        # or a direct `jarvis task run`) already changed this task's status
        # between our read and this attempt -- re-read and report its real,
        # current status honestly, never a fabricated sentinel. Nothing past
        # this point is attempted: no plan execution, no further transition.
        refreshed = authorize_and_get_task(
            task_id,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=chain_path,
            database_path=database_path,
            embedding_port=embedding_port,
            clock=clock,
            id_port=id_port,
        )
        refreshed_data = refreshed.record.value.value if refreshed.record is not None else None
        current_status = refreshed_data.get("status") if isinstance(refreshed_data, dict) else None
        return TaskRunOutcome(
            decision=running_decision,
            status=current_status if isinstance(current_status, str) else None,
            reason=(
                "This task was already claimed or changed by another process; "
                "this run attempt did not execute anything."
            ),
            claimed=False,
        )

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


def is_task_due(data: object, now: datetime) -> bool:
    """Whether a real `"created"` task record's own `scheduled_at` (if any) has passed (WP-122).

    `True` for every task with no real `scheduled_at` string at all --
    the existing, unchanged, immediately-eligible behavior WP-122
    established. `True` once a real, stored `scheduled_at` is at or
    before `now`. A malformed, unparseable `scheduled_at` (should
    never happen through `authorize_and_schedule_task`'s own real
    validation, but a hand-edited or legacy-adjacent record is not
    assumed impossible) is treated as due -- an honest, logged warning
    is the caller's own responsibility, not this pure predicate's.

    **WP-124**: moved here from `kernel.worker` (which now imports
    this exact, unmodified function instead of defining its own copy)
    so `authorize_and_get_task`/`authorize_and_list_tasks` can also
    derive a real, read-only "due" signal for display -- the same
    "compute fresh, never persist, expose via the outcome" shape
    :func:`_is_stale_running` already established for WP-116.
    """
    if not isinstance(data, dict):
        return True
    scheduled_at = data.get("scheduled_at")
    if not isinstance(scheduled_at, str):
        return True
    try:
        parsed = datetime.fromisoformat(scheduled_at)
    except ValueError:
        return True
    return parsed <= now


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
        due: WP-124, real, read-only, computed fresh on every call,
            never persisted. ``True`` only if ``record`` is real,
            currently ``"created"``, has a real ``scheduled_at``, and
            that time has passed a real ``ClockPort.now()`` --
            meaningless (left ``False``) whenever ``scheduled_at`` is
            absent or the task is no longer ``"created"``; callers
            should gate display on ``scheduled_at is not None`` first,
            exactly as they already do for ``stale``.
    """

    decision: Decision
    record: MemoryRecord | None
    stale: bool = False
    due: bool = False


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
    now = (clock or SystemClockAdapter()).now()
    stale = record is not None and _is_stale_running(record.value.value, now)
    data = record.value.value if record is not None else None
    is_created_and_scheduled = (
        isinstance(data, dict)
        and data.get("status") == "created"
        and isinstance(data.get("scheduled_at"), str)
    )
    due = bool(is_created_and_scheduled) and is_task_due(data, now)
    return TaskGetOutcome(decision=get_outcome.decision, record=record, stale=stale, due=due)


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
        due_task_ids: WP-124, real, read-only, computed fresh on every
            call, never persisted -- the identifiers of every returned
            record that is currently ``"created"``, has a real
            ``scheduled_at``, and that time has passed. Mirrors
            ``stale_task_ids``'s own shape exactly.
    """

    decision: Decision
    records: tuple[MemoryRecord, ...]
    stale_task_ids: frozenset[str] = frozenset()
    due_task_ids: frozenset[str] = frozenset()


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
    due_task_ids = frozenset(
        record.identifier
        for record in matching
        if isinstance(record.value.value, dict)
        and record.value.value.get("status") == "created"
        and isinstance(record.value.value.get("scheduled_at"), str)
        and is_task_due(record.value.value, now)
    )
    return TaskListOutcome(
        decision=recall_outcome.decision,
        records=matching,
        stale_task_ids=stale_task_ids,
        due_task_ids=due_task_ids,
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
    resolved_clock = clock or SystemClockAdapter()
    now = resolved_clock.now().isoformat()
    assert isinstance(data, dict)  # noqa: S101 -- narrowed by the isinstance check above
    existing_attempts = data.get("attempts")
    attempts = list(existing_attempts) if isinstance(existing_attempts, list) else []
    if current_status == "running":
        # Mirrors update_task_status's own identical attempts-append condition --
        # concluding a genuinely "running" span, never for "created" -> "cancelled".
        attempts = [
            *attempts,
            {
                "attempt": len(attempts) + 1,
                "started_at": data.get("updated_at"),
                "ended_at": now,
                "status": "cancelled",
                "reason": None,
            },
        ]
    new_value: dict[str, object] = {
        **data,
        "status": "cancelled",
        "reason": None,
        "updated_at": now,
        "attempts": attempts,
    }
    cas_outcome = _authorize_and_cas_memory(
        task_id,
        data,
        new_value,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=resolved_clock,
        id_port=id_port,
    )
    if not cas_outcome.applied:
        return TaskCancelOutcome(
            decision=cas_outcome.decision,
            cancelled=False,
            reason=(
                "Task changed state before cancellation could be applied; not cancelled."
                if cas_outcome.decision.granted
                else "Cancellation was not authorized."
            ),
        )
    (event_bus or EventBus()).publish(
        TaskStatusChanged(
            event_id=(id_port or UuidIdAdapter()).new_id(),
            task_id=task_id,
            goal=goal,
            previous_status=current_status,
            new_status="cancelled",
            reason=None,
            timestamp=now,
        )
    )
    return TaskCancelOutcome(decision=cas_outcome.decision, cancelled=True, reason=None)


_STALE_RECOVERY_REASON_PREFIX = "Recovered from a stale 'running' state (no progress for over"


@dataclass(frozen=True)
class TaskRecoverOutcome:
    """The result of one authorize_and_recover_task() call (WP-126).

    Attributes:
        decision: The most directly gating real ``Decision``. If no
            task was found, its current status is not ``"running"``,
            or it is ``"running"`` but not yet stale, this is the
            ``memory.get`` lookup's own ``Decision`` (always granted,
            ``Tier.ALLOW``) -- nothing past that point was attempted.
            Otherwise it is the real ``memory.update`` ``Decision`` for
            the actual compare-and-swap transition to ``"failed"``.
        recovered: ``True`` only if a real compare-and-swap
            transitioning the task to ``"failed"`` was attempted,
            granted, *and* actually applied (won the race).
        reason: A real, human-readable explanation whenever
            ``recovered`` is ``False`` -- "no such task," that the
            task is not currently ``"running"``, that it has not yet
            crossed the staleness threshold, that the transition
            itself was not authorized, or that a real, concurrent
            writer changed the task's state first. ``None`` when
            ``recovered`` is ``True``.
    """

    decision: Decision
    recovered: bool
    reason: str | None


def authorize_and_recover_task(  # noqa: PLR0913 -- one per composition-function pass-through
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
) -> TaskRecoverOutcome:
    """Recover a real task stuck ``"running"`` past WP-116's own staleness threshold (WP-126).

    **The real gap this closes**: before this function existed, a task
    whose owning process genuinely crashed (SIGKILL, OOM, machine
    shutdown) had exactly one available action -- ``jarvis task
    cancel`` -- which is terminal (WP-117/WP-118: a cancelled task can
    never be retried or re-run). `jarvis task retry` only accepts
    ``"failed"`` (WP-121), and `authorize_and_run_task`'s own atomic
    claim structurally refuses any ``"running"`` -> ``"running"``
    transition (WP-120's own decisive CI finding) -- so nothing could
    ever move a genuinely abandoned task back to a retryable state.
    This closes that gap with the narrowest possible transition:
    ``"running"`` (and stale) -> ``"failed"``, after which
    `jarvis task retry` already works, completely unmodified.

    **The deterministic staleness gate, reused, not reinvented**: this
    function refuses outright unless :attr:`TaskGetOutcome.stale` is
    already ``True`` for this exact task -- the identical
    :func:`_is_stale_running` predicate WP-116 already computes from
    ``updated_at`` against a real ``ClockPort.now()``, with the
    identical :data:`STALE_RUNNING_THRESHOLD_SECONDS` threshold. A
    task that is merely old but still genuinely progressing (its own
    ``updated_at`` keeps advancing) is never eligible, no matter how
    many times this is called.

    **Why this bypasses `update_task_status` and calls the real CAS
    primitive directly, deliberately, not for convenience**: this
    function's own initial staleness check is necessarily based on a
    snapshot that can go stale itself between the read and the write
    (the owning process might genuinely still be alive and about to
    finish legitimately). `update_task_status`'s own ``atomic=True``
    path already refuses a ``"running"`` -> ``"running"`` write, but
    that check only protects the *claim* transition -- it does nothing
    to stop a ``"running"`` -> ``"failed"`` write started against a
    now-stale snapshot from silently overwriting a *different*,
    genuinely-concluded real value (e.g. the owner legitimately
    finished with ``"completed"`` moments before this call's own
    write). Calling :func:`~jarvis.kernel.memory.authorize_and_compare_and_update`
    directly, with the *exact* dict this function itself just read as
    ``expected_value``, closes that gap precisely: the underlying
    ``compare_and_update_value`` only ever applies if the record on
    disk, at the moment of the write, is still byte-for-byte identical
    to what was read -- any real, concurrent change (the owner
    finishing, another recovery attempt, a cancellation) makes the
    comparison fail cleanly, reporting ``recovered=False``, never
    silently clobbering real data. This is the exact same, already-
    audited primitive WP-120 built for the "created" -> "running" claim
    -- reused unmodified for a second, narrow purpose, not a new
    locking mechanism.

    **Attempts history is preserved, not reset**: the new value keeps
    every existing field (``created_at``, ``scheduled_at``, prior
    ``attempts``) untouched except ``status``/``reason``/``updated_at``,
    and appends one new attempt entry for this concluded "running"
    span, mirroring :func:`update_task_status`'s own identical
    attempts-append shape exactly -- so a recovered task's own history
    shows a real, dated ``"failed"`` attempt, not a silent gap.

    Returns:
        A ``TaskRecoverOutcome`` -- see its own docstring.
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
        return TaskRecoverOutcome(
            decision=get_outcome.decision,
            recovered=False,
            reason="No task found for this identifier.",
        )
    data = get_outcome.record.value.value
    current_status = data.get("status") if isinstance(data, dict) else None
    goal = data.get("goal") if isinstance(data, dict) else None
    if current_status != "running" or not isinstance(goal, str):
        return TaskRecoverOutcome(
            decision=get_outcome.decision,
            recovered=False,
            reason=(
                f"Task is {current_status!r}, not 'running'; only a stale running "
                "task can be recovered."
            ),
        )
    if not get_outcome.stale:
        return TaskRecoverOutcome(
            decision=get_outcome.decision,
            recovered=False,
            reason=(
                "Task is 'running' but has not exceeded the staleness threshold "
                f"({int(STALE_RUNNING_THRESHOLD_SECONDS)}s); not eligible for recovery."
            ),
        )
    resolved_clock = clock or SystemClockAdapter()
    now = resolved_clock.now().isoformat()
    assert isinstance(data, dict)  # noqa: S101 -- narrowed by the isinstance check above
    existing_attempts = data.get("attempts")
    attempts = list(existing_attempts) if isinstance(existing_attempts, list) else []
    reason = f"{_STALE_RECOVERY_REASON_PREFIX} {int(STALE_RUNNING_THRESHOLD_SECONDS)}s)."
    new_attempts = [
        *attempts,
        {
            "attempt": len(attempts) + 1,
            "started_at": data.get("updated_at"),
            "ended_at": now,
            "status": "failed",
            "reason": reason,
        },
    ]
    new_value: dict[str, object] = {
        **data,
        "status": "failed",
        "reason": reason,
        "updated_at": now,
        "attempts": new_attempts,
    }
    cas_outcome = _authorize_and_cas_memory(
        task_id,
        data,
        new_value,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=resolved_clock,
        id_port=id_port,
    )
    if not cas_outcome.applied:
        return TaskRecoverOutcome(
            decision=cas_outcome.decision,
            recovered=False,
            reason=(
                "Task changed state before recovery could be applied; not recovered."
                if cas_outcome.decision.granted
                else "Recovery was not authorized."
            ),
        )
    (event_bus or EventBus()).publish(
        TaskStatusChanged(
            event_id=(id_port or UuidIdAdapter()).new_id(),
            task_id=task_id,
            goal=goal,
            previous_status="running",
            new_status="failed",
            reason=reason,
            timestamp=now,
        )
    )
    return TaskRecoverOutcome(decision=cas_outcome.decision, recovered=True, reason=None)


_RETRYABLE_STATUSES = frozenset({"failed"})
"""The only real status authorize_and_retry_task() will transition out of.

Deliberately narrower than `jarvis task run`'s own, already-existing,
unchanged "completed"/"failed" re-run permissiveness (WP-118's own
documented scope boundary) -- "retry" is a real, distinct, explicit
action a human takes specifically in response to a real failure, not
a general-purpose re-run command. A `"completed"` task has nothing to
retry; `jarvis task run` remains the correct, existing command for a
caller that genuinely wants to re-run one anyway. `"created"`/
`"running"`/`"cancelled"` are refused for the same real reason `task
cancel` already refuses them: none represents a real, concluded
failure to retry.
"""


@dataclass(frozen=True)
class TaskRetryOutcome:
    """The result of one authorize_and_retry_task() call (WP-121).

    Attributes:
        decision: The most directly gating real ``Decision``. If no
            task was found, or its current status is not
            ``"failed"``, this is the ``memory.get`` lookup's own
            ``Decision`` (always granted, ``Tier.ALLOW``) -- nothing
            past that point was attempted. Otherwise it is whatever
            real ``Decision`` :func:`authorize_and_run_task` itself
            returns for the actual retry attempt.
        retried: ``True`` only if this call's own retry attempt
            genuinely executed -- mirrors
            ``TaskRunOutcome.claimed`` exactly, since a retry
            delegates to the identical, unmodified claim mechanism
            (WP-120) and can just as validly lose a race against
            another concurrent retry or run attempt for the same
            task.
        status: The task's real, current status after this call, or
            the real reason it was refused naming the non-retryable
            status it found -- never a fabricated sentinel.
        reason: The real reason, mirroring ``TaskRunOutcome.reason``
            when a retry was attempted, or naming why it was refused
            outright (not found, or not currently ``"failed"``).
    """

    decision: Decision
    retried: bool
    status: str | None
    reason: str | None


async def authorize_and_retry_task(  # noqa: PLR0913 -- one per composition-function pass-through
    task_id: str,
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
) -> TaskRetryOutcome:
    """Explicitly retry a real task currently "failed" (WP-121).

    A real, narrow, explicit action: only a task currently ``"failed"``
    may be retried (see :data:`_RETRYABLE_STATUSES`'s own docstring
    for why this is deliberately narrower than ``jarvis task run``'s
    own, unchanged permissiveness). Once permitted, this delegates
    directly to the exact, unmodified :func:`authorize_and_run_task`
    for the actual execution -- no new authorization concept, no new
    ``CapabilityId``/``Effect``/``Tier``, no second execution path.
    This also means a retry is automatically protected by the exact
    same, real, process-safe claim mechanism (WP-120) that already
    protects every other real call into ``authorize_and_run_task``:
    two independent processes both retrying the same failed task race
    on the identical "failed" -> "running" compare-and-swap, and the
    same "running" -> "running" refusal closes the identical gap a
    slower, later racer would otherwise hit.

    A ``"cancelled"`` task is never retried -- it is not in
    :data:`_RETRYABLE_STATUSES` at all, so it is refused by the exact
    same real status check every other non-retryable status is,
    before :func:`authorize_and_run_task` is ever called.

    Returns:
        A ``TaskRetryOutcome`` -- see its own docstring.
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
        return TaskRetryOutcome(
            decision=get_outcome.decision,
            retried=False,
            status=None,
            reason="No task found for this identifier.",
        )
    data = get_outcome.record.value.value
    current_status = data.get("status") if isinstance(data, dict) else None
    goal = data.get("goal") if isinstance(data, dict) else None
    if current_status not in _RETRYABLE_STATUSES or not isinstance(goal, str):
        return TaskRetryOutcome(
            decision=get_outcome.decision,
            retried=False,
            status=current_status if isinstance(current_status, str) else None,
            reason=(f"Task is {current_status!r}; only a 'failed' task can be retried."),
        )
    run_outcome = await authorize_and_run_task(
        task_id,
        goal,
        provider,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
        event_bus=event_bus,
    )
    return TaskRetryOutcome(
        decision=run_outcome.decision,
        retried=run_outcome.claimed,
        status=run_outcome.status,
        reason=run_outcome.reason,
    )


def _parse_aware_iso8601(value: str, field_name: str) -> datetime:
    """Parse `value` as ISO-8601, rejecting a naive (timezone-less) result (WP-122).

    A deliberate, local duplicate of
    `adapters/calendar.py::_parse_aware_iso8601`'s own, already-
    established real bug fix (10-phase combined pass, Phase 10) rather
    than a cross-import: `kernel/tasks.py` has no real reason to depend
    on the calendar adapter, and this is a small, generic, timezone-
    correctness check, not calendar-specific logic. The same real
    hazard applies here -- `datetime.fromisoformat()` silently accepts
    a string with no UTC offset (e.g. `"2026-09-12T09:00:00"`),
    producing a naive `datetime` that would make "is this due yet"
    comparisons against a real, always-UTC `ClockPort.now()` silently
    ambiguous (whose timezone does the naive value mean?). Rejecting
    it outright, rather than guessing a timezone, is the same safe
    choice already made for calendar events.

    Args:
        value: The real, caller-supplied ISO-8601 string.
        field_name: Which field this is, for a clear error message.

    Raises:
        ValueError: If `value` is not valid ISO-8601, or parses to a
            naive `datetime` (no timezone offset).
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        msg = (
            f"{field_name} must include an explicit timezone offset "
            f"(e.g. '+00:00' or 'Z'), got {value!r} -- a naive datetime "
            "would make 'is this due yet' ambiguous."
        )
        raise ValueError(msg)
    return parsed


_SCHEDULABLE_STATUSES = frozenset({"created"})
"""The only real status authorize_and_schedule_task() will accept (WP-122).

A task must still be `"created"` -- never attempted -- to be
scheduled. `"running"`/`"completed"`/`"failed"`/`"cancelled"` are all
refused: scheduling does not interact with retry (WP-121's own
explicit, human-triggered retry remains the one real way to re-attempt
a failed task -- this module deliberately does not let a caller
"schedule a retry" by reusing this function on a `"failed"` task), and
a `"cancelled"`/terminal task has nothing left to schedule.
"""


@dataclass(frozen=True)
class TaskScheduleOutcome:
    """The result of one authorize_and_schedule_task() call (WP-122).

    Attributes:
        decision: The most directly gating real ``Decision``. If no
            task was found, or its current status is not
            ``"created"``, this is the ``memory.get`` lookup's own
            ``Decision`` (always granted, ``Tier.ALLOW``) -- nothing
            past that point was attempted. Otherwise it is the real
            ``memory.update`` ``Decision`` for the actual write of the
            new ``scheduled_at`` value.
        scheduled: ``True`` only if a real write setting
            ``scheduled_at`` was attempted and granted.
        scheduled_at: The real, canonical (UTC) ISO-8601 string that
            was actually stored, if ``scheduled`` is ``True``. ``None``
            otherwise -- never a fabricated echo of the caller's own
            input when nothing was actually written.
        reason: A real, human-readable explanation whenever
            ``scheduled`` is ``False`` -- "no such task," or naming
            the task's own current, non-schedulable status, or that
            the write itself was not authorized. ``None`` when
            ``scheduled`` is ``True``.
    """

    decision: Decision
    scheduled: bool
    scheduled_at: str | None
    reason: str | None


def authorize_and_schedule_task(  # noqa: PLR0913 -- one per composition-function pass-through
    task_id: str,
    scheduled_at: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
) -> TaskScheduleOutcome:
    """Schedule a real task currently "created" to become due at `scheduled_at` (WP-122).

    A real, narrow, additive operation -- this never changes the
    task's own `status` (it stays `"created"`; see module docstring's
    own WP-122 section for why no new status was introduced). Calling
    this again on the same still-`"created"` task simply overwrites
    the previously-stored `scheduled_at` with the new one -- a real,
    deliberate way to reschedule without a separate "unschedule" verb
    (see module docstring).

    Scheduling itself is **not** authorization for the eventual run --
    a real, separate, later `authorize_and_run_task` call (made by
    `jarvis.kernel.worker.run_pending_tasks_once` once `scheduled_at`
    has passed) still independently requires its own
    `physical_confirmation_available`/`remote_confirmation_available`,
    exactly like every other real caller. A scheduled timestamp carries
    no pre-approval of anything a plan might later do.

    `task_id` is a real identifier from a prior, granted
    `authorize_and_create_task` call. `scheduled_at` is a real,
    caller-supplied ISO-8601 timestamp with an explicit timezone
    offset (see `_parse_aware_iso8601`) -- canonicalized to UTC before
    storage, so a later due-time comparison against `ClockPort.now()`
    (always UTC) is never a timezone-conversion question.

    Raises:
        ValueError: If `scheduled_at` is not a valid, timezone-aware
            ISO-8601 timestamp -- raised before any real lookup or
            write is attempted, mirroring `adapters/calendar.py`'s own
            identical fail-fast convention.

    Returns:
        A ``TaskScheduleOutcome`` -- see its own docstring.
    """
    parsed = _parse_aware_iso8601(scheduled_at, "scheduled_at")
    canonical_scheduled_at = parsed.astimezone(UTC).isoformat()

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
        return TaskScheduleOutcome(
            decision=get_outcome.decision,
            scheduled=False,
            scheduled_at=None,
            reason="No task found for this identifier.",
        )
    data = get_outcome.record.value.value
    current_status = data.get("status") if isinstance(data, dict) else None
    goal = data.get("goal") if isinstance(data, dict) else None
    reason = data.get("reason") if isinstance(data, dict) else None
    created_at = data.get("created_at") if isinstance(data, dict) else None
    attempts = data.get("attempts") if isinstance(data, dict) else None
    if current_status not in _SCHEDULABLE_STATUSES or not isinstance(goal, str):
        return TaskScheduleOutcome(
            decision=get_outcome.decision,
            scheduled=False,
            scheduled_at=None,
            reason=f"Task is {current_status!r}; only a 'created' task can be scheduled.",
        )
    record: dict[str, object] = {
        "kind": TASK_KIND,
        "goal": goal,
        "status": current_status,
        "reason": reason if isinstance(reason, str) else None,
        "created_at": created_at,
        "updated_at": (clock or SystemClockAdapter()).now().isoformat(),
        "attempts": list(attempts) if isinstance(attempts, list) else [],
        "scheduled_at": canonical_scheduled_at,
    }
    # WP-127: a real compare-and-swap, not a blind overwrite -- `record` above was
    # built from `data`, read moments earlier. Without this, a worker legitimately
    # claiming this exact task ("created" -> "running") between that read and this
    # write would have its own real claim silently reverted back to "created" by
    # this call's own stale `current_status` snapshot -- a genuine, real hazard for
    # duplicate execution (the reverted task becomes claimable again), not merely a
    # lost update. See docs/architecture/wp127-cancel-and-schedule-race-hardening.md.
    cas_outcome = _authorize_and_cas_memory(
        task_id,
        data,
        record,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    if not cas_outcome.applied:
        return TaskScheduleOutcome(
            decision=cas_outcome.decision,
            scheduled=False,
            scheduled_at=None,
            reason=(
                "Task changed state before scheduling could be applied; not scheduled."
                if cas_outcome.decision.granted
                else "Scheduling was not authorized."
            ),
        )
    return TaskScheduleOutcome(
        decision=cas_outcome.decision,
        scheduled=True,
        scheduled_at=canonical_scheduled_at,
        reason=None,
    )
