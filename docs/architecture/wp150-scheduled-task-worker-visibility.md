# Scheduled task worker visibility (WP-150, 2026-09-12)

## Status

Real, implemented. No ADR -- pure CLI-output disambiguation, no new
task status, no new capability, no `Effect`/`Tier` change.

## What was investigated

`jarvis task worker`'s ordinary (non-`--dry-run`) output printed the
identical `"worker: no eligible ('created') tasks found."` line for
two real, different states: genuinely zero `"created"` tasks in the
store, and one or more real `"created"` tasks that exist but are
scheduled (WP-122) for a future time and therefore correctly not yet
attempted this pass. An operator watching `jarvis task worker`'s
ordinary output had no way to tell "nothing to do, ever" apart from
"something is queued, just not yet" without separately running
`--dry-run`.

## What was built

`_print_worker_pass` gained an additive, keyword-only `not_due_count`
parameter: when a pass's own `attempted` tuple is empty and
`not_due_count > 0`, it now prints `"worker: no tasks due right now (N
'created' task(s) scheduled for later)."` instead of the generic
message. A pass that attempted at least one task is completely
unaffected -- the new parameter is never even computed in that case.

A new, private helper inside `_run_task_worker`,
`_print_pass_with_scheduling_context`, wraps both existing call sites
(`--once` and continuous mode): only when `pass_outcome.attempted` is
empty does it make one extra, real `authorize_and_list_tasks(status=
"created")` read (the same call `--dry-run` already makes) and count
how many of the returned records are absent from `due_task_ids`
(WP-125) -- an unscheduled `"created"` task is always immediately
eligible, so if the pass genuinely attempted nothing, every `"created"`
record this second read finds must be scheduled-but-not-yet-due.

## What was deliberately not built

- No new task status, no persisted "not due" flag -- `due`/
  `not_due_count` are both computed fresh at print time from the
  existing `due_task_ids` (WP-125), exactly like `--dry-run` and
  `jarvis task list`/`status` already do.
- No change to `run_pending_tasks_once`/the worker's own discovery or
  claim logic -- this is presentation-only, layered entirely in
  `cli/main.py`.
- No UI-side equivalent -- `jarvis ui` has no worker-pass view at all
  today; out of this work package's own scope.

## Testing

Three new tests: the pre-existing "no eligible tasks" case now
explicitly mocks `authorize_and_list_tasks` to return zero records
(catching a real hermeticity gap this change introduced -- the new
helper's extra call was previously hitting the real, unmocked default
SQLite path in that test and the two `--max-passes` tests, silently
creating a stray `memory.sqlite3`; all three now mock it); a new test
proves the "scheduled for later" message and count for two genuinely
not-due records; a new test proves the extra read is skipped entirely
(never called) when a pass attempts at least one task.
