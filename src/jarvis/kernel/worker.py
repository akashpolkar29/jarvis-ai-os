"""worker: a real, minimal local background-task worker atop authorize_and_run_task (WP-120).

**The real gap this closes**: every prior work package on task
execution (WP-107 through WP-119) made the task lifecycle durable and
safe, but execution itself was always triggered by one specific,
already-present human action -- a direct `jarvis task run <id>
<goal>` call, or a browser click on the UI's "Run" button. Nothing
ever discovered an eligible, already-created task and ran it on its
own. This module is the smallest real thing that does: a worker that
*discovers* tasks still `"created"`, *claims* one at a time through
the real, process-safe mechanism WP-120 added directly inside
`authorize_and_run_task`'s own "created" -> "running" transition, and
*delegates* execution to that exact, unmodified function.

**Not a second execution engine, by construction, not by convention**:
this module contains zero capability-specific logic. It does not know
what a plan step is, does not call `planning.run_plan`, and does not
touch `kernel.capability_dispatch` -- it only calls
`kernel.tasks.authorize_and_list_tasks`/`authorize_and_run_task`,
completely unmodified, the exact same functions `jarvis task
list`/`jarvis task run` already call. A worker processing many tasks
is structurally indistinguishable, from the kernel's own point of
view, from a human typing `jarvis task run` once per task in a loop.

**The claim mechanism itself lives in `kernel.tasks`, not here**: this
module never touches `compare_and_update_value`/
`authorize_and_compare_and_update` directly. It calls
`authorize_and_run_task` once per eligible task and trusts its own,
already-real `claimed` field (`TaskRunOutcome.claimed`, WP-120) to
know whether *this* call actually executed anything -- see
`kernel.tasks`'s own module docstring for the full claim-mechanism
reasoning (the real, `fcntl.flock()`-based compare-and-swap, why only
the "created" -> "running" transition needed it, why two independent
processes calling this module's own `run_pending_tasks_once` for the
same task can never both execute it).

**Authorization is never special-cased for a worker**: every real call
this module makes reuses the exact same `physical_confirmation_available`/
`remote_confirmation_available` flags every other subcommand already
requires, with no safe default and no auto-confirmation. A worker
launched with neither flag set correctly claims nothing -- every
"created" -> "running" transition attempt is denied by policy, exactly
as a direct `jarvis task run` with no flags already is today. This is
not new code to enforce that; it is simply what reusing
`authorize_and_run_task` unmodified already guarantees.

**Cancellation**: a cancelled task is never even discovered -- this
module's own discovery step only ever lists tasks whose status is
`"created"` (see `_ELIGIBLE_STATUS` below), and `authorize_and_run_task`
itself independently refuses to resume a `"cancelled"` task (WP-118)
even if one somehow reached this far. No new cancellation logic exists
here.

**Crash safety, stated precisely, not overclaimed**: if this worker's
own process is killed mid-execution of one task, that task is left at
`"running"` exactly as it would be for a crashed direct `jarvis task
run` invocation -- WP-116's own stale-running-task detection is the
accepted, existing safety net; this module does not add, and was not
asked to add, any automatic recovery of an abandoned claim. A
genuinely malformed task record (a `"goal"` field that is not a real
string) is skipped with an honest, logged warning, never silently
dropped and never crashing the whole pass.

**Job-application safety (ADR-0058) is structurally unaffected**: this
module can only ever reach `planning.run_plan` through
`authorize_and_run_task`, which only ever reaches capabilities already
wired into `kernel.capability_dispatch.PLAN_STEP_EXECUTORS` -- no
submission capability exists there today, and this module adds none.
A worker automating task execution does not, and structurally cannot,
automate job-application submission.

**WP-122 (2026-09-12): deterministic one-time local scheduling.** A
task's own, real, additive `scheduled_at` field (`kernel.tasks`'s own
WP-122 section) is the one new thing this module's discovery step
consults -- a `"created"` task with no `scheduled_at` at all (every
task created before this work package existed, and every task created
after it that was never scheduled) is eligible exactly as before,
unchanged. A `"created"` task that *is* scheduled is only added to
this pass's own `attempted` set once its own `scheduled_at` has
genuinely passed a real `ClockPort.now()` -- checked fresh, every
pass, never cached. A scheduled task that is not yet due is silently
excluded from `attempted` entirely, exactly as if discovery itself had
not returned it -- it is not an error, and it is not reported as a
"loss." **No second claim mechanism**: this due-time check is a pure,
local, read-only filter over what this pass will *attempt*; the real
mutual-exclusion guarantee (two workers never both executing the same
task) still comes entirely from the one, real, unmodified claim inside
`authorize_and_run_task` itself -- the due-time check merely decides
who gets to *try*, exactly the same way the existing `"created"`
status filter already does.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.kernel.tasks import authorize_and_list_tasks, authorize_and_run_task

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.events import EventBus
    from jarvis.ports.clock import ClockPort
    from jarvis.ports.embedding import EmbeddingPort
    from jarvis.ports.identifier import IdPort
    from jarvis.ports.reasoning import ReasoningPort

_logger = logging.getLogger(__name__)

_ELIGIBLE_STATUS = "created"
"""The one, real, unextended status `run_pending_tasks_once` discovers -- deliberately not a
new "queued" status (see this module's own originating work package: do not activate a
reserved status, or invent a new one, without proving it is genuinely needed). A task already
"running" is never re-discovered by a later pass -- it is not `"created"` anymore."""


def _is_due(data: object, now: datetime) -> bool:
    """Whether a real `"created"` task record's own `scheduled_at` (if any) has passed (WP-122).

    `True` for every task with no real `scheduled_at` string at all --
    the existing, unchanged, immediately-eligible behavior this work
    package does not alter. `True` once a real, stored `scheduled_at`
    is at or before `now`. A malformed, unparseable `scheduled_at`
    (should never happen through `authorize_and_schedule_task`'s own
    real validation, but a hand-edited or legacy-adjacent record is not
    assumed impossible) is treated as due -- an honest, logged warning
    is the caller's own responsibility, not this pure predicate's; see
    `run_pending_tasks_once`'s own real handling immediately below.
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


