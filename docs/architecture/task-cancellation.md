# Real task cancellation (WP-117, 2026-09-11)

## Status

Real, implemented. No ADR -- reuses `memory.update`'s own already-
classified `Effect.WRITE_LOCAL`/`Tier.CONFIRM` (ADR-0063) for the
actual "cancelled" transition, and `memory.get`'s own already-
classified `Effect.READ_LOCAL`/`Tier.ALLOW` for the lookup. No new
`CapabilityId`, `Effect`, or `Tier` was introduced.

## The real gap this closes

`VALID_TASK_STATUSES` (WP-107) has always included `"cancelled"`, with
the module's own docstring naming it honestly as reserved for "a
future cancel verb this module does not yet implement." Two real
situations made this gap concrete rather than hypothetical:

1. A task sitting at `"created"` that a human decides not to run.
   Before this work package, the only way to stop it being listed as
   active was to leave it there forever.
2. A task WP-116 (2026-09-11, the immediately preceding work package)
   reports `stale` -- `"running"` with no `updated_at` progress in over
   30 minutes, almost always because the process that was running it
   has died. WP-116 was deliberately detection-only; it gave a human
   the *signal* but no way to *act* on it. This work package is that
   action.

This was also one of the overnight session's own explicitly named
Priority 2 candidates ("task cancellation semantics").

## The real, narrow semantic -- stated precisely

**Cancelling a `"running"` task does not interrupt any real, in-flight
execution.** There is no in-flight execution to interrupt in this
architecture: `authorize_and_run_task` runs `planning.run_plan`
synchronously to completion inside one call, and `jarvis ui`'s own
HTTP server is deliberately single-threaded (WP-108), so no second
request is even handled concurrently with a run already in progress.
Cancellation is a human retiring a task's own *stored status* by hand
-- nothing more, nothing less. The two real cases it serves are exactly
the two named above: a `"created"` task nobody wants run, and a
`"running"` task whose owning process has already died and will never
touch it again on its own.

## The mechanism

`authorize_and_cancel_task(task_id, ...)` in `kernel/tasks.py`:

1. Calls `authorize_and_get_task(task_id, ...)` (the existing, exact,
   by-id lookup, `Tier.ALLOW`) to read the current record.
2. If no record exists: returns `cancelled=False`, reason "No task
   found for this identifier." -- the lookup's own `Decision` is
   returned; nothing further was attempted.
3. If the record's current `status` is not in
   `_CANCELLABLE_STATUSES = frozenset({"created", "running"})`:
   returns `cancelled=False`, reason naming the real current status
   (e.g. `"Task is already 'completed' and cannot be cancelled."`) --
   again, nothing further was attempted, and the lookup's own granted
   `Decision` is returned since that is the most directly gating real
   decision in this path.
4. Otherwise, calls `update_task_status(task_id, goal, "cancelled",
   None, ...)` -- the identical, unmodified function every other
   real status transition already uses, which itself does a real
   read-modify-write (preserving `created_at` and `goal`) and publishes
   a real `TaskStatusChanged` event (WP-111) if granted.

No new storage primitive, no new event type, no schema change.

## CLI

`jarvis task cancel <task_id>` -- a new nested subcommand alongside
`create`/`run`/`status`/`list`. Prints `cancelled: true` or
`cancelled: false` plus a `reason:` line when refused. Requires the
usual `--physical-confirmation-available`/`--remote-confirmation-available`
flags to actually grant the underlying `Tier.CONFIRM` transition, same
as every other task-mutating subcommand.

## Testing

`tests/unit/test_tasks_kernel.py`: a cancellable `"created"` task
transitions correctly and preserves `created_at`/`goal`; a stale
`"running"` task (WP-116's own scenario) cancels correctly and is no
longer reported stale afterward (since it is no longer `"running"` at
all); an unknown task id is refused with the correct reason and a
granted lookup `Decision`; an already-`"completed"` task is refused
and the underlying record is provably untouched; cancelling twice
refuses the second attempt; a denied confirmation leaves the task
unchanged and reports the refusal; a granted cancellation publishes
exactly one real `TaskStatusChanged` event with the correct
`previous_status`/`new_status`; a refused cancellation (terminal
status) publishes none.

`tests/unit/test_cli_main.py`: `jarvis task cancel` prints
`cancelled: true` for a granted cancellation and `cancelled: false`
plus the real reason for a refused one; `task cancel` with no
`task_id` exits via argparse's own `SystemExit`.

## Residual limitations, stated plainly

- Cancellation never interrupts a real, in-flight plan execution --
  see "the real, narrow semantic" above. There is nothing in this
  architecture today for it to interrupt.
- No voice grammar was added. `task cancel` joins `task create`/`run`/
  `status`/`list` in having none.
- `"waiting_approval"` remains the one state in `VALID_TASK_STATUSES`
  with no real code path producing it yet -- unrelated to this work
  package, unchanged.
