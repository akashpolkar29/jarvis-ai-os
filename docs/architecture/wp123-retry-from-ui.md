# A real "Retry" button in `jarvis ui` (WP-123, 2026-09-12)

## Status

Real, implemented. No ADR -- this is a pure UI counterpart to an
already-classified, already-Accepted capability path (`memory.update`,
ADR-0063), exactly mirroring WP-119's own "UI counterpart to task
cancellation" precedent.

## What was missing

WP-121 built `authorize_and_retry_task` and `jarvis task retry` (CLI
only). WP-121's own report named the gap directly: "no dedicated UI
button (a real, separable follow-up, not built unprompted -- the UI's
existing generic 'Run' button would need its own new state to
distinguish 'run' from 'retry' meaningfully)." This closes exactly that
gap.

## What was built

`POST /api/tasks/<task_id>/retry` (`src/jarvis/cli/ui_server.py`)
reuses `kernel.tasks.authorize_and_retry_task` (WP-121) completely
unmodified -- the exact same function `jarvis task retry` already
calls, which itself delegates unmodified to `authorize_and_run_task`
once it confirms the task is genuinely `"failed"`. Mirrors
`_handle_cancel_task`'s own shape: no server-side goal lookup is
needed here either, since `authorize_and_retry_task` already does its
own lookup and `"failed"`-only status check internally. Because that
delegation genuinely runs a real plan (unlike cancel), this reuses the
same, wider `_HANDLED_TASK_RUN_ERRORS` tuple `_handle_run_task` already
uses (adding `PlanningError`/`PlanValidationError` on top of the
narrower routing-error tuple), not the narrower one `_handle_cancel_task`
uses.

The frontend (`ui_static/index.html`) gained a real `retryTask()`
function, mirroring `cancelTask()`'s own shape, plus a small helper,
`addRetryButtonIfFailed(messageEl, taskId, status)`, called from every
real place a task's own status can first become visible as `"failed"`:

- `runTask`'s own synchronous response (running a task in this
  single-threaded server completes the whole plan before the HTTP
  response returns, so a `"failed"` outcome is already known by then);
- a later `pollTaskStatus` status-change message (e.g. a status change
  produced by a separate `jarvis task run`/worker process); and
- a prior retry that itself failed again.

The button is never attached speculatively at task-creation time --
only once a real `"failed"` status has actually been observed, which
is also the only status `authorize_and_retry_task` itself accepts.

## What was deliberately not built

- No retry button on a task's *initial* `task_created` message
  (status is `"created"` at that point, never retryable).
- No client-side retry-count display or attempt-history rendering --
  a real, separate, presentation-only follow-up over WP-121's own
  `"attempts"` field, not this work package's scope.
- No voice grammar -- matches `task cancel`/`task retry`'s own
  existing scope boundary exactly.

## Testing

Backend: `tests/unit/test_ui_server.py`'s new WP-123 section --
not-found-but-granted lookup, empty task id (404), refusal for a
non-`"failed"` task (real round trip via `authorize_and_create_task`),
a real round trip against a task forced to `"failed"` via
`update_task_status` (the same real, shared write path
`authorize_and_run_task` itself uses), a mocked refusal, a handled
kernel error, and the unexpected-error traceback-suppression case --
mirroring the existing `/cancel` test suite's own shape line for line.
100% branch coverage maintained on `ui_server.py`. No JS test
framework exists in this repository (a real, already-documented,
unchanged limitation) -- the new frontend logic was not independently
exercised beyond manual reasoning about its mirrored shape.
