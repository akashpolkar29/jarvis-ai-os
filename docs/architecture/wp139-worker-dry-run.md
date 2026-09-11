# Worker dry-run visibility (WP-139, 2026-09-12)

## Status

Real, implemented. No ADR -- no new `CapabilityId`/`Effect`/`Tier`, no
new task status, no change to `jarvis.kernel.worker` itself. A pure
CLI-layer addition reusing `authorize_and_list_tasks`'s own already-
computed `due_task_ids` (WP-125) directly.

## What was built

`jarvis task worker --dry-run` -- a real, read-only inspection of
which `"created"` tasks are currently eligible/due, without claiming
or running any of them. Deliberately takes priority over `--once`/
`--max-passes`/`--poll-interval-seconds`: if given, none of those are
consulted at all.

**Why this needed no worker redesign**: `run_pending_tasks_once`
already computes exactly the signal a dry-run needs --
`authorize_and_list_tasks(status="created")` already returns a real
`due_task_ids` field (WP-125's own already-computed, already-tested
due-time predicate). The dry-run branch calls that same function
directly and prints each record's own real `goal`/`due` state --
`run_pending_tasks_once`/`authorize_and_run_task` are never called at
all, so nothing is ever claimed, run, or authorized past the
`Tier.ALLOW` list read itself (the same read `jarvis task list
--status created` already performs).

## What was deliberately not built

- No new worker-internal "plan" or "preview" data structure --
  reusing the existing `TaskListOutcome`/`due_task_ids` shape directly
  was sufficient and required no new kernel code.
- No dry-run mode for continuous/`--max-passes` operation beyond "if
  `--dry-run` is set, do the one-shot inspection and exit" -- a
  dry-run is inherently a single, deterministic snapshot; looping it
  would just repeat the identical query.

## Testing

`test_cli_main.py`: a real, no-tasks case reports "no eligible
tasks found" (matching the existing empty-pass message); a real case
with one due and one not-yet-due task proves both are printed with
the correct `due` state, and proves `run_pending_tasks_once` is never
called even when `--once` is also given on the same command line.
