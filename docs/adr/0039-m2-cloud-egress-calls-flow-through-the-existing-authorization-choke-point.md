# ADR-0039: M2 cloud-egress calls flow through the existing AuthorizationOrchestrator/AuditChain

## Status

Accepted

## Date

2026-08-18

## Source

Work package WP-29 planning finding (M2 reasoning-layer reconciliation, per `docs/architecture/m2-reasoning-layer.md` and the WP-28 planning pass)

## Context

ADR-0005 states: *"Exactly one policy engine (application/policy) evaluates a capability's declared effects, the tier, and the provenance of the data involved, at exactly one point in the call path before any capability executes."*

`application/policy/orchestrator.py`'s `AuthorizationOrchestrator` is the real, already-implemented instance of that single choke point: `authorize()`/`authorize_by_id()` call `domain.policy.evaluate()` and append the resulting `Decision` to an injected `AuditChain` before returning — by construction, per the module's own docstring, it is "structurally impossible to observe a Decision -- granted or denied -- that was not already durably appended to the chain."

`docs/architecture/m2-reasoning-layer.md` section 5 (deliverable #11) names a separate `OutcomeLogger` for "structured outcome logging for future analysis." Left unspecified, this risks becoming a second, parallel record of what M2 did — which would violate ADR-0005 by giving reasoning-provider calls a real, unaudited path around the one authorization choke point every other capability in this repo already goes through.

## Decision

Reasoning-provider calls (anything that would send a `CapabilityInvocation`'s tainted arguments to a cloud or local `ReasoningPort` adapter) are modeled as real `CapabilityInvocation`s, authorized through the existing `AuthorizationOrchestrator` and hash-chain-audited through the existing `AuditChain` — the same mechanism `ping`, `music.*`, and `fs.read_file` already use. No second authorization or audit path is introduced for M2.

`OutcomeLogger` (deliverable #11) is narrowed explicitly to non-authoritative engineering telemetry only — which rung was reached, latency, pass/fail — and must never record or substitute for an authorization-relevant event. The tamper-evident `AuditChain` remains the single source of truth for "was this egress authorized"; `OutcomeLogger`'s output is not audit-grade and carries no authorization weight.

## Consequences

Every reasoning-provider call gets ADR-0014/ADR-0015's Classification-based gating (once ADR-0038 closes the SECRET/DENY gap) and ADR-0026/ADR-0027's tamper-evident, digest-only audit logging for free, by reuse, rather than by re-implementing an equivalent mechanism inside M2. The cost is that M2's dispatcher must construct real `CapabilityDescriptor`/`CapabilityId` entries for its reasoning capabilities (in `kernel/capabilities.py`'s `build_default_registry()`, matching every existing capability) rather than inventing a lighter-weight internal call path — this is required plumbing, not optional.

`OutcomeLogger`'s narrower scope means it cannot be used later as a workaround to avoid the authorization path for a reasoning call that turns out to be inconvenient to route through `AuthorizationOrchestrator` — any such temptation is itself a sign the capability's effects were declared wrong, not a reason to add a second path.

Required test, to become M2 acceptance criterion #11: no vendor name (`openai`, `anthropic`, `chatgpt`, `claude`, `gpt`) leaks past `adapters/reasoning/` into `application/` or `domain/` — extending ADR-0021's existing enforcement pattern (`tests/meta/test_source_invariants.py`) to the new adapter boundary, not a new mechanism.
