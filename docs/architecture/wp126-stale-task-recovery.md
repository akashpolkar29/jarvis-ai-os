# Stale running task recovery (WP-126, 2026-09-12)

## Status

Real, implemented. No ADR -- no new `CapabilityId`/`Effect`/`Tier`, no
new task status. Reuses `memory.update`'s already-Accepted
classification (ADR-0063) and WP-120's already-hardened compare-and-
swap primitive unmodified.

## The real gap this closes

Before this work package, a task whose owning process genuinely
crashed (SIGKILL, OOM, machine shutdown) while `"running"` had exactly
one available human action: `jarvis task cancel` -- which is terminal
by design (WP-117/WP-118: a cancelled task can never be retried or
re-run). `jarvis task retry` only accepts `"failed"` (WP-121), and
`authorize_and_run_task`'s own atomic claim structurally refuses any
`"running"` -> `"running"` transition (WP-120's own decisive CI
finding, closing a real re-claim bug). So nothing could ever move a
genuinely abandoned task back to a retryable state -- the only path
forward was creating a brand-new task with the same goal.

## What was built

`authorize_and_recover_task` (`jarvis task recover <task_id>`,
`kernel/tasks.py`) -- the narrowest possible transition:
`"running"` (and stale) -> `"failed"`, after which `jarvis task retry`
already works, completely unmodified.

**The deterministic staleness gate, reused, not reinvented**: refuses
outright unless `TaskGetOutcome.stale` is already `True` for this
exact task -- the identical `_is_stale_running` predicate WP-116
already computes from `updated_at` against a real `ClockPort.now()`,
with the identical `STALE_RUNNING_THRESHOLD_SECONDS` (1800s) threshold.
A task that is merely old but still genuinely progressing (its own
`updated_at` keeps advancing) is never eligible, no matter how many
times this is called.

**Why this calls the real CAS primitive directly, not
`update_task_status(..., atomic=True)`**: this function's own initial
staleness check is necessarily based on a snapshot that can go stale
itself between the read and the write (the owning process might
genuinely still be alive and about to finish legitimately).
`update_task_status`'s own `atomic=True` path already refuses a
`"running"` -> `"running"` write, but that check only protects the
*claim* transition -- it does nothing to stop a `"running"` ->
`"failed"` write started against a now-stale snapshot from silently
overwriting a *different*, genuinely-concluded real value (e.g. the
owner legitimately finished with `"completed"` moments before this
call's own write). Calling
`jarvis.kernel.memory.authorize_and_compare_and_update` directly, with
the *exact* dict this function itself just read as `expected_value`,
closes that gap precisely: the underlying `compare_and_update_value`
only ever applies if the record on disk, at the moment of the write,
is still byte-for-byte identical to what was read -- any real,
concurrent change (the owner finishing, another recovery attempt, a
cancellation) makes the comparison fail cleanly, reporting
`recovered=False`, never silently clobbering real data. This is the
exact same, already-audited primitive WP-120 built for the "created"
-> "running" claim -- reused unmodified for a second, narrow purpose,
not a new locking mechanism. `update_task_status`'s own shared,
heavily-tested atomic branch (including the "running" -> "running"
claim-refusal check) is completely untouched by this work package.

**Attempts history is preserved, not reset**: the new value keeps
every existing field (`created_at`, `scheduled_at`, prior `attempts`)
untouched except `status`/`reason`/`updated_at`, and appends one new
attempt entry for the concluded "running" span, mirroring
`update_task_status`'s own identical attempts-append shape exactly --
a recovered task's own history shows a real, dated `"failed"`
attempt, not a silent gap. A real `TaskStatusChanged` event is
published on success, mirroring every other real status transition.

## What was deliberately not built

- No automatic recovery anywhere (worker or otherwise) -- this is a
  manual, explicitly human-triggered CLI action only, matching WP-116's
  own "detection only, never automatic recovery" precedent exactly.
- No UI button, no voice grammar -- matches `task cancel`/`task
  retry`'s own existing scope boundaries.
- No new task status -- "recovered" is not a status; the task simply
  becomes `"failed"`, indistinguishable in shape from any other real
  failure, and its own `attempts` history is the only record of what
  happened.

## Testing

`test_tasks_kernel.py`: the headline transition (stale running ->
failed, attempts preserved); refusal for a non-`"running"` task;
refusal for a `"running"`-but-not-yet-stale task (the deterministic
safety gate); refusal for an unknown task id; the real safety
property that a task which legitimately completed first is never
clobbered (via `update_task_status`'s own real blind write, the exact
mechanism `authorize_and_run_task` itself uses at its natural
conclusion); a full recover-then-retry round trip proving the retry
path is genuinely re-opened; denial without confirmation.

`test_task_recovery_process_safety.py` (new): a real
`multiprocessing.Process` test, `_WORKER_COUNT` genuinely independent
OS processes racing `authorize_and_recover_task` against the same,
already-stale task -- exactly one ever reports `recovered=True` (a
stronger, simpler assertion than the run/retry claim race's own "no
overlapping wall-clock windows," since a recovered task can never be
legitimately re-recovered the way a completed task can be legitimately
re-run). Re-run 5+ times, including under `taskset -c 0,1` contention,
with zero flakiness.

`test_cli_main.py`: `jarvis task recover` prints `recovered:
true`/`false` correctly, surfaces the real refusal reason, and
requires a task id.
