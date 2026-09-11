# Task list status filtering via the typed router (WP-136, 2026-09-12)

## Status

Real, implemented. No ADR -- no new registered `CapabilityId`, no new
`Effect`/`Tier`, no new authorization path, no voice grammar. Extends
WP-133's own `"list tasks"` grammar and reuses
`authorize_and_list_tasks`'s already-existing `status` parameter
completely unmodified.

## What was built

`"list <status> tasks"` and `"list scheduled tasks"` generalize
WP-133's own bare `"list tasks"` into one real, single grammar shape
(`"list " + <word> + " tasks"`), not three separate fixed phrases:

- `<word>` empty -> unfiltered list (WP-133's own existing behavior,
  byte-for-byte unchanged).
- `<word>` one of the five real, reachable statuses (`created`,
  `running`, `completed`, `failed`, `cancelled` --
  `kernel.tasks.VALID_TASK_STATUSES`'s own reserved
  `"waiting_approval"` deliberately excluded, since no real task can
  ever reach it) -> `authorize_and_list_tasks(status=<word>)`, the
  identical `TASK_LIST_COMMAND_LABEL` reused, just with a real
  `status` argument now.
- `<word> == "scheduled"` -> a distinct label,
  `task.list_scheduled`, since "scheduled" is not itself a real task
  status (a scheduled task is any `"created"` task that also has a
  real `scheduled_at`, WP-122). Calls
  `authorize_and_list_tasks(status="created")`, then applies one
  further, local, read-only filter (`scheduled_at is not None`)
  before returning -- a new `TaskListOutcome` built from the real
  outcome's own records/`stale_task_ids`/`due_task_ids`, intersected
  with the filtered set, not re-computed from scratch.
- Any other `<word>` -> a real "list ___ tasks" shape matched, but
  ___ isn't recognized -- terminal `UnrecognizedIntent`, never a
  silent guess (mirrors `_resolve_communications_command`'s own
  established "recognized trigger, unresolvable rest" reasoning).

`jarvis ui`'s own summarizer needed **no change at all** -- it already
dispatches purely on `isinstance(result, TaskListOutcome)`, so a
filtered result renders identically to an unfiltered one.

## What was deliberately not built

- No CLI/voice grammar for this -- confined entirely to
  `kernel.router`, matching WP-133's own "no voice work" reasoning.
- No new kernel function -- the "scheduled" filter is applied entirely
  within the router's own execution branch, not a new
  `authorize_and_list_scheduled_tasks`-style composition function,
  since it is a one-line, read-only, router-local filter over data
  `authorize_and_list_tasks` already returns.

## Testing

`test_router_kernel.py`: parametrized resolution tests for all five
real statuses, a resolution test for "scheduled", a real end-to-end
execution test proving `"list created tasks"` returns only the
genuinely-created task (not others), and a real end-to-end test
proving `"list scheduled tasks"` returns only the genuinely-scheduled
task out of two real, otherwise-identical tasks. A regression test
proves an unrecognized status word (the reserved `"waiting_approval"`)
resolves to `UNKNOWN`, never a guess. All 59 pre-existing + new router
tests pass; `router.py` remains at 100% branch coverage.
