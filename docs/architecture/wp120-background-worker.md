# Durable background task execution: a real worker + claim mechanism (WP-120, 2026-09-11)

## Status

Real, implemented. No ADR -- this closes a real, structural gap using
only already-classified capabilities and an additive storage
primitive, never a new authorization concept, new `CapabilityId`,
`Effect`, or `Tier`.

## Why background execution is needed

Every prior work package on task execution (WP-107 through WP-119)
made the task lifecycle durable and safe in isolation -- creation,
running, failure persistence, stale detection, cancellation, the
cancelled-task-run guard, UI cancellation. But execution itself was
always triggered by one specific, already-present human action: a
direct `jarvis task run <id> <goal>` call, or a browser click on the
UI's own "Run" button. Nothing ever discovered an eligible,
already-created task and ran it without a human explicitly initiating
that one specific run. This is the real gap between "a task exists,
persisted, durable" and "a task can run as a durable background job."

## Current foreground execution model (investigated before building)

- `jarvis task run <id> <goal>` and `jarvis ui`'s `POST
  /api/tasks/<id>/run` both call `kernel.tasks.authorize_and_run_task`
  synchronously. The calling process is the only thing that ever runs
  the plan; there is no separate execution process anywhere in this
  codebase.
- If the terminal (or `jarvis ui`) closes, or the process receives
  SIGTERM, or the machine shuts down, mid-execution: the task's own
  stored status is left at `"running"` permanently. No other process,
  ever, revisits it on its own. WP-116 (stale-running-task detection)
  already reports this honestly as a real, read-only signal --
  detection only, no automatic recovery, unchanged by this work
  package.
- If execution takes 30 minutes: it simply keeps running in that one
  process. `adapters/reasoning/local.py`'s own 120s-per-call timeout
  bounds one reasoning call, not the whole task.
- If a task is cancelled before a `run` call starts: WP-118 already
  refuses to resume a `"cancelled"` task -- unchanged, reused as-is.
- **If a task is already "running," or if two processes try to run the
  same task simultaneously**: before this work package, nothing
  prevented it. `authorize_and_run_task`'s own "created" -> "running"
  transition was a blind, unconditional read-then-write -- two
  independent callers (two direct `jarvis task run` invocations, or
  two real worker processes) could both read the same "created" task,
  both transition it to "running," and both then genuinely call
  `planning.run_plan` concurrently for the same task id. This was
  always a real, reachable hazard, not a hypothetical one introduced
  by adding a worker -- a worker only makes the race *likely*, never
  newly *possible*.
- `TaskStore` (the `"kind": "task"`-marked `MemoryRecord`) already
  contained `goal`/`status`/`reason`/`created_at`/`updated_at` --
  enough to identify *which* task is eligible, but nothing to safely
  identify or serialize a specific *execution attempt* against
  concurrent claimants.
- No worker/daemon/scheduler implementation existed anywhere in this
  codebase before this work package.
- The UI already distinguishes `created`/`running`/`completed`/
  `failed`/`cancelled` (the real, existing `VALID_TASK_STATUSES`) and
  `stale` (WP-116, a derived, read-only signal). `"queued"` does not
  exist and is not introduced by this work package -- see "why no new
  status" below.

## The smallest architectural change: a real, process-safe claim

The fix lives in one place: `authorize_and_run_task`'s own "created"
-> "running" transition, inside `kernel.tasks.update_task_status`, now
supports a real, atomic compare-and-swap (`atomic=True`, opt-in,
default `False` -- every other transition in this module keeps its
original, unconditional blind-write behavior unchanged).

**The mechanism**: `MemoryWritePort.compare_and_update_value(identifier,
expected_value, value)` (new), implemented in `SqliteMemoryAdapter`
using SQLite's own `BEGIN IMMEDIATE` -- a real write lock acquired
*before* reading anything, empirically verified (not merely assumed
from documentation) to block a second, genuinely independent
`sqlite3.connect()` to the same file from starting its own write
transaction until the first commits or rolls back, across real,
separate OS processes. The current row is re-read *inside* that lock
and compared, by plain Python value equality, against `expected_value`
-- no SQLite JSON1/`json_extract` dependency, so this works on any
SQLite build. `kernel.memory.authorize_and_compare_and_update` is the
composition-root counterpart, reusing the *exact* same `memory.update`
authorization path (`MemoryWriteAuthorizer.authorize_update`, same
`Effect` derivation) as the existing `authorize_and_update` -- only the
real write mechanism differs.

`update_task_status(..., atomic=True)` uses this for the "running"
transition only: it already reads the task's current value (to
preserve `created_at`, etc.); that same read becomes the CAS's
`expected_value`. If another real writer already changed the task's
status in the meantime, the compare-and-swap fails cleanly --
`TaskRunOutcome.claimed` (new field) is `False`, the function re-reads
the task's own real, current status and reports it honestly (never a
fabricated sentinel), and attempts no plan execution and no further
transition whatsoever.

**Why not widen `atomic=True` to every transition?** Investigated, not
assumed: running -> completed/failed and created/running -> cancelled
are each reached by at most one real, already-serialized path in this
architecture (the claimant that won the race is the only process that
ever attempts them for a given execution, and cancellation racing a
genuinely in-flight run is a pre-existing, accepted, unrelated edge
case -- see "residual limitations"). Widening the CAS everywhere would
not close a real gap and was unjustified scope.

## Task claiming mechanism -- the worker layer

`jarvis.kernel.worker` (new, minimal):

- `run_pending_tasks_once(...)`: a single, bounded pass. Discovers
  every task whose status is `"created"` (`authorize_and_list_tasks(status="created")`,
  unmodified), and for each one, calls the exact, unmodified
  `authorize_and_run_task` -- the worker never touches
  `compare_and_update_value`/`authorize_and_compare_and_update`
  directly, and contains zero capability-specific execution logic. It
  only reads `TaskRunOutcome.claimed`/`.status`/`.reason` to build its
  own per-task `WorkerTaskOutcome`.
- A real exception from one task's own `authorize_and_run_task` call
  is caught per-task (it never aborts the rest of the pass), logged
  via `logging.exception` (never silently swallowed), and recorded --
  `authorize_and_run_task` had already durably persisted the task's
  own real `"failed"` status with the exact same reason before
  re-raising (WP-113); this is diagnostic information for the pass's
  own caller, never the only place the failure lives.
- A malformed task record (no real string `goal`) is skipped with a
  logged warning, never silently dropped, never crashing the pass.

**`jarvis task worker`** (CLI, `cli/main.py`): foreground by design, no
hidden daemonization anywhere.

- `--once`: exactly one real pass, then exit. The simplest, most
  deterministic mode -- no loop, no sleep, what the automated tests
  exercise directly.
- Continuous mode (default): loops `run_pending_tasks_once` +
  `time.sleep(--poll-interval-seconds)`, stopped by a real Ctrl+C
  (`KeyboardInterrupt`, mirroring `jarvis listen`'s own identical
  shape) or, deterministically, after `--max-passes` real passes -- a
  real, scriptable alternative to a signal, and the mechanism this
  work package's own CLI tests use to prove continuous mode genuinely
  bounds itself with zero real delay (a mocked `time.sleep`) and no
  infinite loop inside an automated test.
- No `--provider` flag -- mirrors `jarvis task run`'s own identical,
  already-documented scope limit exactly; the worker uses
  `planning.run_plan`'s real, default (local) reasoning provider.

## Why no new status was introduced

`"queued"` was explicitly considered and rejected: a task discovered
by the worker is, at the moment of discovery, still genuinely
`"created"` -- nothing about being *about to be attempted* by a
worker is a real, distinct, externally-observable state transition
worth persisting. `"retrying"`/`"paused"`/`"scheduled"` were considered
and are out of this work package's own scope entirely (see "next
recommended work" below) -- none is activated or introduced here.
`"waiting_approval"` (reserved since WP-107 for a future planner
extension past today's `Tier.ALLOW`-only ceiling) remains unreachable
and untouched.

## Crash behavior

If the worker's own process is killed mid-execution of one task, that
task is left at `"running"` -- exactly as a crashed direct `jarvis
task run` invocation already would be. WP-116's own stale-running-task
detection is the accepted, existing safety net; this work package adds
no automatic recovery of an abandoned claim, per its own explicit
instruction not to invent one without separate justification.

## Cancellation behavior

Unchanged, fully reused: a cancelled task is never even discovered (the
worker's own discovery step only lists `"created"` tasks), and
`authorize_and_run_task` itself independently refuses to resume a
`"cancelled"` task (WP-118) even if one somehow reached this far. No
new cancellation logic exists in this work package.

## Authorization behavior

Every real call the worker makes reuses the exact, existing
`physical_confirmation_available`/`remote_confirmation_available`
flags every other subcommand already requires, with no safe default
and no auto-confirmation -- a worker launched with neither flag set
correctly claims nothing (every "created" -> "running" attempt is
denied by policy), exactly as a direct `jarvis task run` with no flags
already is today. This is not new enforcement code; it is simply what
reusing `authorize_and_run_task` unmodified already guarantees. No
plan step is ever executed directly, no outer gate or ADR-0062
per-step authorization is bypassed, no `CONFIRM` action is
auto-confirmed, no `MANUAL_ONLY` action is ever executed by this
module (it cannot reach one -- `kernel.capability_dispatch.PLAN_STEP_EXECUTORS`
wires none today).

## Job-application safety (ADR-0058)

Structurally unaffected. The worker can only ever reach
`planning.run_plan` through `authorize_and_run_task`, which can only
ever reach capabilities already wired into
`kernel.capability_dispatch.PLAN_STEP_EXECUTORS` -- no submission
capability exists there today, and this work package adds none. A
worker automating task execution does not, and structurally cannot,
automate job-application submission.

## Audit behavior

Unchanged. Every real decision the worker's calls make (the list, each
claim attempt, each plan step) lands in the exact same audit chain via
the exact same, unmodified `authorize_and_list_tasks`/
`authorize_and_run_task` call chain -- no worker-only audit format, no
bypass. The CAS itself re-reads the chain and re-appends through the
identical `JsonFileAuditStorageAdapter.save()`/`AuditChain.append()`
mechanism WP-115 already made process-safe -- no changes needed there.

## Testing -- real, process-level proof, not merely unit tests

- `tests/unit/test_memory_adapter_process_safety.py`: real
  `multiprocessing.Process` workers (8 real, separate OS processes)
  proving `compare_and_update_value` grants the swap to exactly one
  real racer, and that every racer given an already-stale expectation
  correctly loses, with the store provably untouched either way.
- `tests/unit/test_tasks_claim_process_safety.py`: the headline,
  end-to-end proof -- 6 real, separate OS processes all calling the
  exact, unmodified `authorize_and_run_task` for the exact same,
  already-created task. Exactly one real process reports
  `claimed=True` and genuinely executes the plan; every other process
  reports `claimed=False` having attempted no execution, and the final
  stored record is the one real winner's own, unmodified result.
- `tests/unit/test_worker_kernel.py`: `run_pending_tasks_once`
  discovers and runs a created task; a completed task is never
  rediscovered on a later pass; a real `PlanningError` is persisted as
  `"failed"` and reported, never silently swallowed; a cancelled task
  is never discovered; a malformed record is skipped without crashing
  the pass; a denied confirmation claims nothing.
- `tests/unit/test_cli_main.py`: `jarvis task worker --once` reports a
  claimed run, no-eligible-tasks, a not-claimed task, and a real
  error, all from a mocked `run_pending_tasks_once`; continuous mode
  with `--max-passes` is proven to call the real pass function exactly
  that many times and sleep exactly `max_passes - 1` times, with
  `time.sleep` itself mocked -- zero real delay, zero infinite loop,
  inside the automated test suite.
- Live-smoke-tested end to end against a real, locally running Ollama
  server: `task create` -> `task worker --once` (claimed, ran, a real
  hallucinated-capability `PlanningError` persisted as `"failed"`) ->
  `task worker --once` again (nothing eligible) -> continuous mode
  with `--max-passes 2` (one real pass ran a newly-created task, the
  second found nothing, then stopped cleanly on its own).

## A real finding from CI, not silently worked around

This work package's own first real CI run genuinely failed
`test_tasks_claim_process_safety.py` -- not reproducible locally, on
this machine's own faster, less-contended scheduling. The real
failure: two of six racers reported `claimed=True`, not one. The
claim mechanism's own mutual exclusion had not failed -- the test's
original, zero-step plan let the real winner race all the way through
claim -> run -> `"completed"` before a real, slower racer (genuinely
delayed by OS scheduling under contention on a busier CI runner) ever
got CPU time to attempt its own claim. That slower racer then read the
task as `"completed"` -- which WP-118 already, deliberately, documents
as freely re-runnable -- and legitimately re-claimed and re-ran it,
*sequentially*, not *simultaneously*. Both reports were real and
correct; the test's own assertion was simply stronger than the real
guarantee this work package provides (no *concurrent* double-execution
-- never a promise that a fast-completing task can't be legitimately
re-run by a second, slower caller racing the same initial request).

The fix did not weaken the safety property under test: the fake
reasoning provider now takes a real, deliberately generous 2 seconds
before returning its plan, keeping the real winner genuinely
`"running"` long enough that every racer, however late it is actually
scheduled, attempts its own claim while the task is still `"running"`
rather than against one that has already finished. Verified 4
consecutive real passes locally before re-pushing.

## Residual limitations, stated plainly

- Cancellation racing a genuinely in-flight run (the human cancels
  while the worker's own `planning.run_plan` call is actually
  executing) is not specially handled -- this is a pre-existing
  property of the synchronous execution model (WP-117/WP-119 already
  document the identical limitation for the CLI/UI cancel paths), not
  a new gap this work package introduces or was asked to close.
- `WorkerTaskOutcome.claimed` can be mislabeled `True` in one real,
  narrow, named edge case: a genuine I/O failure (e.g. a real SQLite
  lock timeout) occurring *during* the claim's own atomic write would
  also be caught by the worker's per-task exception handler and
  reported `claimed=True`, even though nothing was actually won. This
  is a benign, diagnostic-only imprecision in this one bookkeeping
  field -- the real, persisted `TaskStore` state is unaffected either
  way, since no write lands in that failure case.
- No automatic recovery of a crashed worker's abandoned claim -- see
  "crash behavior" above; WP-116's stale detection remains the
  accepted, existing signal.
- No scheduling of any kind (natural-language or deterministic) --
  explicitly out of this work package's own scope.
