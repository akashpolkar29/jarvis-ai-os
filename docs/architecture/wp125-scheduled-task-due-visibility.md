# Scheduled task due/not-due visibility (WP-125, 2026-09-12)

## Status

Real, implemented. No ADR -- purely additive derived state, mirroring
WP-116's own already-established "compute fresh, never persist, expose
via the outcome" shape exactly. No new stored field, no new task
status, no new capability.

## What was missing

WP-122 added real, one-time local task scheduling and a `scheduled_at`
field, already printed by `jarvis task status`/`jarvis task list`. But
neither command told a user whether a scheduled task's own due time
had actually passed yet -- only the raw timestamp was visible, and a
user had to compare it against the current time themselves.

## What was built

`is_task_due(data, now)` -- the exact, unmodified due-time predicate
WP-122 originally wrote as `kernel.worker._is_due` -- moved into
`kernel.tasks` (made public, no leading underscore) so it can be
reused by both `kernel.worker` (unchanged behavior) and the two real
task-lookup composition functions. `kernel.worker` now imports this
one, shared implementation instead of keeping its own private copy --
a real, small deduplication, not a behavior change.

- `TaskGetOutcome.due: bool` (new field, default `False`) -- mirrors
  `stale`'s own shape exactly. `True` only when the record is
  currently `"created"`, has a real `scheduled_at`, and that time has
  passed a real `ClockPort.now()`.
- `TaskListOutcome.due_task_ids: frozenset[str]` (new field, default
  empty) -- mirrors `stale_task_ids`'s own shape exactly.
- `jarvis task status`/`jarvis task list` (`_print_one_task_record`)
  print a `due: true`/`due: false` line immediately after
  `scheduled_at`, but only when `scheduled_at` is present -- due-ness
  is meaningless without a real schedule to be due (or not yet due)
  against, mirroring `stale`'s own precedent of only ever being
  interesting in context.

## What was deliberately not built

- No due-ness field for a task that isn't currently `"created"` --
  once a scheduled task runs, cancels, or fails, "due" no longer means
  anything real; the field stays `False` in that case (not applicable,
  not "not due").
- No UI/voice exposure -- matches `task schedule`'s own already-
  documented scope boundary exactly.
- No change to the worker's own real due-time filtering behavior --
  `run_pending_tasks_once` calls the exact same predicate, unmodified,
  just imported from its new home.

## Testing

`test_tasks_kernel.py`: `authorize_and_list_tasks` returns the correct
`due_task_ids` (mirroring the existing stale-task-ids list test);
`authorize_and_get_task` reports `due=True` for a past-scheduled
created task, `due=False` for a future-scheduled one, `due=False` for
an unscheduled one, and `due=False` once a scheduled task has already
run. `test_cli_main.py`: `due: true`/`due: false` print correctly
alongside `scheduled_at`, and no `due:` line prints when there is no
schedule at all -- both for `task status` and `task list`. Existing
`kernel.worker` tests (`test_worker_kernel.py`,
`test_worker_scheduling_process_safety.py`) were updated to import
`is_task_due` from its new home in `kernel.tasks` rather than the
retired `kernel.worker._is_due` -- behavior unchanged, proven by the
same tests passing unmodified in substance.