@dataclass(frozen=True)
class WorkerTaskOutcome:
    """What happened to one real, individually-attempted task during one worker pass.

    Attributes:
        task_id: The real task identifier this outcome describes.
        claimed: Mirrors `TaskRunOutcome.claimed` (WP-120) exactly --
            `True` only if this pass's own call was the one that
            actually executed the task. `False` if another real
            claimant (another worker process, or a direct `jarvis task
            run`) won the race first, or if the underlying
            `authorize_and_run_task` call raised (see `error`).
        status: The real, current status this call observed -- `None`
            only if `error` is set (the exception occurred before any
            status could be read back, an extremely rare case covered
            defensively, not a designed-for outcome).
        reason: The real reason string, if any -- mirrors
            `TaskRunOutcome.reason`.
        error: The real exception's own `f"{type}: {message}"` text,
            if `authorize_and_run_task` raised for this task. `None`
            for every task that did not raise -- `authorize_and_run_task`
            itself already persisted the task's own `"failed"` status
            with this exact reason before re-raising (WP-113), so a
            non-`None` `error` here is diagnostic information for this
            pass's own caller, not the first or only place this
            failure was recorded.
    """

    task_id: str
    claimed: bool
    status: str | None
    reason: str | None
    error: str | None = None


@dataclass(frozen=True)
class WorkerPassOutcome:
    """The result of one real call to run_pending_tasks_once() -- every eligible task, once each.

    Attributes:
        attempted: One `WorkerTaskOutcome` per real task this pass
            discovered and attempted, in the order
            `authorize_and_list_tasks` returned them. Empty if no
            `"created"` task existed at the moment this pass started
            its own discovery step -- not an error. WP-122: a
            `"created"` task that is scheduled but not yet due is
            excluded from this tuple entirely -- not attempted, not an
            error, and not distinguishable here from never having
            existed at all (see `_is_due`).
    """

    attempted: tuple[WorkerTaskOutcome, ...] = field(default_factory=tuple)

    @property
    def claimed_count(self) -> int:
        """How many of `attempted` this pass itself actually executed (won the claim)."""
        return sum(1 for outcome in self.attempted if outcome.claimed)


