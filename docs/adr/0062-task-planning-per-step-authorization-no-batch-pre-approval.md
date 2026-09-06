# ADR-0062: Task-planning per-step authorization -- no batch pre-approval

## Status

Proposed -- written as part of a real design proposal
(`docs/architecture/m7-task-planning-design.md`, 7 real decisions
prompt, Decision 7, 2026-09-05), not yet reviewed by the user, not
self-accepted. Flagged here for the user's own later review of this
document's full text, mirroring every other safety-relevant ADR in
this project's history (ADR-0055/ADR-0056/ADR-0059/ADR-0060/ADR-0061,
among others).

## Date

2026-09-05

## Source

`docs/architecture/m7-task-planning-design.md`'s own design work,
itself building on `docs/architecture/m7-scoping-notes.md`'s real
finding that no multi-step, cross-capability task-planning mechanism
exists in this codebase today. No prior ADR addresses task planning
at all -- this is new scope, not a revision of an existing decision.

## Context

A real, minimal task-planning mechanism (design proposed in
`m7-task-planning-design.md`) would let a `ReasoningPort` provider
propose an ordered sequence of steps, each naming an already-existing
`CapabilityId` and its arguments, to be executed toward a single,
higher-level goal. This introduces a genuinely new shape of risk this
project's existing capabilities do not have: a **single point of
approval covering multiple, potentially heterogeneous-tier actions**.
Every existing capability in this codebase is authorized exactly once,
individually, at the moment it runs (`AuthorizationOrchestrator.authorize`/
`authorize_by_id`, the one real choke point `CLAUDE.md`'s own
Architecture summary already names). A planner that executed an entire
multi-step plan after a single upfront confirmation would be a real,
structural exception to that pattern -- and a dangerous one: a user
approving "do the thing" once, in the abstract, is not the same real
signal as a user approving each specific, concrete action a plan
happens to decompose that goal into, especially when a plan's own step
list is itself model-generated content (`UNTRUSTED_EXTERNAL`-worthy,
per ADR-0025's "model opinion carries zero weight" precedent) and
therefore not fully trusted before execution.

## Decision

**A plan is never authorized as a whole. Every step is authorized
individually, exactly when that step is about to run, via the same,
unmodified `AuthorizationOrchestrator.authorize_by_id()` every other
capability invocation already uses -- no new authorization path, no
batch/bulk `PolicyContext`, no "the plan was already approved"
exception anywhere in the authorization flow.**

Concretely: if a plan's own step N is classified `Tier.MANUAL_ONLY`,
step N is denied unless `PolicyContext.physical_confirmation_available`
is `True` **at the moment step N itself runs** -- evaluated fresh, by
whatever real confirmation mechanism is wired in then, with no
consideration given to whether the user confirmed the plan's own
existence, or an earlier step, or the goal in the abstract. A
`Tier.CONFIRM` step similarly requires its own real confirmation
signal at that step's own moment of execution, not inherited from an
earlier point in the plan's own lifecycle. This holds regardless of
how many steps preceded it, how much time elapsed, or whether every
prior step in the same plan already succeeded.

**A minimal first version of any real capability built from this
design should additionally restrict itself to only `Tier.ALLOW`/
`Tier.CONFIRM` steps** -- deferring the question of whether
`MANUAL_ONLY` steps inside a plan need any additional structural
safeguard beyond "authorized individually, same as always" to a
later, separately-considered version, once the simpler case has real
operating experience behind it. This ADR's own core decision (no
batch pre-approval, ever) already covers the `MANUAL_ONLY` case
correctly on its own terms; the additional first-version restriction is
a matter of rollout caution, not a gap in this decision's own
correctness.

## Consequences

**Makes easier**: no new authorization mechanism, no new `Effect`
member, no change to `domain/policy.py`'s own evaluation logic --
task planning becomes "a new caller of the same, existing choke
point, called more than once per outer invocation," not a parallel or
alternate authorization system. Every plan step still produces its
own real, individually hash-chained audit record, so a plan's own
full execution history is fully reconstructable from the existing
audit chain with no new logging mechanism.

**Makes harder / accepted cost**: a plan involving several
`Tier.CONFIRM`/`Tier.MANUAL_ONLY` steps could require the user to
confirm multiple times in quick succession to let one logical goal
complete -- a real, deliberate friction, not an oversight. This project
has already accepted an analogous cost elsewhere (each of M6a's own
`send_email`/`create_event` requires its own separate `MANUAL_ONLY`
confirmation, ADR-0059, with no "approve all my pending sends at
once" shortcut) -- this ADR extends that same, already-accepted
posture to planning rather than inventing a new one.

**Forecloses**: any future planner design that batches, caches, or
otherwise reuses one confirmation signal across more than one real
capability invocation, without a new ADR explicitly superseding this
one first -- mirroring ADR-0058's own "no submission capability
without a new ADR explicitly superseding it first" structural-boundary
pattern for M6b's job-assistance scope.

**Follow-up work this implies, not resolved here**: whether a plan is
ever shown to the user in full before its first step runs (a real,
additional transparency measure, distinct from and layered on top of
this ADR's own per-step authorization requirement) is a real, open
design question -- see `m7-task-planning-design.md`'s own "Real, open
sub-questions" section. This ADR's own scope is narrower and more
load-bearing: regardless of whether a plan is ever previewed, no step
within it is ever authorized in bulk.
