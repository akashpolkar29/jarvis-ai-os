# Safe task retry + durable execution history (WP-121, 2026-09-11)

## Status

Real, implemented. No ADR -- retry reuses `planning.run_plan`'s own
already-Accepted classification (ADR-0062) completely unmodified, via
the exact same `authorize_and_run_task` entry point WP-120 already
hardened. Execution history is a purely additive, backward-compatible
storage field, not a new capability.

## Investigation findings (before writing any code)

- Before this work package, a real execution attempt left no durable
  trace of its own beyond the task's own final `status`/`reason`
  pair. A task that failed, was retried, and failed again a second
  time for a different reason would have its first failure's own
  reason silently overwritten by the second -- the record answers
  "what is the task's status right now," never "what actually
  happened across every attempt."
- `jarvis task run <id> <goal>` (and `jarvis ui`'s `POST
  /api/tasks/<id>/run`) already let a human re-run a `"completed"` or
  `"failed"` task (WP-118's own deliberate, documented
  permissiveness) -- but only by re-supplying the task's own
  identifier and goal through the exact same generic `run` verb used
  for a brand-new task's first attempt. There was no verb naming
  "this task specifically failed and I am explicitly retrying it,"
  and no place to record that distinction.
- Plans themselves are not persisted anywhere -- `planning.run_plan`
  generates a fresh plan from the goal string on every call, "failed"
  or "completed". A retry therefore cannot resume a partially-executed
  plan from where it left off; it can only regenerate and re-run a
  plan for the identical goal, exactly like an ordinary `run` would.
  This is an accepted, pre-existing property of `planning.run_plan`
  (ADR-0062's own `Tier.ALLOW`-only, no-mid-plan-pause ceiling), not a
  new limitation this work package introduces.
- The UI (`jarvis ui`) already renders a task's own `status`/`reason`
  generically; nothing there currently distinguishes a first attempt
  from a retry.

## Retry semantics

`authorize_and_retry_task(task_id, provider=None, ...)` -- a new,
real, explicit, human-triggered verb, deliberately narrower than
`jarvis task run`'s own existing permissiveness:

- Only a task currently `"failed"` may be retried
  (`_RETRYABLE_STATUSES = frozenset({"failed"})`). `"created"`,
  `"running"`, `"cancelled"`, and `"completed"` are all refused
  outright, before `authorize_and_run_task` is ever called, each with
  a real reason naming the task's own current status.
- `"completed"` is deliberately excluded even though `jarvis task
  run` already permits re-running a completed task -- a completed
  task has nothing to retry; "retry" is a real, distinct, explicit
  response to a genuine prior failure, not a general-purpose re-run
  command. A caller that genuinely wants to re-run a completed task
  anyway still has `jarvis task run` for that, unchanged.
- `"cancelled"` is never retried -- it is not in
  `_RETRYABLE_STATUSES` at all, so a human's own explicit cancel
  decision is never silently undone by a retry, mirroring WP-118's
  identical guard for ordinary `run`.
- Once permitted, `authorize_and_retry_task` looks up the task's own
  real, stored `goal` and delegates directly, unmodified, to
  `authorize_and_run_task(task_id, goal, provider, ...)` -- no second
  execution path, no new authorization concept, no new
  `CapabilityId`/`Effect`/`Tier`. `TaskRetryOutcome` wraps the
  delegated call's own real `TaskRunOutcome` (`retried` mirrors
  `claimed`; `status`/`reason` pass straight through).

## Execution history

Every task record gained a real, additive `"attempts"` field: a list
of concluded-attempt entries, each `{"attempt": N, "started_at": ...,
"ended_at": ..., "status": ..., "reason": ...}`. A new entry is
appended only at the moment a `"running"` task concludes (transitions
to `"completed"`, `"failed"`, or `"cancelled"`) -- never at the start
of an attempt, since an attempt that is still running has not
concluded yet and nothing to record. `started_at` is the record's own
`updated_at` from just before this transition (when it became
`"running"`); `ended_at` is the transition's own new timestamp.

This is deliberately the smallest durable representation that answers
"what happened across every attempt," not an event-sourcing framework
and not a duplicate of the existing `EventBus` (WP-111): the `EventBus`
is an in-process, transient notification mechanism with no persistence
of its own (a subscriber that wasn't listening at the time misses the
event, by design); `attempts` is the real, durable, queryable record
living in the task's own stored value, readable by `jarvis task
status`/`list` long after any process that published an event has
exited. Neither mechanism needed for the other to work correctly; kept
separate on purpose.

A retry's own new attempt is **appended alongside** the original
failure's attempt entry, never replacing it -- the original failure
information is never destroyed. A task retried twice and failing both
times accumulates two real, distinct `"failed"` entries, each with its
own `reason`.

## Concurrency protection

Retry needs no new locking code at all: `authorize_and_retry_task`
delegates directly to the exact, unmodified `authorize_and_run_task`,
which already carries WP-120's real, process-safe
compare-and-swap-based claim mechanism (the `"created"`/`"completed"`/
`"failed"` -> `"running"` transition, plus the `"running"` ->
`"running"` refusal that closed WP-120's own real, empirically-found
CI race). Two independent processes both calling
`authorize_and_retry_task` for the same failed task race on the
identical, already-hardened claim -- one wins the `"failed"` ->
`"running"` transition, and the other either fails the earlier
status-gate check (if it reads after the winner has already started,
it sees `"running"`, which is not in `_RETRYABLE_STATUSES`, and is
refused there) or loses the CAS itself inside `authorize_and_run_task`
(if both pass the status-gate check nearly simultaneously). Either way,
two processes never both genuinely execute the same retry at the same
real instant -- proven directly (see Testing below).

## Authorization

Unchanged from `authorize_and_run_task`'s own existing, Accepted
classification (`planning.run_plan`, ADR-0062, `Effect.EXECUTE`/
`Tier.CONFIRM` at the outer gate; every individual plan step
separately authorized, never batch-pre-approved). Retry never
auto-confirms anything -- `physical_confirmation_available`/
`remote_confirmation_available` are threaded straight through to the
identical, unmodified call, exactly like every other real caller.

## Cancellation

A `"cancelled"` task is never retried, full stop -- see Retry
semantics above. `jarvis task cancel`'s own existing behavior is
completely unchanged; retry adds no new way to resume a cancelled
task.

## Audit

No cryptographic audit-chain changes. Every real transition a retry
makes (the `"failed"` -> `"running"` claim, and whatever terminal
transition follows) is a real, separate, hash-chained
`memory.update` record, identical in shape to an ordinary `run`'s own
records -- the audit chain already distinguishes a retry's own two
real writes from an original run's own two real writes purely by
their real, different `previous_status` values (`"failed"` ->
`"running"` only ever happens via a retry or a fresh claim on an
already-failed task, never an original `run`'s own first transition,
which is always `"created"` -> `"running"`).

## Backward compatibility

Existing, pre-WP-121 task records have no `"attempts"` key at all.
`update_task_status` reads `existing.get("attempts")`, defaulting to
an empty list when absent or malformed, so a legacy record loads,
runs, retries, and gains a correct, real first attempt entry exactly
like a brand-new one -- proven directly by a dedicated test
constructing a legacy record via `authorize_and_remember` (bypassing
`write_task_record`, which now always includes `"attempts"`) and
confirming it still loads and runs correctly.

## Testing -- real, process-level proof, not merely unit tests

- `tests/unit/test_tasks_kernel.py`: execution-history accumulation on
  a successful run, an empty-history brand-new task, legacy-record
  backward compatibility, and a full battery of `authorize_and_retry_task`
  tests -- a real retry succeeding, a real retry failing again and
  accumulating a second attempt without destroying the first, refusal
  for each non-retryable status (`created`/`completed`/`cancelled`/
  `running`) with the exact, real reason, denied-confirmation leaving
  the task untouched, and real `TaskStatusChanged` event publication
  (two real transitions for a successful retry, matching an ordinary
  `run`'s own shape exactly).
- `tests/unit/test_tasks_claim_process_safety.py`: a new,
  `_WORKER_COUNT`-process real multiprocessing test,
  `test_real_independent_processes_racing_to_retry_the_same_failed_task_never_run_simultaneously`,
  mirroring WP-120's own headline `run` test exactly -- a real task is
  first driven to `"failed"` synchronously (a real `PlanningError`
  from a malformed plan), then `_WORKER_COUNT` genuinely independent
  OS processes are barrier-released together, all calling the exact
  same, unmodified `authorize_and_retry_task`. The same real property
  is proven: no two real winners' own measured `[start, end]`
  wall-clock intervals overlap. Run 3/3 consecutive times normally and
  3/3 consecutive times under `taskset -c 0,1` (the same adversarial
  CPU-contention technique that originally exposed WP-120's real
  "running" -> "running" CAS bug) with zero flakiness.
- `tests/unit/test_project_kernel.py`: the one pre-existing exact-dict
  assertion updated for the new `"attempts"` field (`project.py`
  shares `tasks.py`'s storage helpers, so it gains the same field).
- `tests/unit/test_cli_main.py`: `jarvis task retry` reporting a
  granted retry, a refused retry with its real reason, the one real
  "not found" case where no `status:` line exists at all (proving the
  CLI's own retry-printing code does not duplicate the reason line),
  and the missing-task-id `SystemExit` case.

## Files changed

- `src/jarvis/kernel/tasks.py`: `"attempts"` field on
  `write_task_record`/`update_task_status`; `_RETRYABLE_STATUSES`,
  `TaskRetryOutcome`, `authorize_and_retry_task`.
- `src/jarvis/cli/main.py`: `task retry <task_id>` subparser and
  dispatch, `task_retried` field on `_CommandOutcome`, printing.
- `tests/unit/test_tasks_kernel.py`,
  `tests/unit/test_tasks_claim_process_safety.py`,
  `tests/unit/test_project_kernel.py`, `tests/unit/test_cli_main.py`.

## Open limitations, stated plainly

- A retry regenerates and re-runs a plan from the goal string; it
  cannot resume a partially-executed plan from its own point of
  failure. This is `planning.run_plan`'s own existing, accepted
  property (no plan persistence anywhere), not a new gap WP-121
  introduces.
- No natural-language/voice grammar for retry -- `jarvis task retry`
  is CLI-only, matching `jarvis task cancel`'s own identical, existing
  scope boundary.
- The UI (`jarvis ui`) gained no dedicated retry button in this work
  package -- the prompt's own "do not redesign the UI" caveat and
  "only if the backend semantics make the distinction meaningful"
  condition were weighed directly: the UI's existing `task_created`
  message already has a generic "Run" button (WP-112) that, for an
  already-`"failed"` task a user creates a fresh run on, would need
  its own new endpoint and its own new button state to distinguish
  "run" from "retry" meaningfully -- real, additive frontend work
  this work package's own explicit scope did not call for building
  unprompted. `jarvis task retry` is the real, working entry point
  today; UI exposure is a clean, separable follow-up.
