# Deterministic one-time local task scheduling (WP-122, 2026-09-12)

## Status

Real, implemented. No ADR -- scheduling reuses `memory.update`'s own already-
classified authorization path (the identical reasoning `update_task_status`/
`authorize_and_cancel_task`/`authorize_and_retry_task` already established)
completely unmodified. No new `CapabilityId`/`Effect`/`Tier`.

## Investigation findings (before writing any code)

A repository-wide search for `schedule`/`scheduled`/`scheduler`/`cron`/`timer`/
`due_at`/`run_at`/`next_run`/`interval`/`recurrence` in `src/jarvis/` found
**no existing scheduling infrastructure of any kind** -- the only false-positive
hits were unrelated (`EscalationLadder.next_rung`, a docstring mentioning "not a
new background scheduler"). `ClockPort`/`SystemClockAdapter` already exist
(ADR-0054) and are already the one real, injectable source of wall-clock time
this project allows anywhere in `src/`. `jarvis.kernel.worker.run_pending_tasks_once`
already discovers every `"created"` task and delegates each to the exact,
unmodified `authorize_and_run_task` -- the real claim mechanism (WP-120, a
process-safe `fcntl.flock()`-backed compare-and-swap on the "created" -> "running"
transition) already exists and needed no changes. `update_task_status` already
performs a real read-modify-write that preserves fields it does not itself
change (`created_at`, `attempts`) -- the exact mechanism a new, additive
`scheduled_at` field needed to plug into.

## Scheduling model

**No new task status.** A scheduled task stays `"created"` for its entire wait
-- the worker already discovers every `"created"` task; scheduling adds exactly
one more, optional, additive field to the stored record: `scheduled_at` (a real,
UTC-canonicalized ISO-8601 string, or `None`). `None` is the default for every
task created before or after this work package, and for every legacy record
with no such key at all -- it means exactly what `"created"` already meant
before this work package existed: immediately eligible. A non-`None`
`scheduled_at` means "eligible once this real time has passed."

`authorize_and_schedule_task(task_id, scheduled_at, ...)` (`jarvis task
schedule <task_id> --at <iso8601>`) is the one, new, explicit write. Only a task
currently `"created"` may be scheduled (`_SCHEDULABLE_STATUSES = frozenset({"created"})`)
-- `"running"`/`"completed"`/`"failed"`/`"cancelled"` are all refused with a
clear reason naming the current status. `"failed"` is deliberately excluded:
scheduling is not a back-door way to auto-retry a failed task -- WP-121's own
explicit, human-triggered `jarvis task retry` remains the one real way to do
that, unaffected by this work package.

Calling `authorize_and_schedule_task` again on the same, still-`"created"` task
simply overwrites the prior `scheduled_at` with the new one. This is the real,
deliberate substitute for a separate "unschedule" verb, which was investigated
and not built: no genuine, independent use case was found for "clear the
schedule but keep the task waiting, unscheduled" that re-scheduling (or, if the
real intent is "don't run this at all," `jarvis task cancel`) does not already
cover.

## Timezone policy

`_parse_aware_iso8601` (a small, local, deliberate duplicate of
`adapters/calendar.py::_parse_aware_iso8601`'s own already-established real bug
fix, 10-phase combined pass, Phase 10 -- not a cross-import, since `kernel/tasks.py`
has no real reason to depend on the calendar adapter for a small, generic
timezone-correctness check) rejects a naive (timezone-less) input outright,
raising `ValueError` before any real lookup or write is attempted. The accepted
value is canonicalized to UTC (`parsed.astimezone(UTC).isoformat()`) before
storage, so every later due-time comparison against `ClockPort.now()` (always
UTC) is a plain `<=` between two UTC-aware datetimes, never a conversion
question. A non-UTC offset (e.g. `+05:00`) is accepted and converted, not
rejected.

## Missed-schedule policy

The simplest safe, deterministic choice: **a `scheduled_at` at or before the
current real time is due, full stop** -- whether that is because the worker
happens to be checking promptly, or because the worker was not running at all
for hours and only just started. There is no catch-up logic and no "this was
supposed to run N times while the laptop was asleep" accounting, because
recurrence is explicitly out of this work package's own scope -- there is only
ever one real due moment to miss or not miss. A task already executed once
naturally leaves `"created"` status, so the worker structurally cannot
re-discover and re-run it on a later pass; no separate "already consumed" flag
was added (see "What was deliberately not built" below for why).

## Worker integration

