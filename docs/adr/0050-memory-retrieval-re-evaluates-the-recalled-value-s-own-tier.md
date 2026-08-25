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

**Amended, resolving what was originally left as an open gap: a real
`Classification.SECRET` filter at the retrieval boundary itself,
independent of and redundant with ADR-0049's write-time guarantee.**
Per-caller re-evaluation (above) is the right, sufficient mechanism
for `PERSONAL`/`SENSITIVE` records -- those are legitimately memorized,
and the question is only "does the *next* use re-check the right
tier." `SECRET` is different in kind, not degree: per ADR-0049, a
SECRET value should structurally never reach storage at all, so a
SECRET-classified `MemoryRecord` existing in the real store at all is
not a normal case retrieval needs to gate correctly -- it is evidence
that ADR-0049's own write-time guarantee already failed somewhere
upstream, a real integrity violation, not a routine authorization
decision. Relying on "the normal DENY floor applies to whatever tries
to use it next" (the original text here) is not strong enough on its
own: it assumes every future caller's own classification-to-effect
mapping is SECRET-aware, the same generic-future-caller trust gap
named below, applied to the one classification this project has
already decided (ADR-0014/ADR-0038/ADR-0049) gets zero exception paths
anywhere.

**Decision**: `RetrievalPort`'s real adapter unconditionally excludes
any record whose `Provenance.classification is Classification.SECRET`
from its own returned results, before any ranking/relevance logic
runs -- a SECRET record is never returned to any caller, full stop,
regardless of query. This check does not replace ADR-0049's write-time
DENY; it is deliberate, redundant defense-in-depth, matching this
project's own established posture that a single point of enforcement
is not treated as sufficient for its most sensitive classification
(the same reasoning already visible in ADR-0038 requiring a real
property test rather than trusting one code review of the effect
table). **Encountering a SECRET record during a query is not silently
filtered and forgotten**: it is a detectable anomaly indicating
ADR-0049's own guarantee was bypassed somewhere, and must be surfaced
loudly -- a new, real exception type
(`MemoryIntegrityViolationError`, or equivalent, defined on
`ports/retrieval.py`, matching this project's own "define errors on
the port so any adapter raises the same type" convention) raised
after the filtering/exclusion happens, not instead of it, so the
caller's own query still completes safely (no SECRET content leaks
through a crashed query) while the anomaly is not swallowed silently
either. This mirrors the real, already-learned lesson
`adapters/media_player.py`'s own docstring records: an AppArmor
denial silently swallowed as success, caught only by manual
verification -- this ADR chooses not to repeat that shape of mistake
for the one classification this project can least afford it for.

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

**Previously left open, now resolved above (amended)**: what happens
to a retrieved record whose classification is `SECRET` is no longer
an open question -- see the Decision section's own amendment.
`RetrievalPort` never returns one, and encountering one raises a real,
distinct anomaly signal rather than either silently filtering it or
silently returning it. **Still real, still open**: this ADR does not
specify what the implementing work package's own operational response
to a raised `MemoryIntegrityViolationError` should be beyond "surface
it" -- whether that means a real alert to the user, a log entry only,
or something stronger, is genuinely undecided and left for that work
package, not pre-answered by this document.

**Required acceptance criterion, added by this amendment**: a real
test proving that a `MemoryRecord` carrying `Classification.SECRET`,
if present in the underlying store by any means, is never included in
`RetrievalPort.retrieve()`'s returned results, and that encountering
one raises the real, distinct exception this ADR now names -- not
silently dropped, not silently returned.
