# Stale-running-task detection (WP-116, 2026-09-11)

## Status

Real, implemented. No ADR -- this is detection-only, read-only,
additive visibility on top of `jarvis.kernel.tasks`'s own already-real,
already-Accepted (ADR-0063) persistent task lifecycle (WP-107). It
introduces no new `CapabilityId`, `Effect`, or `Tier`, and it never
mutates a task's own stored status -- it only computes and surfaces a
derived, ephemeral fact about an existing record.

## The real gap this closes

WP-107's `Task`/`TaskStore` persists a task's `status` (one of
`VALID_TASK_STATUSES`) and an `updated_at` timestamp, updated on every
real transition. WP-109 unified the vocabulary so a task that failed
mid-execution is always recorded as `"failed"`, never a mix of
`"failed"`/`"stuck"`.

Neither WP-107 nor WP-109 addressed the case this work package closes:
a task whose owning **process** is killed (SIGKILL, OOM, machine
shutdown, crash) while the task's own stored status is still
`"running"`. No in-process exception ever fires, so no
`(PlanningError, PlanValidationError)` branch in
`authorize_and_run_task` ever runs, so the status is never transitioned
to `"failed"` -- the record is left at `"running"` forever, with a real,
genuine, silent loss of visibility (this is the same underlying
process-level-crash gap WP-112's own documentation already named as
"a real, pre-existing limitation found while building this, not
introduced by it" -- WP-116 is the first work package to actually
address it, on the visibility side only).

## Why detection-only, never automatic recovery

A task legitimately mid-run for longer than the chosen threshold (a
slow local model, a long-running coding loop) is, from the stored
record's own fields alone, indistinguishable from a crashed one --
both look like `status == "running"` with a stale `updated_at`. Per
the overnight session's own explicit instruction ("if a process
crashes, investigate whether the current task state can recover
safely before adding recovery behavior"), no automatic status mutation
is introduced. A human (or a future, separately-decided mechanism) is
the only thing that can safely decide a specific stale task is
genuinely dead rather than genuinely slow.

## The mechanism

`STALE_RUNNING_THRESHOLD_SECONDS = 1800.0` (30 minutes), chosen well
above `adapters/reasoning/local.py::_REQUEST_TIMEOUT_SECONDS` (120
seconds per reasoning call) -- even a real coding-loop climb through
several escalation rungs, each making one or more reasoning calls,
should complete well inside 30 minutes; a task still `"running"` past
that point is treated as worth flagging to a human, not as proof of a
crash.

`_is_stale_running(data, now)` is a pure, total function: returns
`True` only if `data` is a dict, `data["status"] == "running"`, and
`now - fromisoformat(data["updated_at"])` exceeds the threshold;
returns `False` for any malformed/missing field, never raises.

- `authorize_and_get_task()` now returns `TaskGetOutcome.stale: bool`,
  computed against a real `ClockPort.now()` (injected, defaulting to
  `SystemClockAdapter()`, matching every other real clock-consuming
  function in this module).
- `authorize_and_list_tasks()` now returns
  `TaskListOutcome.stale_task_ids: frozenset[str]` -- a deliberately
  separate field from `records`, not a per-record flag baked into the
  tuple, to keep genuinely-persisted content and ephemeral, derived-at-
  read-time facts visibly distinct in the return shape.

Neither function mutates the underlying `MemoryRecord` or calls
`update_task_status`/`update_value` -- confirmed directly, the only
new code paths are pure reads.

## CLI visibility

`jarvis task status <id>` and `jarvis task list` now print a real
warning line under any task reported stale:

```
task:7: goal='...' status=running
    warning: no status update in over 30 minutes -- this task may have
    crashed or been interrupted; its status was never automatically changed
```

`_print_one_task_record()` takes a new `stale: bool = False` keyword
parameter; `_print_task_outcome()` passes
`outcome.task_stale` (single-record case, `task status`) or
`record.identifier in outcome.stale_task_ids` (per-record case inside
the `task list` loop). No existing call site's behavior changes for a
non-stale task -- the new parameter defaults to `False` and the
existing print lines are otherwise untouched.

## Testing

- `tests/unit/test_tasks_kernel.py`: `_is_stale_running` exercised
  directly via `authorize_and_get_task`/`authorize_and_list_tasks`
  using a real `_FakeClock`, covering: past-threshold reported stale;
  just-under-threshold not stale; a `"completed"` task never reported
  stale regardless of age; `task list`'s `stale_task_ids` correctly
  scoped to only the genuinely stale identifiers; the raw stored
  `status` field is never mutated by either check.
- `tests/unit/test_cli_main.py`: the warning line appears for a task
  the kernel reports as `stale=True`, is absent for one reported
  `stale=False`, and in a `task list` with two records only the one
  whose identifier is in `stale_task_ids` gets the warning -- the other
  record's own output is provably unaffected.

## Residual limitations, stated plainly

- The 30-minute threshold is a fixed constant, not configurable via
  any flag or environment variable -- a deliberately narrow, additive
  work package; a configurable threshold was not requested and was not
  built.
- This is purely a read-time signal. `jarvis task list` run against a
  store with very many tasks still relies on `authorize_and_list_tasks`'s
  own existing broad-recall-then-filter approximation (the same
  limitation already documented for `job_application.list`).
- No voice grammar was added -- `task status`/`task list` have never
  had voice grammar, and this work package does not change that.
