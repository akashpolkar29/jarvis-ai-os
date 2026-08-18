# ADR-0038: SECRET egress to a cloud reasoning provider is a genuine DENY, not MANUAL_ONLY

## Status

Accepted

## Date

2026-08-18

## Source

Work package WP-29 planning finding (M2 reasoning-layer reconciliation, per `docs/architecture/m2-reasoning-layer.md` and the WP-28 planning pass)

## Context

ADR-0014 states: *"Data classified SECRET is DENY for egress to any cloud reasoning provider, with no exception path, no override, and no code path that places it into a model's context window."*

Checked directly against `src/jarvis/domain/capability.py`'s `_EFFECT_TIER_FLOOR`:

```python
_EFFECT_TIER_FLOOR: dict[Effect, Tier] = {
    Effect.DESTRUCTIVE: Tier.MANUAL_ONLY,
    Effect.IRREVERSIBLE: Tier.MANUAL_ONLY,
    Effect.CREDENTIAL: Tier.MANUAL_ONLY,
    Effect.EGRESS_SECRET: Tier.MANUAL_ONLY,
    Effect.EGRESS_SENSITIVE: Tier.CONFIRM,
    ...
}
```

`Effect.EGRESS_SECRET` floors at `Tier.MANUAL_ONLY`, and `domain/policy.py`'s `evaluate()` grants `MANUAL_ONLY` whenever `context.physical_confirmation_available` is `True`. A tier a human can satisfy by being physically present and pressing a button is, by construction, an exception path — it directly contradicts ADR-0014's "no exception path, no override." No shipped M0 capability currently declares `EGRESS_SECRET` (confirmed via `kernel/capabilities.py`'s `build_default_registry()`, which registers only `READ_LOCAL`, `WRITE_LOCAL`, and `EGRESS_LOCAL` effects today), so this gap has never been exercised in real code. M2's `ReasoningPort` adapters are the first real consumer of it: they are the first capabilities in this repo whose whole purpose is sending data to a cloud provider.

Separately, `Tier` (`domain/capability.py`) already defines a `DENY = 3` member, and `evaluate()` already treats it as an absolute ceiling: *"DENY is an absolute ceiling: no confirmation, physical or remote, can override it,"* per the code's own comment and the `if tier == Tier.DENY: granted = False` branch that reads neither confirmation flag. `Tier.DENY` already carries exactly the unconditional semantics ADR-0014 requires — no new tier value needs to be introduced; the fix is a one-entry remapping.

## Decision

Change `_EFFECT_TIER_FLOOR[Effect.EGRESS_SECRET]` in `domain/capability.py` from `Tier.MANUAL_ONLY` to `Tier.DENY`.

## Consequences

Any capability declaring `Effect.EGRESS_SECRET` now floors at an unconditional `DENY`, satisfying ADR-0014 for real rather than by confirmable exception. This is a domain-level change affecting every current and future capability that declares this effect, not only M2's — today's blast radius is zero (no shipped capability uses it), but it is a breaking change to the effect's documented meaning going forward: nothing that ever declares `EGRESS_SECRET` can be designed assuming `MANUAL_ONLY`-style confirmability again.

Two existing tests assert the old behavior and must be updated in the same work package that makes this change (WP-30, not this ADR-writing pass): `tests/unit/test_capability.py`'s `(Effect.EGRESS_SECRET, Tier.MANUAL_ONLY)` and `(Effect.EGRESS_SECRET | Effect.READ_LOCAL, Tier.MANUAL_ONLY)` cases, and `tests/property/test_capability.py`'s grouped property test currently documented as *"DESTRUCTIVE/IRREVERSIBLE/CREDENTIAL/EGRESS_SECRET always floor at MANUAL_ONLY."* `EGRESS_SECRET` moves out of that group into its own `DENY` assertion.

Required test, to become M2 acceptance criterion #9: a property/regression test asserting a SECRET-classified task never reaches a cloud provider at any rung, under any circumstance — including `physical_confirmation_available=True`.
