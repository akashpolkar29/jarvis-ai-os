# Scheduler inspection (WP-140, 2026-09-12)

## Status

Real, implemented. No ADR -- no new `CapabilityId`/`Effect`/`Tier`, no
new task status, no new scheduler. A pure, shared, read-only filter
reused by both `kernel.router` and `jarvis task list`.

## What was built

`kernel.tasks.filter_scheduled_tasks(outcome: TaskListOutcome) ->
TaskListOutcome` -- a real, pure, local filter narrowing a real
`authorize_and_list_tasks(status="created")` result to only its
genuinely-scheduled records (`scheduled_at` present), with
`stale_task_ids`/`due_task_ids` correctly intersected down to the
same subset. No I/O, no authorization decision of its own -- `outcome.decision`
is passed straight through unchanged.

**A real, small refactor alongside the new feature**: WP-136's own
`"list scheduled tasks"` router command had this exact filtering logic
inlined. Extracted here as a shared function so `kernel.router` and
the new `jarvis task list --scheduled-only` CLI flag both call the
same, single implementation -- not two copies of the identical filter.

`jarvis task list --scheduled-only` -- a real, new CLI flag,
mutually exclusive with `--status` (argparse
`add_mutually_exclusive_group`, since a scheduled task is always
`"created"` -- combining them would be meaningless). Calls
`authorize_and_list_tasks(status="created")` then
`filter_scheduled_tasks(...)`, printing the result exactly like any
other `task list` invocation (`scheduled_at`/`due` already print
per-record since WP-125, unchanged).

## What was deliberately not built

- No second scheduler, no recurrence -- purely a read-only view over
  already-stored data.
- No new kernel composition function for the CLI path -- reuses the
  identical `filter_scheduled_tasks` the router already calls.

## Testing

`test_tasks_kernel.py`: `filter_scheduled_tasks` keeps only the
genuinely-scheduled, still-`"created"` record out of three real tasks
(scheduled/unscheduled/completed); a second test proves
`stale_task_ids`/`due_task_ids` are correctly narrowed, not just
`records`. `test_cli_main.py`: `--scheduled-only` requests
`status="created"` and filters correctly; `--status`/`--scheduled-only`
together is a real, deterministic `SystemExit` (argparse's own mutual-
exclusion enforcement). `kernel/router.py`'s existing `"list scheduled
tasks"` tests still pass unmodified against the refactored
implementation. One incidental fix: the new `--scheduled-only` help
text was written without any internal WP/ADR reference from the
start, avoiding the "help text leaks an internal reference" meta-test
this repository already enforces.