`jarvis.kernel.worker.run_pending_tasks_once`'s own discovery step gained one
new, pure, local filter: `_is_due(data, now)`. A `"created"` task with no
`scheduled_at` at all (every task created before this work package existed, and
every task created after it that was never scheduled) is eligible exactly as
before, unchanged. A `"created"` task that *is* scheduled is only added to a
pass's own `attempted` set once its own `scheduled_at` has genuinely passed a
real `ClockPort.now()`, checked fresh on every pass. A scheduled task that is
not yet due is silently excluded from `attempted` entirely -- not an error, not
a "loss," exactly as if discovery itself had not returned it.

**No second claim mechanism, no second execution engine.** `_is_due` is a pure,
read-only filter over what a pass will *attempt* -- the real, load-bearing
mutual-exclusion guarantee (two workers never both executing the same task)
still comes entirely from the one, real, unmodified claim inside
`authorize_and_run_task` itself (WP-120). The due-time check merely decides who
gets to *try*, exactly the same way the existing `"created"` status filter
already does.

## Duplicate-execution protection

Proven directly by a new, dedicated, real `multiprocessing.Process` test,
`tests/unit/test_worker_scheduling_process_safety.py`, mirroring WP-120's/
WP-121's own headline pattern exactly -- but racing `run_pending_tasks_once`
itself (the real function two independent `jarvis task worker` invocations
would each call), not `authorize_and_run_task` directly, since that is the
real, faithful shape this work package actually introduces. Six genuinely
independent OS processes, barrier-released together, all call the exact same,
unmodified `run_pending_tasks_once` against the exact same, already-scheduled,
already-past-due task. The real property proven: no two real winners' own
measured `[start, end]` wall-clock windows ever overlap -- the literal,
real-world meaning of "never simultaneous," using the identical
`_intervals_overlap` technique (and the identical reasoning for why a raw claim
*count* is the wrong instrument) that WP-120's own CI debugging already
established. Run 3/3 consecutive times normally and 3/3 consecutive times under
`taskset -c 0,1` (the same adversarial CPU-contention technique that originally
exposed WP-120's real "running" -> "running" CAS bug) with zero flakiness.

## Cancellation

A cancelled task's own status is `"cancelled"`, not `"created"`, so the
worker's own, unchanged status filter already excludes it from discovery
entirely -- no scheduling-specific cancellation check was needed or added.
`scheduled_at` itself survives a cancellation (preserved by
`update_task_status`'s own existing read-modify-write, see below) purely as
historical information; it has no further effect once the task is
`"cancelled"`.

## Retry

Retrying a scheduled-then-failed task (WP-121) delegates directly,
unmodified, to `authorize_and_run_task`, which does not consult `scheduled_at`
at all -- an explicit retry always runs immediately, exactly like retrying any
other failed task. The original `scheduled_at` is preserved in the record
purely as historical information; this was verified directly by a dedicated
test (`test_scheduled_at_survives_a_failed_run_and_a_subsequent_retry`).

## Authorization

Scheduling itself is never authorization for the eventual run. The real,
separate, later `authorize_and_run_task` call (made by
`run_pending_tasks_once` once `scheduled_at` has passed) still independently
requires its own `physical_confirmation_available`/`remote_confirmation_available`
-- exactly like every other real caller, with no safe default and no
auto-confirmation. A scheduled timestamp carries no pre-approval of anything a
plan might later do. ADR-0062's own per-step authorization, the `CONFIRM`/
`MANUAL_ONLY` tier floors, and ADR-0058's job-application submission boundary
are all completely untouched -- the worker still cannot structurally reach a
submission capability, since none is wired into
`kernel.capability_dispatch.PLAN_STEP_EXECUTORS`, unchanged by this work
package.

## Audit

Scheduling reuses the exact, unmodified `memory.update` authorization/write
path every other real status-adjacent task mutation already uses -- every real
`authorize_and_schedule_task` call that actually writes produces a real,
hash-chained audit record, with no new audit mechanism and no hash-chain
changes. Verified directly: the full test suite's own hash-chain-verifying
tests pass unchanged with this work package's changes in place.

## Backwards compatibility

`update_task_status`'s own real read-modify-write (the same mechanism that
already preserves `created_at`/`attempts` across every transition) now also
preserves `scheduled_at` -- reading `existing.get("scheduled_at")`, defaulting
to `None` for any record (legacy or otherwise) that lacks the key. A genuine
pre-WP-122 record, constructed directly via `authorize_and_remember` with no
`"scheduled_at"` key at all, was proven to still load and still be schedulable
(`test_a_legacy_task_record_with_no_scheduled_at_field_can_still_be_scheduled`),
and to still be immediately eligible to the worker with no schedule at all
(`test_a_legacy_created_task_record_with_no_scheduled_at_key_is_immediately_eligible`).

## What was deliberately not built

- **No recurrence.** Explicitly out of scope per this work package's own
  instructions -- no recurring-schedule primitive existed to reuse, and
  building one was not asked for.
- **No natural-language scheduling** ("tomorrow morning," "every weekday").
  `--at` requires an exact, explicit ISO-8601 timestamp with a timezone offset.
- **No `jarvis task unschedule`.** Investigated and not built -- re-scheduling
  (calling `schedule` again) already covers "change the time," and
  `jarvis task cancel` already covers "don't run this at all." No genuine,
  independent use case was found for a third verb.
- **No separate "schedule consumed" flag.** Once a scheduled task executes, its
  status leaves `"created"` (to `"running"` and then a terminal status), so the
  worker's own, unchanged `"created"`-only discovery filter structurally cannot
  re-discover and re-run it -- the existing state machine already provides the
  "executes only once" guarantee for free, without a second, redundant
  bookkeeping field.
- **No UI exposure.** `jarvis ui`'s frontend is unmodified -- out of scope per
  this work package's own instructions unless it could be exposed with
  essentially zero redesign, and a real scheduling UI (a date/time picker, a
  "scheduled" indicator on a task card) is genuinely new frontend surface, not
  a zero-cost addition.
- **No voice grammar.** Matching `jarvis task cancel`/`jarvis task retry`'s own
  identical, existing scope boundary.

## Testing

- `tests/unit/test_tasks_kernel.py`: 15 new tests covering
  `authorize_and_schedule_task` directly -- a successful schedule with UTC
  canonicalization, non-UTC-offset conversion, naive-timestamp rejection,
  garbage-timestamp rejection, not-found/wrong-status refusals (`running`/
  `completed`/`failed`/`cancelled`, each with its own exact reason),
  re-scheduling overwriting the prior value, denied-confirmation leaving the
  record untouched, `scheduled_at` surviving a run/retry/cancellation
  transition, and legacy-record backward compatibility.
- `tests/unit/test_worker_kernel.py`: 9 new tests -- a not-yet-due scheduled
  task is never attempted, a task scheduled for exactly `now` is due (`<=`,
  not `<`), a past-scheduled task runs through the real canonical path, a
  scheduled task executes only once across several passes, a failed scheduled
  task persists `"failed"` and preserves `scheduled_at`, a cancelled scheduled
  task is never discovered, an unscheduled task is unaffected, a legacy record
  with no `scheduled_at` key is immediately eligible, plus 5 direct unit tests
  of the pure `_is_due` predicate (non-dict input, malformed timestamp, no key,
  explicit `None`, a real future timestamp) closing out branch coverage on
  `worker.py` to 100%.
- `tests/unit/test_worker_scheduling_process_safety.py` (new file): the
  headline, real, cross-process duplicate-execution proof -- see "Duplicate-
  execution protection" above.
- `tests/unit/test_cli_main.py`: 4 new tests -- `jarvis task schedule`
  reporting a granted schedule, a refused schedule with its reason, a real
  `ValueError` (naive timestamp) surfacing cleanly through `main()`'s own
  existing broad except tuple, and the missing-argument `SystemExit` cases.
- A real, live, manual smoke test (not just automated tests) exercised the
  full path end to end against this development machine's real local Ollama
  server: a task scheduled far in the future was correctly left untouched by
  `jarvis task worker --once`; the same task scheduled in the past was
  correctly discovered, claimed, and run through the real canonical execution
  path, reaching a real `PlanningError` (the already-documented ~33% local-model
  failure hazard) with `scheduled_at` correctly preserved in the resulting
  `"failed"` record -- satisfying this work package's own explicit
  requirement not to claim "scheduling complete" without testing a real
  scheduled task from persisted state through the actual worker and canonical
  execution path.

## Files changed

- `src/jarvis/kernel/tasks.py`: `_parse_aware_iso8601`, `_SCHEDULABLE_STATUSES`,
  `TaskScheduleOutcome`, `authorize_and_schedule_task`; `scheduled_at` added to
  `write_task_record`/`update_task_status`.
- `src/jarvis/kernel/worker.py`: `_is_due`, its use in `run_pending_tasks_once`;
  a stale "BEGIN IMMEDIATE" reference in the module docstring corrected in
  passing (the real, merged WP-120 mechanism is `fcntl.flock()`, a drift this
  file's own docstring had not been updated for since WP-120's final CI fix).
- `src/jarvis/cli/main.py`: `task schedule <task_id> --at <timestamp>`
  subparser and dispatch, `task_scheduled`/`task_scheduled_at` fields on
  `_CommandOutcome`, printing (including `scheduled_at` in `task status`/
  `task list`'s own existing record printer).
- `tests/unit/test_tasks_kernel.py`, `tests/unit/test_worker_kernel.py`,
  `tests/unit/test_cli_main.py`,
  `tests/unit/test_worker_scheduling_process_safety.py` (new).