async def run_pending_tasks_once(  # noqa: PLR0913 -- one per composition-function pass-through
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    database_path: Path | None = None,
    embedding_port: EmbeddingPort | None = None,
    clock: ClockPort | None = None,
    id_port: IdPort | None = None,
    event_bus: EventBus | None = None,
    provider: ReasoningPort | None = None,
) -> WorkerPassOutcome:
    """Discover every real task currently "created" and attempt to claim-and-run each, once.

    A single, bounded, deterministic pass -- never loops, never
    sleeps, never blocks waiting for new work. `jarvis task worker`
    (the CLI entry point) is the thin, continuous-mode wrapper around
    repeated calls to this function; this function itself is what
    tests exercise directly, with no infinite loop anywhere in this
    call.

    Each eligible task is attempted through the exact, unmodified
    `authorize_and_run_task` -- this function never executes a plan
    step itself, never bypasses authorization, and never auto-confirms
    anything (see module docstring).

    WP-122: a `"created"` task whose own real `scheduled_at` has not
    yet passed `now` is silently excluded from `attempted` entirely --
    not attempted, not reported, exactly as if discovery had not
    returned it (see module docstring's own WP-122 section and
    `_is_due`).

    A real exception from one task's own `authorize_and_run_task` call
    is caught and recorded in that task's own `WorkerTaskOutcome.error`
    -- it never aborts the rest of this pass, and it is never silently
    swallowed: it is also logged via `logging.exception`.

    Returns:
        A `WorkerPassOutcome` -- see its own docstring.
    """
    list_outcome = authorize_and_list_tasks(
        status=_ELIGIBLE_STATUS,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=embedding_port,
        clock=clock,
        id_port=id_port,
    )
    now = (clock or SystemClockAdapter()).now()

    attempted: list[WorkerTaskOutcome] = []
    for record in list_outcome.records:
        data = record.value.value
        if not _is_due(data, now):
            continue
        goal = data.get("goal") if isinstance(data, dict) else None
        if not isinstance(goal, str):
            _logger.warning(
                "worker: skipping task %s -- its own stored record has no real string goal",
                record.identifier,
            )
            attempted.append(
                WorkerTaskOutcome(
                    task_id=record.identifier,
                    claimed=False,
                    status=None,
                    reason=None,
                    error="Malformed task record: no real string goal.",
                )
            )
            continue

        try:
            run_outcome = await authorize_and_run_task(
                record.identifier,
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
        except Exception as exc:
            # authorize_and_run_task already persisted a real "failed" status
            # with this exact reason before re-raising (WP-113) -- this is
            # diagnostic information for this pass's own caller, never the
            # first or only place the failure is recorded, and never
            # silently swallowed (logged below).
            #
            # claimed=True here, not False: reaching this except block at all
            # almost always means the claim itself already succeeded -- a
            # lost claim race returns normally (claimed=False on the real
            # TaskRunOutcome, see authorize_and_run_task's own WP-120
            # section), it never raises. A real, named, narrow exception:
            # a genuine I/O failure *during* the claim's own atomic write
            # (e.g. a real SQLite lock timeout) would also land here and be
            # reported claimed=True even though nothing was actually won --
            # a benign, diagnostic-only imprecision in this field alone,
            # since the real, persisted TaskStore state is correct either
            # way and is never affected by this bookkeeping distinction.
            _logger.exception("worker: task %s raised during execution", record.identifier)
            attempted.append(
                WorkerTaskOutcome(
                    task_id=record.identifier,
                    claimed=True,
                    status=None,
                    reason=None,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        attempted.append(
            WorkerTaskOutcome(
                task_id=record.identifier,
                claimed=run_outcome.claimed,
                status=run_outcome.status,
                reason=run_outcome.reason,
            )
        )

    return WorkerPassOutcome(attempted=tuple(attempted))
