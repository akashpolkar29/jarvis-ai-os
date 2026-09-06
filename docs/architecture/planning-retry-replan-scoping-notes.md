# Planning retry/replan scoping notes — investigated, not decided

**Status: research only. No decision made, nothing built.** No code
was written for this document — no port, no adapter, no application
module, no capability, no ADR. Mirrors `m7-scoping-notes.md`'s own
precedent exactly. Written 2026-09-07.

## The real, current behavior, quoted directly from the real code

`m7-task-planning-design.md`'s own "Real, open sub-questions" section
(sub-question 1) named this as genuinely unresolved when the design
was written, and it remains unbuilt today, confirmed directly against
the real, current implementation:

- `application/planning/planner.py::generate_plan()` calls
  `provider.generate(prompt, prior_attempts)` **exactly once**, with
  `prior_attempts: tuple[Attempt, ...] = ()` hardcoded empty every
  time — there is no loop, no retry, and nothing is ever fed back to
  the provider about a prior failure.
- `application/planning/executor.py::execute_plan()` stops at the
  **first** denied or (per `PlanValidationError`) invalid step and
  returns immediately (`PlanExecutionResult(aborted=True)`) — every
  step after that point is never attempted, matching
  `m7-task-planning-design.md`'s own stated "simplest, safest first
  version."

So today: any failure, anywhere in a plan, ends the whole
`planning.run_plan` invocation. There is no retry of the failed step
and no replanning around it — a caller gets a real, honest, partial
`PlanExecutionResult` naming exactly which step failed and why, and
that is the end of it.

## Defining the two real, distinct mechanisms this task's own prompt names

Worth separating explicitly, since they imply genuinely different
real designs, not two names for the same thing:

- **Retry**: re-attempt the *same* step, with the *same* arguments,
  again. Only meaningful for a step that failed for a transient or
  environment-shaped reason (a real exception from the wrapped
  `authorize_and_*` call — e.g. a momentarily-locked file, a flaky
  network call inside a future non-`ALLOW` capability) — retrying a
  step that was cleanly **denied** by the policy engine (lack of
  confirmation, wrong tier) achieves nothing: the same arguments under
  the same confirmation state produce the same `Decision` every time,
  by `evaluate()`'s own deterministic design. Retry only makes real
  sense paired with re-asking for confirmation (a human changing their
  answer) or waiting for a real environment condition to change —
  neither of which "retry the same step" alone captures.
- **Replan**: go back to the `ReasoningPort` provider with the failed
  step's own real context (mirroring `Dispatcher`'s own existing
  `prior_attempts` feedback loop, the real, already-established
  precedent for "tell the provider what didn't work and ask again")
  and ask for a **new**, possibly different plan — one that might
  avoid the failed step, substitute an alternative capability, or
  reorder remaining work. This is the more generally useful of the
  two for a *denied* step (the provider could propose a different
  approach entirely, rather than blindly repeating something already
  known to be denied).

## Sub-question 1 — does a retried/replanned step get a fresh authorization check regardless?

**Already answered, structurally, by ADR-0062 itself — not a new
question this document needs to resolve.** ADR-0062's own core
decision is that *every* step, with no exception named or implied for
retries, is authorized via its own, individual `authorize_by_id()`
call, evaluated fresh at the moment it runs. There is no mechanism
anywhere in `execute_plan()`/`AuthorizationOrchestrator` that could
skip or cache a decision across two calls even if a future retry/
replan mechanism wanted to — each call to a `PlanStepExecutor`
constructs its own fresh registry/storage/chain/orchestrator and calls
the real `authorize_and_*` function's own internal `authorize_by_id()`
independently (see `kernel/capability_dispatch.py`'s own module
docstring). **Any real retry/replan design automatically inherits
this guarantee for free, by construction** — it is not something the
retry/replan mechanism itself needs to implement or remember to
preserve.

## Sub-question 2 — is there a bound on retries?

