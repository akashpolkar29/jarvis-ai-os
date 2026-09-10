# WP-112: task-execution trigger from the UI (2026-09-10)

## Status

Real, implemented. No new `CapabilityId`/`Effect`/`Tier`, no ADR --
this work package exposes one already-existing, already-classified
kernel function (`kernel.tasks.authorize_and_run_task`) over one new
HTTP endpoint. Nothing about authorization semantics changes.

Roadmap numbering checked directly before starting: the highest real
`WP-\d+` reference was 111 (WP-111, task-event infrastructure).
WP-112 was genuinely free.

## The real gap this closes

WP-111 gave the UI a way to *observe* a task's status. It did not give
the UI a way to *run* one: `kernel.router.authorize_and_route`'s own
`COMPLEX_GOAL` handling only ever creates a task (WP-104's own
explicit, unchanged design) -- there was no way, from `jarvis ui`
alone, to make a created task actually execute. The only existing path
was a separate CLI invocation, `jarvis task run <id> <goal>`, in a
different terminal.

## The change: one new endpoint, zero new authorization logic

`POST /api/tasks/<task_id>/run` reuses `kernel.tasks.authorize_and_run_task`
completely unmodified -- the exact same function `jarvis task run`
already calls. Nothing about the real authorization chain changes:

1. The outer `memory.update`-based "running" transition gate
   (`Effect.WRITE_LOCAL`/`Tier.CONFIRM`) -- unchanged.
2. `planning.run_plan`'s own outer gate (`Effect.EXECUTE`/`Tier.CONFIRM`)
   -- unchanged.
3. Every real plan step's own, separate, individual authorization
   (ADR-0062, no batch pre-approval) -- unchanged, enforced by
   `application/planning/executor.py`, which this work package did
   not touch.

The endpoint reads `UiServerConfig.physical_confirmation_available`/
`remote_confirmation_available` exactly like `POST /api/command`
already does -- no new confirmation concept, no localhost-as-physical-
confirmation inference introduced here either.

## Never automatic

Creating a task and running it remain two real, separately-triggered
actions. A `COMPLEX_GOAL` route still only ever creates a task; running
one requires a second, explicit `POST /api/tasks/<task_id>/run` request,
which the frontend only ever sends when the user clicks a real "Run"
button -- never on task creation, never on a timer, never as a side
effect of polling. This mirrors `jarvis task create`/`jarvis task run`'s
own already-established two-verb separation (WP-107) exactly.

## The goal is looked up server-side, never trusted from the client

The endpoint calls `authorize_and_get_task` first, using the real,
currently-stored goal for the `authorize_and_run_task` call --
the browser's `POST` body is empty; it never supplies its own copy of
the goal text. This means a client cannot request a real plan run for
a goal different from the one the task was actually created for, even
in principle.

## Response shape

```json
{
  "task_id": "...",
  "granted": true | false,
  "status": "completed" | "failed" | null,
  "reason": "..." | null
}
```

Mirrors `kernel.tasks.TaskRunOutcome`'s own real fields directly, the
same "no re-derivation, no separate guess" discipline WP-111 already
established for `GET /api/tasks/<task_id>`.

## Error handling

`404` for an unknown or empty task id (mirroring the `GET` endpoint's
own behavior exactly). A real, listed exception
(`PlanningError`/`PlanValidationError`, plus the same memory-store/
OS-level errors `POST /api/command` already handles) becomes a clean
`400`. Any other, truly unexpected exception is caught by a final
backstop and reported as a generic `500`, logged server-side, never
echoed to the browser -- the identical discipline `POST /api/command`
already established.

## A real, pre-existing limitation, found while building this, not introduced by it

`authorize_and_run_task`'s own exception handling only catches
`(PlanningError, PlanValidationError)` -- a real, uncaught exception
from *within* a plan step's own execution (e.g. a wired
`PLAN_STEP_EXECUTORS` capability raising `PathOutsideAllowedScopeError`)
propagates all the way up through `execute_plan` -> `authorize_and_run_plan`
-> `authorize_and_run_task`, uncaught anywhere in that chain. The
task's own stored status is left at `"running"` permanently in that
case -- not because this endpoint fails to handle the exception (it
does, cleanly, at the HTTP layer, reporting a real `400`), but because
the underlying kernel function never itself transitions the task to
`"failed"` for this class of error.

**Confirmed directly, not assumed, to be pre-existing**: `jarvis task
run` (the CLI) has the exact same property today -- it was never fixed
by this work package, and `kernel.tasks.authorize_and_run_task` was
deliberately not modified here (it is explicitly meant to stay "reused
unmodified"; whether every real plan-step exception should also
transition a task to `"failed"` is a genuine, separate architectural
decision -- possibly touching how much `authorize_and_run_task` should
know about *why* a step failed -- that deserves its own explicit
review, not a change bundled quietly into "add a UI trigger for an
already-existing function." Live-verified directly: a real task whose
plan step raised `PathOutsideAllowedScopeError` was left at `status:
"running"` after three real run attempts, each cleanly reported as a
`400` to the caller.

## Reusing WP-111's `EventBus`

The endpoint passes `self.server.event_bus` (WP-111's own, real,
shared bus) into `authorize_and_run_task`, so a real run triggered from
the UI publishes real `TaskStatusChanged` events into the same
in-process bus WP-111 already wired subscribers into -- the first real
caller in this codebase for which that was possible (WP-111's own
`authorize_and_route` call site can only ever produce `TaskCreated`,
never a status change, since the router itself never runs a task).

## Frontend: a real, explicit "Run" button, disabled after use

Every `task_created` message now includes a real "Run" button. Clicking
it disables the button immediately (`"Running..."`), sends the real
`POST`, and:

- on a granted response: shows `"Started"`, **stays disabled** (a
  deliberate choice -- re-running an already-started task is not
  unsafe, since every step is still individually authorized, but it is
  confusing/wasteful, and the button's own job is to prevent the easy,
  accidental case, not to add new server-side validation
  `authorize_and_run_task` itself doesn't have),
- on any real failure (network error, `404`, `400`, `500`): shows a
  real error message and **re-enables**, so the user can retry.

No progress is fabricated -- the button's own state reflects only what
the real `POST` response said; the existing WP-111 polling mechanism
(already wired to every `task_created` message) continues to report
real status changes afterward, unchanged.

## Testing

`tests/unit/test_ui_server.py` (+6 tests): `404` for an unknown/empty
task id, a real round trip proving the endpoint's own real goal lookup
against a real, independently-created task record (with
`authorize_and_run_task` itself mocked to stay hermetic, independent
of a real local Ollama server), a real `PlanningError` becoming a
clean `400`, an unexpected exception never leaking its message, and a
malformed stored record becoming a clean `500`. 100% coverage
maintained on `cli/ui_server.py`.

**Frontend**: the real, shipped Run-button JS was executed live,
unmodified, against a real running server (two real backend
configurations: one where the run succeeds, one where it raises) using
the same minimal DOM-stub harness WP-110/WP-111 already established --
8 checks for the success path (button appears, disables on click,
shows "Running..." then "Started", stays disabled, a real status
message appears) and 3 for the failure path (button re-enables, label
reverts, a real error message appears). Not part of the committed gate
suite, the same stated limitation WP-110/WP-111 already documented.

## Security / authorization -- unchanged

`127.0.0.1`-only binding, single-threaded server, no new capability,
no new `Effect`/`Tier`. ADR-0058 (no automated job-application
submission) and ADR-0062 (per-step authorization, no batch
pre-approval) remain completely untouched -- neither
`application/planning/` nor the authorization kernel were modified in
this work package at all.
