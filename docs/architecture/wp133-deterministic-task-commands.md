# Deterministic task-management commands (WP-133, 2026-09-12)

## Status

Real, implemented. No ADR -- no new `CapabilityId` registered in
`kernel.capabilities.build_default_registry()`, no new `Effect`/`Tier`,
no new authorization path, no voice grammar. Reuses
`authorize_and_get_task`/`authorize_and_list_tasks` (both already
`Tier.ALLOW`) completely unmodified.

## What was investigated

`kernel.intent.resolve_intent()` had zero task-related grammar at
all -- `jarvis do "..."`/`jarvis ui` could not look up or list tasks
by natural language; a user always had to know the dedicated
`jarvis task status`/`jarvis task list` subcommands.

## What was built

Two new, router-only commands, confined entirely to `kernel.router`
(mirroring WP-114's own `_resolve_communications_command` precedent
exactly, including its reasoning for why this isn't added to the
shared `resolve_intent()`):

- `"task status <task_id>"` -- everything after the fixed prefix,
  verbatim, is the task id (mirrors `resolve_intent()`'s own
  "read <path>" shape). No id following it is a terminal
  `UnrecognizedIntent` (never a silent fall-through), matching
  `_resolve_communications_command`'s identical "read email" reasoning.
- `"list tasks"` -- a single, fixed, exact-match, zero-argument
  command listing every real task, unfiltered
  (`authorize_and_list_tasks(status=None)`). No "list `<status>` tasks"
  filtered variant in this pass -- a real, separate, small addition,
  not built speculatively.

**A real structural collision found and avoided, not just a naming
choice**: `authorize_and_get_task`/`authorize_and_list_tasks` reuse
`memory.get`/`memory.retrieve`'s own real, already-registered
capability ids internally -- but `memory.retrieve` is *also* the
capability id the pre-existing `"recall <query>"` command already
resolves to, and that id is one of the four entries already wired in
`kernel.capability_dispatch.PLAN_STEP_EXECUTORS`. Reusing
`memory.get`/`memory.retrieve` as the *routing* label for `"task
status"`/`"list tasks"` would have made `authorize_and_route`'s own
generic `PLAN_STEP_EXECUTORS` branch catch them first and call
`authorize_and_recall(query=...)` with the wrong arguments shape
entirely. Two new, deliberately **unregistered** `CapabilityId`
values -- `task.status`/`task.list` (`kernel/router.py`, not
`kernel/capabilities.py`, since they are router-internal labels, not
real static capabilities) -- exist purely so the router can report a
precise, honest `capability_id` and dispatch to two new, dedicated
execution branches in `authorize_and_route`, checked *before* the
generic `PLAN_STEP_EXECUTORS` lookup could ever collide with them.
This is not a new authorization primitive: the real authorization
these routes cause is still exactly `memory.get`/`memory.retrieve`,
performed by `authorize_and_get_task`/`authorize_and_list_tasks`
internally, completely unmodified.

`jarvis ui`'s own chat rendering gained two new summarizer functions
(`_summarize_task_status`/`_summarize_task_list`), extending the
already-"exhaustive by design" `_summarize_execution_result` dispatch
table. `jarvis do`'s own CLI print path needed **no new code at all**
-- it already renders every execution result generically via `!r`,
the same, pre-existing, uniform fallback every other result type not
specially handled already uses.

## What was deliberately not built

- No `"cancel task <id>"`/`"retry task <id>"`/`"recover task <id>"`
  grammar -- these are `Tier.CONFIRM`/dynamic-effect actions (`memory.update`),
  structurally incompatible with `PLAN_STEP_EXECUTORS`'s own
  `Tier.ALLOW`-only ceiling (ADR-0062); adding them here would mean
  either violating that ceiling or building a second, router-specific
  higher-tier execution path -- exactly the kind of new mechanism this
  work package's own hard boundary ("no automatic execution from
  ambiguous commands") warns against. These remain CLI-only, matching
  `jarvis task cancel`/`retry`/`recover`'s own existing, deliberate
  scope.
- No `"list <status> tasks"` filtered variant, no voice grammar (the
  "no voice work" hard boundary is reason enough on its own, mirroring
  `_resolve_communications_command`'s own first, independently-
  sufficient reason).

## Testing

`test_router_kernel.py`: `route_deterministically` resolves both new
commands correctly, refuses a bare "task status" with no id, and
proves the new grammar does not collide with the pre-existing "recall
<query>" command; two real, unmocked, end-to-end `authorize_and_route`
tests prove both commands are actually *executed* (not just
recognized) against real tasks. `test_ui_server.py`: two real,
unmocked HTTP round trips through the running server prove the same
end-to-end path via `POST /api/command`; direct unit tests for both
new summarizer functions cover every real branch (found/not-found,
reason present, stale, malformed record, empty list, mixed
real/malformed list), restoring `ui_server.py`'s 100% branch coverage.
`lint-imports`/`mypy --strict` confirm no layering violation and no
new authorization surface.
