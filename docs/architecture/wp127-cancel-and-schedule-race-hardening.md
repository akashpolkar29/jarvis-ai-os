# Cancel/schedule race hardening (WP-127, 2026-09-12)

## Status

Real, implemented. No ADR -- no new `CapabilityId`/`Effect`/`Tier`, no
new task status, no new claim mechanism. Widens WP-120's already-
hardened `authorize_and_compare_and_update` primitive to two more
call sites; `update_task_status`'s own shared atomic branch (the
"running" -> "running" claim-refusal check) is completely untouched.

## The real gap found while investigating worker/task lifecycle hardening

`authorize_and_cancel_task` and `authorize_and_schedule_task` both
read a task's current record, then wrote a *new* record built from
that same read -- via a **blind overwrite**, not a compare-and-swap.
Two concrete, real hazards followed directly from this:

- **Cancel**: if a task's real, still-alive owner legitimately
  completed it between cancel's own read and its write, cancel's
  blind write would silently revert the real `"completed"`/`"failed"`
  outcome back to `"cancelled"` -- discarding real, concluded work.
- **Schedule**: `authorize_and_schedule_task`'s new record preserves
  whatever `status` it read -- if a real worker legitimately claimed
  the exact same task (`"created"` -> `"running"`, WP-120's own
  claim) between schedule's read and its write, scheduling's blind
  write would silently revert that real claim back to `"created"`,
  making the task claimable *again* by a second worker. This is a
  genuine duplicate-execution hazard, not merely a lost update.

Neither race is new -- both existed since WP-117/WP-122 respectively.
WP-120's own report explicitly named the general class ("cancellation
racing a genuinely in-flight run") as a known, deliberately deferred,
"pre-existing, accepted, unrelated edge case," not something that work
package was asked to close. WP-126 (stale task recovery) needed the
identical direct-CAS pattern for its own new transition, which is what
surfaced this: cancel and schedule had never been widened the same way
run's own claim already was.

## What was built

Both `authorize_and_cancel_task` and `authorize_and_schedule_task` now
call `jarvis.kernel.memory.authorize_and_compare_and_update` directly
-- the exact same, already-hardened primitive WP-120 built for the
"created" -> "running" claim and WP-126 already reused for recovery --
with the *exact* dict each function itself just read as
`expected_value`. If the record on disk has changed by the time the
write is attempted (a real, concurrent completion, claim, or another
cancel/schedule/recover), the comparison fails cleanly and the call
reports its own real refusal (`"Task changed state before ... could
be applied; not ..."`), never silently overwriting real data.

- **Cancel** additionally replicates `update_task_status`'s own
  attempts-append shape (an entry is appended only when concluding a
  genuinely `"running"` span, mirroring the exact same conditional),
  and publishes a real `TaskStatusChanged` event on success, matching
  its own prior behavior exactly.
- **Schedule** needed no attempts/event changes -- it never changes
  `status` or publishes an event, before or after this fix.

`update_task_status` itself was **not modified** -- its own atomic
path (used only by `authorize_and_run_task`'s claim) does its own
fresh internal read before the CAS, which does *not* by itself
protect against this class of race (see "why not reuse
`update_task_status`" below); reusing it here would have required
either widening its own hardened logic (risking regression to the
most safety-critical code in this module) or adding a new parameter
whose semantics don't cleanly generalize across both use cases. Direct
use of the raw CAS primitive was the narrower, lower-risk choice.

### Why not reuse `update_task_status(..., atomic=True)`

`update_task_status`'s atomic path re-reads the task fresh internally,
then CASes against *that* fresh read -- which only protects against a
write landing *during* `update_task_status`'s own call, not against
the *caller*'s own earlier semantic check (e.g. "is this task still
cancellable?") having gone stale before `update_task_status` was even
invoked. Building the new record from a fresh internal read means it
would happily accept whatever status it finds and write over it
(except the one hardcoded `"running"` -> `"running"` special case) --
exactly the blind-write hazard this work package closes. Calling the
raw CAS primitive directly, with the caller's *own* already-validated
snapshot as `expected_value`, closes the gap correctly: the write only
lands if nothing changed since the caller's own semantic check.

## What was deliberately not built

- No generalized "required previous status" parameter added to
  `update_task_status` -- investigated and rejected as unnecessary
  complexity added to the most heavily-tested, safety-critical shared
  function in this module, for no real benefit over the narrower,
  already-proven direct-CAS pattern.
- No fix to `authorize_and_retry_task` -- it delegates entirely to
  `authorize_and_run_task`'s own already-CAS-protected claim; it never
  performs its own blind write.
- No genuine multiprocessing reproduction of these two specific races
  -- unlike the run/retry claim (which has an artificially delayed
  plan-generation step to widen the race window), cancel and schedule
  have no slow step to delay, making a genuine OS-level race
  vanishingly unlikely to trigger by chance in a short test run.
  Instead, each race is reproduced deterministically, in one process,
  by making the composition function's own internal
  `authorize_and_get_task` lookup return a snapshot captured *before*
  a real, concurrent change that has already landed on disk by the
  time the write is attempted -- the exact real ordering a genuine
  race would produce, proven directly rather than left to timing luck.

## Testing

`test_tasks_kernel.py`: two new regression tests
(`test_cancel_never_clobbers_a_task_that_legitimately_completed_first`,
`test_schedule_never_reverts_a_task_a_worker_legitimately_claimed_first`)
using the monkeypatch-based deterministic race simulation described
above; both prove the real, concluded state survives and the
would-be clobbering call is cleanly refused. All 78 existing
cancel/schedule tests pass unmodified, proving this is a pure
hardening with no behavioral change to any already-correct path.
