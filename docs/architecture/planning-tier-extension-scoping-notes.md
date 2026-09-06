# Planning tier-extension scoping notes — extending past `Tier.ALLOW`, investigated, not decided

**Status: research only. No decision made, nothing built.** No code
was written for this document — no port, no adapter, no application
module, no capability, no ADR. Mirrors `m7-scoping-notes.md`'s own
precedent exactly: a real investigation of a genuine, previously-named
implementation gap, options laid out for the user's own decision.
Written 2026-09-07.

## The real, current gap, quoted directly from the real code

`application/planning/executor.py`'s own module docstring states the
finding plainly: ADR-0062 itself permits `Tier.ALLOW`/`Tier.CONFIRM`
plan steps in a first version, but the real implementation restricts
further, to `Tier.ALLOW` only, because:

> every existing `authorize_and_*` function hardcodes its own
> arguments' `Provenance` internally (e.g. `authorize_and_read_file`
> always wraps its path as `Tainted(..., Provenance.user())`) — there
> is no seam for a caller to inject a different, more cautious
> `Provenance` reflecting that a plan step's arguments actually came
> from a model-generated plan.

Checked directly against the real code, not assumed: every one of the
four capabilities currently wired into
`kernel/capability_dispatch.py::PLAN_STEP_EXECUTORS`
(`fs.read_file`, `fs.list_dir`, `git.status`, `memory.retrieve`) — and,
by inspection, every other `authorize_and_*` composition function in
this codebase — constructs its own `Tainted(value, Provenance.user())`
(or `Provenance.system()`) inline, with no parameter exposing that
choice to the caller. For `Tier.ALLOW` capabilities this has no real
behavioral consequence today (`domain/policy.py::evaluate()` hardcodes
`granted=True` for `Tier.ALLOW` regardless of classification). Adding
a `Tier.CONFIRM` capability to the dispatch registry without first
closing this gap would mean a model-generated argument value
(`Trust.UNTRUSTED_EXTERNAL`-worthy, per `m7-task-planning-design.md`'s
own sub-question 3) gets silently treated as `Trust.USER_DIRECT` —
under-classifying real, adversary-influenced content, the exact class
of mistake `ADR-0025`'s "model opinion carries zero weight" precedent
already exists to prevent elsewhere in this codebase.

## Option 1 — a new, optional keyword argument threaded through each `authorize_and_*` function

**Shape**: each composition function gains e.g. `provenance:
Provenance | None = None`, defaulting to today's exact hardcoded value
when omitted (`None` → `Provenance.user()`, unchanged for every
existing caller), and using the caller-supplied value when given.
`kernel/capability_dispatch.py`'s own adapter functions would then pass
a real, correct `Provenance` (`Trust.UNTRUSTED_EXTERNAL`, some
`Classification`) reflecting that the value came from a plan step, not
directly from the user.

**Real scope, not hand-waved**: this does *not* mean touching all ~40
statically-registered capabilities' composition functions at once.
`capability_dispatch.py`'s own module docstring already states
"extending coverage to more capabilities is real, incremental future
work, adding one small adapter function per capability" — the same
incremental shape applies here: only a capability actually being added
to `PLAN_STEP_EXECUTORS` (or promoted from `Tier.ALLOW` to needing
`Tier.CONFIRM` treatment) needs its own composition function's
signature touched, matching Task 1's own real, recent precedent
(`ClockPort` was threaded through every kernel composition function
that constructs an `AuthorizationOrchestrator`, one function at a
time, mechanically, verified by mypy — see
`docs/OPEN_DECISIONS.md`'s own item on the audit-record timestamp for
that exact shape of change). Concretely, for the four capabilities
already in `PLAN_STEP_EXECUTORS` today, this means four real function
signature changes (`authorize_and_read_file`, `authorize_and_list_dir`,
`authorize_and_get_git_status`, `authorize_and_recall`) plus their own
existing test suites' own coverage extended with a
"caller-supplied provenance is actually used" case each.

**Real risk named, not glossed over**: a new optional parameter
defaulting to today's behavior is safe by construction for every
*existing* caller (CLI, voice, any other composition-function caller)
— but a *future* caller adding a *new* plan-step adapter could still
forget to pass the more-cautious `Provenance`, silently reproducing
today's exact gap for that one new capability. This is a real,
per-addition discipline risk, not eliminated by the seam existing —
only made possible to close, not automatically closed. A real,
mechanical safeguard mirroring this codebase's own established style
(see `tests/meta/test_job_search_no_content_reading.py`,
`tests/meta/test_job_assistance_no_submission.py`) could enforce "every
function registered in `PLAN_STEP_EXECUTORS` must pass a non-default
`provenance` argument to its wrapped `authorize_and_*` call" via an AST
scan of `capability_dispatch.py` specifically — not attempted here,
real future work if Option 1 is chosen.

## Option 2 — a wrapper/parallel layer, not touching existing functions

