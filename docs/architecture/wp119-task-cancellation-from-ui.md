# Task cancellation from the UI (WP-119, 2026-09-11)

## Status

Real, implemented. No ADR -- a direct UI-layer counterpart to WP-117's
own already-classified `authorize_and_cancel_task`, reused completely
unmodified. No new `CapabilityId`/`Effect`/`Tier`, no new
authorization path.

## The real gap

`jarvis ui`'s frontend gained a real "Run" button (WP-112) the moment
a task could be run from a second, explicit action separate from
creation. WP-117 then added real task cancellation as a kernel
capability and a CLI subcommand (`jarvis task cancel`) -- but `jarvis
ui` itself never gained any way to trigger it. A human chatting
through the web UI who created a task and changed their mind, or who
watched `GET /api/tasks/<id>` polling report a status that stopped
changing (WP-116's stale signal), had no button to press and no
endpoint to call -- they would have to drop to a separate terminal and
run `jarvis task cancel <id>` by hand, breaking the "just use the web
UI" story WP-108 through WP-114 otherwise maintained.

## The mechanism

`POST /api/tasks/<task_id>/cancel` (`_handle_cancel_task` in
`cli/ui_server.py`) reuses `kernel.tasks.authorize_and_cancel_task`
(WP-117) completely unmodified -- the exact same function `jarvis task
cancel` already calls, the exact same `memory.get`-then-maybe-
`memory.update` shape, the exact same `Tier.CONFIRM` floor for the
actual transition. Unlike `_handle_run_task`, no separate server-side
goal lookup is needed first: `authorize_and_cancel_task` already does
its own lookup internally and returns a real, honest
`cancelled`/`reason` pair either way.

Response shape: `{"task_id": ..., "granted": ..., "cancelled": ...,
"reason": ...}`. An unknown-but-well-formed task id is *not* an
HTTP-layer 404 -- it is a real, granted (`Tier.ALLOW`) lookup that
simply found nothing, surfaced as `cancelled: false` with the reason
`"No task found for this identifier."`, exactly mirroring what
`authorize_and_cancel_task` itself already returns for that case. Only
a genuinely empty task id (`/api/tasks//cancel`) is rejected before
any kernel call, at `404`, matching `_handle_run_task`'s own existing
empty-id handling.

As with cancellation everywhere else in this codebase: cancelling a
`"running"` task does not interrupt any real, in-flight execution --
there is none to interrupt in this single-threaded server (the exact
same reasoning `docs/architecture/task-cancellation.md` already
states for the CLI path).

## Frontend

A real "Cancel" button now appears next to "Run" on every
`task_created` message. Clicking it calls the new endpoint; a granted
cancellation disables the button and shows "Cancelled"; a real refusal
(the task already finished, or doesn't exist) re-enables the button
and shows the real reason as a task status line, not an error bubble
-- refusing to cancel an already-completed task is a normal, expected
outcome, not a failure. A genuine network/server error still shows as
an error bubble and re-enables the button, mirroring "Run"'s own
established pattern exactly.

## Testing

`tests/unit/test_ui_server.py`: an empty task id returns 404; an
unknown-but-well-formed task id returns 200 with `cancelled: false`
and the real "not found" reason (not 404 -- see "the mechanism"
above); a real, independently-created task is genuinely cancelled
end-to-end with nothing mocked; a real refusal (already-completed)
returns 200 with `cancelled: false` and its own reason, not an error
status; a handled kernel error (`MemoryRecordNotFoundError`) reports a
clean 400; an unexpected error reports a clean 500 with no leaked
traceback.

In passing, this work package also corrected one pre-existing, stale
one-line docstring claim on `_JarvisUiRequestHandler` ("exactly two
real routes"), already inaccurate since WP-111/WP-112 added the
`/api/tasks/<id>` family -- a one-line factual fix directly adjacent
to what this work package was already touching, not a separate,
unscoped cleanup pass.

## Residual limitations, stated plainly

- No automated test exercises the actual browser-side JS click
  handler or button state transitions -- this repository has no JS
  test framework or browser-automation dependency, the same,
  already-established limitation WP-110's own design doc names for
  `runTask`'s identical shape.
- No voice grammar -- cancellation has none anywhere in this codebase.
