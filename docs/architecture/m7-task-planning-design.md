# M7 task-planning design (7 real decisions prompt, Decision 7, 2026-09-05)

## Status

Real design proposal, not yet implemented, not yet reviewed by the
user. Mirrors `m6a-communications.md`/`m6b-job-assistance.md`'s own
scoping-note-then-design-doc-then-ADR sequence before any code was
written. **No `Dispatcher`/`EscalationLadder` code was touched to
produce this document** -- this pass's own hard gate explicitly
authorizes design/ADR work toward eventually touching that machinery,
but not touching it in this pass itself, and this document honors
that: everything proposed below sits in a new layer *above*
`Dispatcher`, never inside it. Builds directly on
`docs/architecture/m7-scoping-notes.md`'s own real finding (Part 1):
`Dispatcher`/`EscalationLadder` implement retry/escalation for one
already-scoped task, never decomposition of a goal into an ordered,
multi-step, cross-capability plan -- that finding is not repeated in
full here, only extended into a real design.

## What structurally changes: a new layer above `Dispatcher`, not a change to it

The real design is a **new, separate `application`-layer module** --
tentatively `application/planning/` -- that:

1. Takes a single, natural-language goal (a `Tainted[str]`, same
   provenance discipline every other task-shaped input already
   follows).
2. Calls a `ReasoningPort` provider (the *same* real port
   `Dispatcher` already uses -- no new port) with a **planning
   prompt**, distinct from `Dispatcher`'s own task-solving prompt,
   asking for an ordered list of steps, each step naming: (a) an
   already-existing `CapabilityId` (never a new, invented one --
   the planner selects from the real, live capability registry, it
   does not describe free-form actions), and (b) that step's own
   arguments, as a JSON-serializable mapping.
3. Validates the provider's response structurally (every named
   `CapabilityId` must actually exist in
   `CapabilityRegistry.list_capabilities()` -- confirmed by the real
   registry, not trusted from the model's own claim) before treating
   it as a real plan. A response naming an unregistered capability is
   a planning failure, not silently coerced into "close enough."
4. Drives the validated plan through the **existing**
   `AuthorizationOrchestrator.authorize_by_id()` one step at a time,
   exactly as any other caller already does -- `kernel/coding.py`'s
   own `authorize_and_run_coding_task` is the closest real precedent
   for "a composition function that authorizes, then, if granted,
   performs the real action."

**Why a new layer, not a `Dispatcher` change**: `Dispatcher`'s own
real job (climb an escalation ladder for one task, trying
increasingly expensive strategies) is a different problem from
"decompose a goal into steps and run each one." Conflating them would
mean `Dispatcher` needs to know about capability selection and
cross-step dependencies, neither of which is its concern today, and
would require touching code this pass's own hard gate places off
limits. A planner that calls `Dispatcher` *as one possible per-step
mechanism* (e.g., a plan step that is itself a coding task) is a
legitimate future composition, but the planner and `Dispatcher` remain
architecturally separate, each usable without the other -- the same
separation `application/coding/loop.py` already keeps between
`run_coding_task` (a specific caller) and `Dispatcher` (the general
mechanism it wraps).

## How this interacts with the policy engine: no batch pre-approval, ever

**This is the single most safety-relevant property of this whole
design, and it is non-negotiable, not a tuning knob**: a plan is
*never* authorized as a whole. Each step is authorized individually,
by calling `authorize_by_id()` once per step, exactly when that step
is about to run -- never before, never in bulk, never with one
`PolicyContext` covering multiple steps implicitly.

Concretely: a 4-step plan that includes one `Tier.ALLOW` read, one
`Tier.CONFIRM` write, and one `Tier.MANUAL_ONLY` destructive action
results in **three separate real calls** to `authorize_by_id()`
(the fourth step, if also `ALLOW`, a fourth) -- each with its own
`PolicyContext`, each producing its own real `Decision`, each
appended to the real audit chain as its own record. A `MANUAL_ONLY`
step deep inside a plan is denied exactly as it would be if invoked
standalone, with no special "the user already approved the plan"
exception -- `PolicyContext.physical_confirmation_available` is
evaluated fresh, per step, by whatever real confirmation mechanism is
wired in at the moment that step actually runs (the same
`ConfirmationPort`/`Gtk4PhysicalConfirmationAdapter` machinery every
other capability already uses). **A plan is a proposed sequence of
capability calls, not a pre-authorized batch of them** -- this
mirrors `docs/adr/0055-...md`'s own "an escalation ladder tries cheap
things first, but never bypasses per-attempt validation" precedent
and this project's own foundational principle that a single choke
point (the Policy Engine) evaluates every real invocation, with no
alternate path around it.

## Real, open sub-questions this design surfaces, not resolved here

1. **Does a failed step abort the whole plan, or retry/replan?**
   Simplest, safest first version: abort the whole plan on the first
   step that is denied or that fails at runtime, reporting exactly
   which step and why -- no automatic retry, no automatic replanning.
   Retry/replan is real, valuable future scope, but adds real
   complexity (does a retried step re-read state a prior, aborted step
   already changed? Does replanning risk an infinite loop?) that a
   first, minimal version should not need to solve.
2. **Is a plan ever shown to the user before any step executes?**
   A real, valuable safety property, distinct from and layered on top
   of per-step confirmation: showing the full, ordered plan (which
   capabilities, in what order, with what arguments) before the first
   step runs, via the same `ConsolePort`/`GtkConsoleAdapter` mechanism
   `browser.open_page` already uses for a different purpose. This
   would not replace per-step `MANUAL_ONLY` confirmation -- it is an
   *additional* upfront transparency step, not a substitute for it.
   Real open question: is this always shown, or only for plans above
   some step count / containing any `CONFIRM`-or-above step?
