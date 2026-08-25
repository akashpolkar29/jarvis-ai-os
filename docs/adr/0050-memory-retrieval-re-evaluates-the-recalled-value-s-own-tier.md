# ADR-0050: Memory retrieval re-evaluates the recalled value's own tier at the point of use

## Status

Proposed

## Date

2026-08-25

## Source

M4 scoping question 2 (`docs/architecture/m4-scoping-notes.md`),
answered directly by the user 2026-08-25: "Memory reads inherit the
tier of what they retrieve -- a CONFIRM-tier memory re-triggers
CONFIRM on recall, it doesn't get a free pass just because it came
from storage instead of a live source." A draft for the user's own
review, not a decision made unilaterally here.

## Context

`RetrievalPort.retrieve()` (ADR-0048) returns `MemoryRecord`s with
their own real, unmodified `Provenance` attached -- the port itself
performs no gating. Left unaddressed, this creates a real, concrete
gap: a `Classification.SENSITIVE` value, once successfully memorized
(behind whatever gate ADR-0049 required at write time), could
otherwise be recalled and used completely ungated thereafter -- the
exact "write-time check only, then a permanent free pass" failure
shape ADR-0038's own Context section already named as the mistake to
avoid (there: whether `Tier.MANUAL_ONLY`'s confirmable-by-presence
design accidentally became an exception path for `EGRESS_SECRET`;
here: whether a one-time write-time gate becomes a permanent exception
path for every later use of the same value).

This is a genuinely new shape of problem for this architecture, not a
straightforward reapplication of an existing pattern: every other
`Tainted[T]` value in this codebase is evaluated once, at the point a
capability invocation carries it -- `CapabilityInvocation.effective_tier`
escalates by one step for a single, specific call. Memory introduces a
value that gets evaluated *again*, potentially many times, at each
future point it's retrieved and used, by callers `RetrievalPort` itself
cannot enumerate in advance.

## Decision

**`RetrievalPort` itself performs no gating** (ADR-0048's own decision,
restated as this ADR's own starting premise). Instead: **any caller
that uses a retrieved `MemoryRecord`'s value inside a new capability
invocation must construct that invocation's `Tainted[T]` argument from
the record's own real, unmodified `Provenance`** -- not a fresh
`Provenance.user()`-style wrapping that would discard the original
classification. Concretely: if a future capability (e.g. a
coding-assistant capability under M5) wants to use a recalled
`SENSITIVE` preference inside a call to a cloud-bound `ReasoningPort`
adapter, that call's own `CapabilityInvocation` carries the record's
real `Classification.SENSITIVE` provenance, and
`AuthorizationOrchestrator.authorize_by_id()` evaluates it exactly as
it would a live `SENSITIVE` value reaching the same call -- `CONFIRM`
required, no exception, because from the Policy Engine's own
perspective it *is* the same case: a `SENSITIVE`-classified value about
to flow into a specific capability, regardless of whether that value's
immediate origin was a live source or memory.

**This is enforced by convention plus a real test, not by new logic in
`domain/policy.py` or `domain/capability.py`** -- neither module gains
new code for this ADR. The real, load-bearing rule is: **no adapter or
application-layer code under this milestone, or any future one
consuming `RetrievalPort`, may construct a fresh, unclassified
`Provenance` for a value that originated from a `MemoryRecord`.** A
real, structural meta-test (mirroring `tests/meta/test_speaker_id_isolation.py`'s
own AST-based enforcement style) is required to check this
mechanically where practical -- named as a real acceptance criterion,
not left to code review alone.

## Consequences

No `Effect`/`Tier` change is needed for this ADR specifically (unlike
ADR-0049) -- the existing `effective_tier` machinery already does the
right thing once a retrieved record's real provenance is correctly
carried into a new invocation; this ADR's whole job is ensuring that
carrying-forward actually happens, every time, not inventing new
authorization logic.

**Real, honestly-named gap this ADR does not close**: enforcing "never
discard a `MemoryRecord`'s real provenance" is a real discipline this
document can require and test for the code this milestone itself
writes, but it does not, and cannot, guarantee every *future*
milestone's own consumer of `RetrievalPort` honors it -- the same class
of trust-the-future-caller gap this project already accepts elsewhere
(e.g. `WorkspacePort`'s own materialized files are only as safe as
whatever reads them next). Named here rather than assumed solved by
this ADR's own existence.

**Also real, also open**: what happens to a retrieved record whose
classification is `SECRET`? Per ADR-0049, a SECRET value should never
have been written in the first place -- if one is ever found in
storage regardless (a bug, a pre-ADR-0049 legacy write, a
classification computed incorrectly at write time), this ADR does not
specify `RetrievalPort`'s own behavior beyond "the normal DENY floor
applies to whatever tries to use it next," which may not be a strong
enough real answer given SECRET's own "should never even be
retrievable" spirit -- flagged as a real open question for the
implementing work package, not resolved here.
