# `task run` refuses to resume an already-cancelled task (WP-118, 2026-09-11)

## Status

Real, implemented. No ADR -- a pure correctness fix closing a real gap
the immediately preceding work package (WP-117) itself opened. No new
`CapabilityId`/`Effect`/`Tier`.

## The real gap

Before WP-117, no real task could ever reach `"cancelled"` --
`authorize_and_run_task` transitioned a task to `"running"`
unconditionally, with no check of its current stored status, and that
was harmless: there was no status it could silently override that
mattered. The moment WP-117 made `"cancelled"` real and reachable,
that same unconditional behavior became a genuine correctness bug:

```
jarvis task create "some goal"        # -> created
jarvis task cancel <id>               # -> cancelled
jarvis task run <id> "some goal"      # silently resumes it anyway!
```

Nothing in the run path consulted the task's own current status, so a
human's explicit decision to cancel a task could be completely undone
by a direct `run` call, with no indication anything unusual had
happened -- the task would simply run and, most likely, transition to
`"completed"` or `"failed"` as if it had never been cancelled at all.
This directly undermines the entire point of WP-117.

## The fix

`authorize_and_run_task` now looks up the task's current record first
(`authorize_and_get_task`, the identical, unmodified `memory.get`
lookup `authorize_and_cancel_task` already uses). If the stored status
is `"cancelled"`, the function returns immediately:

```python
TaskRunOutcome(
    decision=get_outcome.decision,  # the lookup's own Decision, Tier.ALLOW, always granted
    status="cancelled",
    reason="Task was cancelled; run refuses to resume a cancelled task.",
)
```

No "running" transition is attempted, no plan is executed, no
`TaskStatusChanged` event is published -- nothing about the task's own
stored state changes. `TaskRunOutcome`'s docstring was updated to name
this as a third real case for both `decision` and `status`.

## Deliberately narrow scope

Only `"cancelled"` is checked. A `"completed"`/`"failed"` task remains
freely re-runnable via `jarvis task run` -- that is legitimate retry
behavior (effectively this codebase's existing, if implicit, "safe
retry" mechanism for a failed task), not a gap, and changing it was
out of this work package's own scope. The asymmetry is deliberate:
`"cancelled"` is the one status a human explicitly, deliberately
chose, as opposed to one the system arrived at on its own.

## Testing

`tests/unit/test_tasks_kernel.py`: a cancelled task's `run` call
returns `status="cancelled"` with the correct reason and a granted
lookup `Decision`, and the stored record is provably untouched; no
`TaskStatusChanged` event is published for a refused run; a task that
was never cancelled still runs normally to `"completed"` exactly as
before this change (proving the new lookup adds no regression to the
ordinary path).

No CLI change was needed -- `cli/main.py`'s existing `task run`
dispatch already passes `TaskRunOutcome.status`/`.reason` through
generically to the same print path `"failed"` already uses, so
`jarvis task run <cancelled-id> <goal>` already prints
`status: cancelled` / `reason: ...` correctly with zero code changes
there.

## Residual limitations, stated plainly

- `"completed"`/`"failed"` tasks remain re-runnable by design, not
  oversight -- see "deliberately narrow scope" above.
- This adds one extra real `memory.get` lookup to every `run` call
  (negligible cost, `Tier.ALLOW`, no extra confirmation prompt).