3. **Where does plan generation itself sit on the taint ladder?**
   The goal text is `Tainted[str]` with the caller's own real
   provenance (typically `Provenance.user()`, matching every other
   voice/CLI-supplied task string today). The *provider's own
   response* (the proposed plan) is `UNTRUSTED_EXTERNAL`-worthy content
   exactly like any other model output this project already treats
   with suspicion (`ADR-0025`'s own "model opinion carries zero
   weight" precedent) -- it is validated structurally (real
   `CapabilityId`s only) before being trusted as a plan, but a
   provider could still propose a *technically valid but harmful*
   sequence (e.g., real capabilities, wrong order, or an
   attacker-steerable goal string engineering a plan toward a
   `MANUAL_ONLY` action hoping confirmation fatigue grants it) --
   this is exactly why per-step authorization, never batch
   pre-approval, is this design's own load-bearing safety property,
   not merely a implementation convenience.
4. **What does a minimal first real capability under this look
   like?** A new capability, e.g. `planning.run_plan`, `Effect.EXECUTE`
   (matching `coding.run_task`'s own precedent for "this capability's
   own real effect is determined by what it does internally, gated at
   `Tier.CONFIRM` for the outer gate, with every real inner step
   authorized separately regardless of the outer tier"). Its own
   composition function (`authorize_and_run_plan`, mirroring every
   other `authorize_and_*` function's shape) would: authorize itself
   at the outer gate exactly like any other capability, then, if
   granted, generate a plan via the mechanism above, then drive each
   step through `authorize_by_id()` exactly as described. A minimal
   first version would deliberately support only `Tier.ALLOW`/
   `Tier.CONFIRM` steps (no `MANUAL_ONLY` step inside a plan at all,
   for the very first version) -- narrowing real, first-version scope
   while the harder cross-step-`MANUAL_ONLY` interaction is proven out
   more carefully, mirroring this project's own repeated "ship the
   narrow, safe version first" discipline (e.g. M6a's attendee-less
   `create_event` shipping before attendee-bearing events did).

## What this document does not decide

Whether to build this at all, which of the open sub-questions above
get answered which way, and the exact real capability ID / effect
classification are all the user's own decisions, not pre-empted here.
See `docs/adr/0062-task-planning-per-step-authorization-no-batch-pre-approval.md`
for the one real, safety-relevant property from this design (no batch
pre-approval) written up as its own Proposed ADR, since that property
is load-bearing enough to warrant an explicit accept/reject decision
independent of whether the rest of this design is ever built.

## Real implementation (2026-09-05)

This design was built the same day, real, direct instruction: `planning.run_plan`
(`Effect.EXECUTE`/`Tier.CONFIRM`, `kernel/capabilities.py`),
`application/planning/planner.py` (real plan generation +
structural validation, item 3's own JSON-array/registered-capability
checks), `application/planning/executor.py` (item 4's real minimal-
first-version restriction, ADR-0062's own core decision made real),
and `kernel/planning.py` (the real, invocable composition root,
mirroring `kernel/coding.py`'s own shape).

**A real, significant gap found and closed during implementation, not
foreseen by this design's own original text**: step 4's own "drives
the validated plan through `authorize_by_id()`" undersold what
running a step actually requires -- `authorize_by_id()` alone never
performs a capability's real side effect; only each capability's own
hand-written `authorize_and_*` function does. Closed via a new,
generic capability-dispatch registry
(`kernel/capability_dispatch.py`), reusing existing, unmodified
`authorize_and_*` functions rather than inventing a new execution
path. See that module's own docstring for the full account, and
ADR-0062's own closing note for a second, real, narrower-than-planned
restriction this same discovery forced (`Tier.ALLOW`-only steps for
v1, not `Tier.ALLOW`/`Tier.CONFIRM` as originally written above).

**Deliberately minimal initial capability coverage**: only four real
capabilities are wired into the dispatch registry today
(`fs.read_file`, `fs.list_dir`, `git.status`, `memory.retrieve`),
proving the real mechanism end-to-end without attempting every one of
this codebase's 39 capabilities in one pass. Real, open sub-questions
1 and 2 above (retry/replan, plan preview) remain genuinely
unresolved, real future work -- not built.

## Real, disclosed change to plan-generation defaults (2026-09-05)

Adversarial verification of ADR-0062 (a separate, later pass)
empirically measured a real ~33% failure rate for the real, local
`qwen2.5:0.5b` model on plan generation, even for a single-capability
goal (see `docs/threat-model/v0.md`'s own "Adversarial verification of
ADR-0062's real boundaries, Task 3" section for the full, quoted
findings). Following that finding, the user asked for plan generation
to prefer real cloud reasoning by default.

**A real, honest correction made during investigation, not silently
assumed**: neither `kernel/coding.py` nor `kernel/job_assistance.py`
-- the two modules this task was told to mirror -- has any real
credential-auto-detection mechanism at all. Both are purely
explicit-override: a caller passes its own real, cloud-configured
provider/factory, or the default is unconditionally local. There was
nothing to "prefer cloud when configured" against, since this
codebase has no way to detect that anywhere.

**The real, honest change actually made, chosen by the user
directly**: the default stays local (unchanged, mirroring
`coding.py`/`job_assistance.py`'s own real shape exactly, no new
credential-detection invented), but taking that default now logs a
real, observable `logging.WARNING` naming the empirically-measured
~33% failure rate plainly -- `kernel/planning.py`'s own module
docstring carries the full addendum. A caller wanting real cloud
reasoning still supplies its own explicit provider, exactly as
before; doing so produces no warning at all. This is a real, disclosed
behavior change to ADR-0062's own "local-only default" framing above,
not a silent drift -- stated here explicitly.
