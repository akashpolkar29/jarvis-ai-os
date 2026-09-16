# Reasoning / model provider abstraction review (WP-176)

## Status

Review only. **Conclusion: JARVIS already has sufficient provider
abstraction.** No code changed, no new provider added, no new
dependency, no ADR (nothing here changes architecture -- it confirms
the existing one already meets the bar).

## What exists today (checked directly, file by file)

- **`jarvis.ports.reasoning.ReasoningPort`** (`src/jarvis/ports/reasoning.py`)
  -- the one seam between "a task description" and "a proposed
  Candidate." A single-method `Protocol` (`generate(task, prior_attempts)`),
  vendor-name-free by construction and by tooling (ADR-0021,
  `tests/meta/test_source_invariants.py`'s repo-wide grep).
- **`jarvis.domain.reasoning.ProviderProfile`** -- static,
  registered-once provider metadata (`name`, `is_local`). The domain
  analogue of `CapabilityDescriptor`: identity and shape, never a live
  connection.
- **Real adapters implementing the port**
  (`src/jarvis/adapters/reasoning/`): `family_a.py`/`family_b.py`
  (two real, distinct cloud-provider chat-completions integrations,
  deliberately named by shape rather than vendor per ADR-0021 even at
  the adapter ring), `local.py` (`LocalReasoningAdapter`, a real,
  locally-running Ollama-backed provider, `qwen2.5:0.5b`), and
  `cassette.py` (a real, recorded-response test adapter). Four
  concrete, swappable implementations already exist behind one port --
  not a hypothetical extension point.
- **`application.reasoning.router.ModelRouter`** -- authorizes every
  single reasoning-provider call through the *exact same*
  `AuthorizationOrchestrator`/`AuditChain` choke point every other
  capability goes through (ADR-0039). A cloud call's `Effect` is
  computed per call from the task's real `Classification`
  (`application/reasoning/classification.py::egress_effect_for`):
  `Classification.SECRET` -> `Effect.EGRESS_SECRET` -> unconditional
  `Tier.DENY`, no exception path (ADR-0038); everything else ->
  `Effect.EGRESS_SENSITIVE` -> `Tier.CONFIRM`. A local provider never
  egresses at all (`Effect.EGRESS_LOCAL`, floors `ALLOW`). This is the
  real, structural place "SECRET must never reach a cloud provider"
  lives -- not a convention, a mechanism every call passes through.
- **`application.reasoning.dispatcher.Dispatcher` +
  `EscalationLadder` + `Arbiter` + `TaskBudget`** -- a real
  cost-aware escalation policy: cheap rungs before expensive ones,
  self-repair via the local provider before a second cloud provider is
  ever tried, a hard budget ceiling, and an arbiter that *selects* one
  candidate unmodified (never splices two) with model-authored review
  evidence given zero weight (ADR-0025). This is materially more than
  a bare "pick an engine and call it" abstraction -- it is a real
  policy layer over multiple providers, already built and already
  gated at 100% branch coverage (`application/reasoning/*`,
  `application/policy/*`, both CI gates).
- **Already established "safe local default" precedent** --
  `kernel/planning.py`/`kernel/coding.py`/`kernel/job_assistance.py`
  each default to `LocalReasoningAdapter` when no explicit provider is
  supplied, logging a real, honest reliability warning (the measured
  ~33% local-model plan-generation failure rate) rather than silently
  reaching for a cloud provider nobody configured. `kernel/router.py`
  (WP-104/175) follows the identical pattern.

## Comparison with OpenJarvis's engine abstraction (conceptual only)

OpenJarvis's "engine abstraction" is cited as inspiration for a
swappable-backend concept generally -- this review does not import or
adapt any of its code, only compares shape. Conceptually, an "engine"
there plays the role `ReasoningPort` + `ProviderProfile` +
`ModelRouter` jointly play here: a common interface, provider
metadata, and a selection mechanism. What JARVIS's version adds that a
bare engine-swap abstraction would not, by construction of this
project's own architecture, is that **every provider call is itself an
authorized, audited capability invocation** -- there is no path to
calling a reasoning provider that bypasses `AuthorizationOrchestrator`,
because `ModelRouter.authorize_provider_call` is the only real way
`Dispatcher` ever reaches one. An engine abstraction that only
decouples *which backend answers* would not, on its own, guarantee
that decoupling; JARVIS's already does, for free, because the
abstraction is built on top of the same capability/policy primitives
everything else uses, not a separate mechanism.

## What was checked and found NOT to be a gap

- `adapters/reasoning/family_a.py`/`family_b.py` are at 85% line
  coverage, `local.py` at 94% -- in every case the missing lines are
  the one real, live, blocking HTTP call itself
  (`_post_sync`/equivalent), each explicitly documented in its own
  module as "the one real, untested-by-design piece," matching this
  codebase's own long-established, already-accepted convention for
  every other network-dependent adapter (IMAP/CalDAV, STT/TTS,
  browser automation) -- exercised live, once, manually, never by the
  automated suite. Not a new or newly-discovered gap; not something
  this review's own "add only missing tests" instruction calls for
  closing, since closing it would mean either mocking away the real
  boundary this project deliberately leaves unmocked, or requiring
  live credentials in CI, both rejected precedents elsewhere in this
  codebase.
- The mandatory 100%-coverage gates (`application/policy/*`,
  `application/reasoning/*`) already pass, confirmed directly this
  session, not assumed from history.

## What was deliberately not built

- No third/fourth provider adapter "for demonstration" -- explicitly
  out of scope, and two real cloud families plus a real local provider
  already prove the abstraction is genuinely multi-provider, not
  single-implementation.
- No new port, no new `Effect`/`Tier`, no new dependency.
- No change to `Dispatcher`/`EscalationLadder` internals (hard rule
  #11).
- No real credentials configured or exercised.

## Conclusion

The existing `ReasoningPort`/`ProviderProfile`/`ModelRouter`/
`Dispatcher` stack already satisfies every real requirement this work
package named: policy-controlled local and cloud reasoning, an
unconditional SECRET-to-cloud `DENY` floor, no real credentials
required to exist, and no provider-specific routing hacks (rung-to-
provider assignment is an injected, overridable choice, not a
hardcoded branch). This document is the deliverable; no code changed.
