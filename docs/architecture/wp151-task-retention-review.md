# Task cleanup/retention review (WP-151, 2026-09-12)

## Status

Investigated, **skipped** -- no code change. This is a real, genuine
data-retention-policy question, not a bug with one obviously-correct
fix; per this session's own standing instruction ("do not guess at a
genuine threat-model/architecture decision"), it is documented and
flagged rather than silently resolved.

## What was investigated

Whether any task-specific cleanup/retention mechanism exists for
`"completed"`/`"failed"`/`"cancelled"` task records, and what happens
to a task record over a long time horizon.

**Real finding, confirmed by direct inspection, not assumed**: task
records have no retention mechanism of their own. `write_task_record`
(`kernel/tasks.py`) writes every task through the completely
unmodified `authorize_and_remember` (`kernel/memory.py`), which in
turn calls the real `SqliteMemoryAdapter.write()` -- every task record
therefore silently receives the identical `DEFAULT_RETENTION = 90
days` (`application/memory/retention.py`) every other, ordinary
memory record gets, with no distinction for its `"kind": "task"`
marker. `authorize_and_remember` also calls `adapter.sweep_expired()`
on **every single granted write anywhere in the system** (ADR-0051) --
a real, unconditional `DELETE FROM memory_records WHERE expires_at IS
NOT NULL AND expires_at <= ?` -- so a task record older than 90 days
is permanently, irrecoverably deleted the next time *any* memory write
happens to run the sweep, not just a task-specific one. `job_application.record`
(the applied-jobs ledger) reuses the exact same mechanism and carries
the identical exposure.

**Two real, concrete consequences, neither hypothetical**:

1. A `"completed"`/`"failed"`/`"cancelled"` task's own execution
   history (`"attempts"`, WP-121) is not specially preserved -- it
   ages out with the rest of the record after 90 days, with no
   archival step.
2. A task record could in principle expire while still logically
   `"running"` (e.g. an abandoned task whose owning process crashed
   more than 90 days ago and was never recovered via WP-116/WP-126) --
   an edge case, not a realistic operational scenario at this
   project's current scale, but a real gap in the model: nothing
   prevents it structurally.

## Why this was not simply fixed

Two candidate "smallest fixes" were considered and both rejected as
silent architecture decisions, not safe defaults:

- **Auto-pin every task record** (`authorize_and_pin`, already a real,
  classified `Effect.WRITE_LOCAL`/`Tier.CONFIRM` capability) after
  every `write_task_record` call. Rejected: this silently commits
  every task, forever, to never expiring -- a real, permanent
  retention-policy change with genuine storage-growth and
  right-to-be-forgotten implications, not something to decide on this
  pass's own authority. It would also double the audit-chain writes
  for every single task creation.
- **Give tasks their own, longer or infinite default retention**
  (e.g. a `TASK_RETENTION` distinct from `DEFAULT_RETENTION`).
  Rejected for the identical reason -- retention duration is a real,
  user-facing data-lifecycle policy, not an implementation detail.

Both would be real, silent, unreviewed policy decisions layered onto
an already-Accepted retention design (ADR-0050/ADR-0051), exactly the
class of decision this session's own hard boundaries name as requiring
the user's explicit, separate sign-off rather than an autonomous
pass's own judgment call.

## What was deliberately not built

- No auto-pinning, no task-specific retention duration, no archival
  mechanism, no change to `write_task_record`/`update_task_status`/
  `authorize_and_remember`/`SqliteMemoryAdapter`.

## Recorded as a real, open decision

See `docs/OPEN_DECISIONS.md` item 52. The real question for the user:
should task records (and/or the job-application ledger) be pinned, or
given their own longer retention, or is the shared 90-day default
memory retention the intended, accepted behavior for them too?
