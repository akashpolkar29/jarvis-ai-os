# Scheduled task recovery interactions (WP-128, 2026-09-12)

## Status

Real, investigated. No code change beyond one new regression test --
every interaction this work package was asked to verify was already
correctly, generically handled by WP-122/WP-126/WP-127's own existing
design, not by any scheduling-specific special case.

## What was investigated

Whether a scheduled task (WP-122's own `scheduled_at` field) interacts
correctly with cancellation, failure, retry, stale recovery (WP-126),
worker restart, and repeated worker passes.

- **Cancellation**: already tested
  (`test_scheduled_at_survives_cancellation`) -- `scheduled_at`
  survives, since `authorize_and_cancel_task`'s new value is built via
  `**data` (WP-127's own hardened version), preserving every field it
  does not itself change.
- **Failure/retry**: already tested
  (`test_scheduled_at_survives_a_failed_run_and_a_subsequent_retry`)
  and already documented (`docs/OPEN_DECISIONS.md` item 31): retrying
  a scheduled-then-failed task delegates unmodified to
  `authorize_and_run_task`, which never consults `scheduled_at` at
  all -- it is preserved purely as historical information, and a
  retry runs immediately regardless of the original schedule. This is
  intentional, established WP-122 behavior, not something WP-128 was
  asked to change.
- **Stale recovery (WP-126)**: no existing test covered this specific
  combination. Investigated directly: `authorize_and_recover_task`'s
  new value is also built via `**data`, so `scheduled_at` survives
  recovery exactly the same way it survives cancellation -- confirmed
  by a new test, `test_scheduled_at_survives_recovery` (a scheduled
  task claimed by a worker that then crashes, recovered to `"failed"`,
  its own `scheduled_at` unchanged).
- **Worker restart**: `jarvis.kernel.worker.run_pending_tasks_once` is
  stateless -- it re-reads the real task store fresh on every pass, so
  a worker restart has no in-memory state to lose. Nothing to fix.
- **Repeated worker passes**: already proven by a real
  `multiprocessing.Process` test
  (`test_worker_scheduling_process_safety.py`) that racing
  `run_pending_tasks_once` itself across genuinely independent
  processes never lets two winners overlap. WP-127's own schedule
  hardening additionally closes a real, related hazard: scheduling a
  task can no longer silently revert a real, concurrent worker claim
  back to `"created"` (a genuine duplicate-execution risk WP-128's own
  investigation surfaced, closed one work package earlier since it was
  discovered while implementing WP-126, not deferred).

## What was deliberately not built

- No recurrence, no natural-language scheduling -- out of scope, as
  instructed.
- No new scheduling-specific recovery mechanism -- WP-126's own
  generic, status-based recovery already applies uniformly to any
  stale `"running"` task, scheduled or not; no special-casing was
  needed or added.

## Testing

One new regression test, `test_scheduled_at_survives_recovery`
(`tests/unit/test_tasks_kernel.py`), closing the one real, missing
combination this investigation found. All other scheduled-task
interaction properties were already covered by existing tests, cross-
referenced above rather than duplicated.