**Real, existing precedent in this codebase to follow, not a novel
design problem**: `application/coding/loop.py`'s own
`DEFAULT_MAX_CLIMBS = 3` is the established shape for "a finite,
named ceiling on how many times this project retries something
expensive/risky before giving up and reporting failure honestly,"
already reviewed and accepted for `Dispatcher`'s own escalation
climbs. A retry/replan mechanism for `planning.run_plan` could use an
directly analogous `max_replans`/`max_retries` parameter, defaulting
to a small, fixed integer, threaded through
`authorize_and_run_plan`/`execute_plan` the same way `max_climbs`
already threads through `run_coding_task`. **Real, additional
questions a bound alone does not resolve**: does the bound apply
per-step (each step gets its own N retries) or per-plan (N total
replans across the whole plan, however distributed)? A per-plan bound
is simpler and caps total real cost (each replan is a new, real,
non-free call to a `ReasoningPort` provider) more predictably; a
per-step bound could let one persistently-failing step exhaust the
whole budget before any other step is even attempted. Neither is
obviously correct without knowing which failure mode (one flaky step,
or a systematically bad plan) is more common in practice — this
document does not have that data and does not guess at it.

## Sub-question 3 — does the audit chain need a new record type to distinguish "replanned" from "new plan"?

**A real, investigated finding, not assumed either way**: checked
directly against `domain/audit.py::AuditRecord`'s own real fields
(`sequence`, `decision`, `previous_hash`, `written_at`, `record_hash`
— see the 2026-09-07 addition of `written_at`) — there is **no field
anywhere that ties multiple records together as belonging to the same
higher-level operation**. This is not a gap specific to retry/replan:
it already exists today, for a single, un-retried plan run. Given a
real, current audit chain with five consecutive `Tier.ALLOW` records,
there is no way to tell from the chain alone whether those five
records are one `planning.run_plan` invocation's five steps, or five
completely unrelated direct capability calls that happened to run back
to back — `PlanStepRecord`/`PlanExecutionResult` (the *in-memory*
return value of one `execute_plan()` call) carry that grouping, but
nothing persists it to the audit chain itself.

**Real implication for retry/replan specifically**: if a future
replan mechanism runs a second `generate_plan()`/`execute_plan()`
cycle after the first one's failure, its own new steps' audit records
would be **structurally indistinguishable from a completely separate,
later `planning.run_plan` invocation** — same gap, just now also
hiding "this is attempt 2 of the same original goal" rather than only
hiding "this is part of a plan at all."

**Real options, not resolved here**: (a) add a new, optional
`plan_id`/`attempt_number` field to `AuditRecord`, mirroring exactly
how `written_at` was just added — an additive field, included in the
hash, with the same real "old chain files won't have it, no migration
path" consequence Task 1's own work already established as this
project's accepted precedent for this class of change; (b) leave the
audit chain as a flat, ungrouped sequence permanently, and build any
"which records belong to this plan" reconstruction as an
external/application-level concern (e.g., `PlanExecutionResult` itself
already IS that grouping, in memory, for the caller that just ran the
plan — the gap is only real for someone reconstructing history *after
the fact*, from the chain alone); (c) do nothing until retry/replan is
actually built, since the gap costs nothing while only one
non-repeating plan attempt ever happens per invocation, exactly
today's real behavior.

## Summary

Retry/replan is genuinely unbuilt, confirmed directly against the real
code, matching `m7-task-planning-design.md`'s own original, honest
disclosure. Sub-question 1 (fresh authorization) is not actually open
— ADR-0062's own existing guarantee already covers it unconditionally.
Sub-questions 2 (a bound) and 3 (audit traceability) have real,
concrete options laid out above, mirroring already-accepted precedent
elsewhere in this codebase (`DEFAULT_MAX_CLIMBS`, the `written_at`
field's own additive-and-hashed shape) rather than inventing new
patterns. No recommendation is made; this is options-on-the-table work
for the user's own decision.