**Shape investigated, and found not to actually work as a clean
alternative**: could `kernel/capability_dispatch.py`'s own adapter
functions re-authorize with a corrected `Provenance` *before* calling
the existing `authorize_and_*` function, leaving that function itself
untouched? No — each `authorize_and_*` function already performs its
*own* internal `authorize_by_id()` call using its own internal,
hardcoded `Provenance`; a wrapper calling `authorize_by_id()` a second
time first would produce a *second*, separate audit record for the
same logical step (violating this codebase's own "one capability
invocation, one audit record" shape used everywhere else), and would
not change what `Provenance` the wrapped function's own internal call
actually uses regardless.

**The only version of "a wrapper layer" that is actually distinct from
Option 1**: build new, parallel, plan-aware composition functions
(e.g. `authorize_and_read_file_for_plan_step`) that accept an explicit
`Provenance` and do their own real "authorize, then act" call, never
touching the original `authorize_and_read_file`. This avoids any
signature change to existing, already-tested functions — a real
benefit if minimizing churn to existing call sites matters more than
avoiding duplication. **Real cost, named plainly**: this doubles the
maintenance surface for every capability that gets a plan-step
variant — two functions per capability that must be kept in sync
(same real action, same real error handling) as either evolves, a
real, ongoing drift risk Option 1 does not have (Option 1 has exactly
one function per capability, always).

## Option 3 — leave it as a deliberate, permanent v1 boundary

**Always a valid choice, named directly**: `Tier.ALLOW`-only is not a
broken state — it is a real, working, currently-shipped v1 boundary
that already lets four real capabilities run inside a plan safely.
Every capability actually needed for a plan so far is `Tier.ALLOW`.
Extending past it is speculative work for a need not yet demonstrated;
doing nothing costs nothing today and forecloses no future option
(Options 1/2 remain available whenever a real `Tier.CONFIRM` (or
higher) plan-step need actually arises).

## Should `Tier.MANUAL_ONLY` steps ever be plannable at all, even with a seam?

A real, additional finding surfaced by this investigation, not just
the taint-classification gap named above. Checked directly against
`application/planning/executor.py::execute_plan()`'s own real code: it
takes `physical_confirmation_available`/`remote_confirmation_available`
as **flat, fixed booleans supplied once, at the top of the whole
plan's execution**, and passes that *exact same pair of values*,
unchanged, into every single step's own `authorize_and_*` call, in
order. For `Tier.ALLOW` steps this is irrelevant (confirmation is
never consulted). For a hypothetical future `Tier.CONFIRM` step this
is already the intended, correct design — ADR-0062's own text
requires each step be "authorized individually... evaluated fresh...
with no consideration given to whether the user confirmed... an
earlier step" — and a flat, unchanging confirmation *input* does not
violate that: the authorization *decision* is still computed fresh,
per step, by that step's own real `evaluate()` call.

**Where this becomes a genuinely harder question is `Tier.MANUAL_ONLY`
specifically**: ADR-0013's own physical-presence requirement is meant
to mean "a human is physically present and aware, right now, approving
*this specific action*." A plan with, say, five `Tier.ALLOW` steps and
one `Tier.MANUAL_ONLY` step (e.g. a hypothetical future
`memory.forget`/`git.force_push` plan step) would authorize that one
`MANUAL_ONLY` step using the *same* `physical_confirmation_available`
value the user supplied once, before seeing what the plan would
actually do — structurally similar in spirit to exactly the "user
approving 'do the thing' once, in the abstract" failure mode ADR-0062's
own Context section names as the reason per-step authorization exists
at all, even though the *mechanism* (an individual `authorize_by_id()`
call per step) is technically followed. **Two real options, not
resolved here**: (a) `MANUAL_ONLY` plan steps could require a *fresh*,
distinct physical-confirmation prompt per step, re-asked at the moment
that specific step is about to run (a real change to `execute_plan`'s
own signature/control flow, needing a callback or per-step confirmation
source rather than one flat boolean) — the only design that fully
honors ADR-0013's "presence at decision time" intent; (b) `MANUAL_ONLY`
steps could remain permanently excluded from planning entirely,
regardless of whether Options 1/2 above ever close the Provenance gap
— a real, separate, narrower ceiling than "no Tier above ALLOW," worth
naming as its own decision axis rather than assuming closing the
taint-classification gap alone would make `MANUAL_ONLY` steps safe.
ADR-0062's own text already defers this exact question ("a matter of
rollout caution... once the simpler case has real operating
experience") — this document does not resolve it, only names the
concrete mechanism (`execute_plan`'s flat, single confirmation input)
that makes it a real question, not a hypothetical one.

## Summary table

| Option | New signatures touched | Existing code changed | New maintenance surface | Closes the seam gap |
| --- | --- | --- | --- | --- |
| 1. New optional kwarg | One per capability added to plan-step coverage | Yes (existing `authorize_and_*` functions) | None beyond the new parameter | Yes |
| 2. Parallel plan-aware functions | Zero (new functions only) | No | A second function per capability, real drift risk | Yes, at a real, ongoing cost |
| 3. Leave as v1 boundary | None | None | None | No — deferred |

No recommendation is made here; this is options-on-the-table work for
the user's own decision, exactly like `m7-scoping-notes.md`'s own
precedent.
