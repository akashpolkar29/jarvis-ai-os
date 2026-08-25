# ADR-0049: SECRET-classified values are a genuine DENY to memory write, mirroring ADR-0038

## Status

Proposed

## Date

2026-08-25

## Source

M4 scoping question 2 (`docs/architecture/m4-scoping-notes.md`),
answered directly by the user 2026-08-25: "SECRET-tier values are
never memorized -- hard DENY at the policy layer for any memory-write
action carrying a SECRET taint, not a CONFIRM prompt." This ADR
resolves the real technical gap that answer surfaced once checked
against actual code (see `m4-memory-retrieval.md`'s own "A real
technical gap decision 2 surfaced" section) -- a draft for the user's
own review, not a decision made unilaterally here.

## Context

Checked directly, not assumed: `domain/capability.py`'s
`CapabilityInvocation.effective_tier` escalates by exactly one step
when `provenance.is_tainted` -- and `is_tainted` (`domain/provenance.py`)
is defined purely as `trust == Trust.UNTRUSTED_EXTERNAL`, with no
reference to `Classification` anywhere. There is no existing generic
mechanism by which a `Classification.SECRET` argument automatically
escalates a capability's tier at all, let alone to `DENY`.

ADR-0038's own real SECRET/DENY enforcement (`Effect.EGRESS_SECRET`
floors at `Tier.DENY`) does not fire generically either -- it requires
a capability invocation to *declare* `Effect.EGRESS_SECRET` in the
first place. `application/reasoning/classification.py`'s real
`egress_effect_for(classification: Classification) -> Effect` is the
actual mechanism: bespoke, per-invocation glue code M2's router calls
at dispatch time, mapping the task's real, runtime classification to
the correct effect *before* `AuthorizationOrchestrator` ever evaluates
the call. A memory-write capability does not inherit this behavior by
resembling M2's cloud-egress case -- it needs the same shape of glue
code built for itself.

Reusing `Effect.EGRESS_SECRET` directly for memory writes was
considered and rejected: that effect's own name and ADR-0038's own
reasoning are specifically about a value *leaving this machine* to a
cloud provider. A local memory write never leaves the machine at all
-- reusing the name would make the effect taxonomy actively misleading
(a future reader seeing `Effect.EGRESS_SECRET` on a memory-write
invocation would reasonably conclude cloud egress is involved, which
would be false), not a harmless shortcut.

## Decision

A new effect, `Effect.MEMORY_WRITE`, added to `domain/capability.py`'s
`Effect` flag enum, with a new `_EFFECT_TIER_FLOOR` entry:

```python
Effect.MEMORY_WRITE: Tier.DENY,
```

A new, real function, `application/memory/classification.py`'s
`memory_effect_for`, directly mirroring `egress_effect_for`'s own
shape:

```python
def memory_effect_for(classification: Classification) -> Effect:
    """Return the Effect a memory-write CapabilityInvocation must declare for `classification`.

    Effect.MEMORY_WRITE (floors Tier.DENY) for Classification.SECRET
    only, matching ADR-0038's own precedent for EGRESS_SECRET: DENY is
    an absolute ceiling, no confirmation overrides it. Effect.WRITE_LOCAL
    (floors Tier.CONFIRM, unchanged from today) for everything else --
    PUBLIC/PERSONAL/SENSITIVE values are memorized behind the same
    ordinary confirmation gate any other local write already requires,
    not specially restricted beyond that by this ADR.
    """
    if classification is Classification.SECRET:
        return Effect.MEMORY_WRITE
    return Effect.WRITE_LOCAL
```

Called by `kernel/memory.py`'s composition root at dispatch time,
before `AuthorizationOrchestrator.authorize_by_id()` runs -- the same
point in the flow `application/reasoning/router.py` already calls
`egress_effect_for`, not a new architectural position invented for
this case.

**No exception path, matching ADR-0014/ADR-0038's own established
rule exactly**: `Tier.DENY` is already, unconditionally, an absolute
ceiling in `domain/policy.py`'s `evaluate()` -- no confirmation,
physical or remote, reads either confirmation flag at that tier. This
ADR adds no new logic to `evaluate()` itself; `Effect.MEMORY_WRITE`'s
own floor is sufficient, the same one-entry-table mechanism ADR-0038
used.

## Consequences

Any capability declaring `Effect.MEMORY_WRITE` floors at an
unconditional `DENY` -- today, that means exactly the real memory-write
capability this milestone registers, but the effect itself is general
enough that a future capability could declare it too, the same way
`Effect.EGRESS_SECRET` is not hardcoded to only M2's adapters.

**Required test, mirroring ADR-0038's own acceptance criterion #9
exactly**: a property/regression test asserting a SECRET-classified
value never reaches the real vector store at any rung, under any
circumstance -- including `physical_confirmation_available=True` --
the same standard already applied to M2's cloud-egress path, applied
here for the first time to a *local* persistence mechanism.

**Real, deliberately narrow scope of this ADR**: it governs write-time
denial only. What happens when a *previously* memorized value's
classification is later reclassified (e.g. a value written as
`PERSONAL` that some future process determines was actually more
sensitive) is not addressed here -- no such reclassification mechanism
exists anywhere in this codebase today, and this ADR does not invent
one. Retrieval-time re-evaluation of an already-stored record's
existing classification is ADR-0050's own, separate concern.
