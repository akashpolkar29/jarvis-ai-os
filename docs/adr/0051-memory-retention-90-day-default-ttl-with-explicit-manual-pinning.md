# ADR-0051: Memory retention -- 90-day default TTL, with explicit manual pinning

## Status

Proposed

## Date

2026-08-25

## Source

M4 scoping question 3 (`docs/architecture/m4-scoping-notes.md`),
answered directly by the user 2026-08-25: "Default time-boxed expiry
(suggest 90 days) with an explicit manual 'pin' action for anything
you want kept longer. Not unbounded append-only... and not silent LRU
eviction." A draft for the user's own review, not a decision made
unilaterally here.

## Context

`m4-scoping-notes.md`'s own technical map (question 5) found no
existing port in this codebase deletes anything at all -- this is
genuinely new infrastructure, not an extension of an established
pattern the way most of M3's own ports were. Three real, researched
patterns existed going into this decision (`m4-scoping-notes.md`
Part 2): append-only with manual deletion only, a visible/editable
memory list, and time-boxed retention with renewal. The user's answer
picks a real hybrid of the third and a lightweight version of the
second (an explicit pin, not a full review UI) -- not decided by this
ADR, restated here as the ADR's own starting premise.

Real reasoning behind rejecting the two alternatives, as the user
stated it: unbounded append-only retention is its own privacy risk,
independent of ADR-0049's SECRET-specific denial (a large store of
years-old PERSONAL/SENSITIVE data is a real, growing liability even
though each individual write was authorized correctly at the time);
silent LRU eviction is unpredictable from the user's own perspective
and erodes trust in what the assistant "remembers" (a value could
vanish not because it aged out on a knowable schedule, but because
enough *other* things were recalled more recently -- a real, confusing
failure mode this project's own "always legible" principle argues
against).

## Decision

**Every `MemoryRecord` (ADR-0048) carries a real `expires_at` field**,
set at write time to `written_at + 90 days` by default (a real,
adjustable constant, not hardcoded as a magic literal at every call
site -- a single, named default in `application/memory/retention.py`).
**`written_at`/`expires_at` are computed via `ClockPort`, never
`datetime.now()` directly** -- this project's own banned-API rule
(CLAUDE.md, enforced by ruff + an AST test) applies to this milestone's
new code exactly as it does everywhere else in `src/`.

**A real, callable `pin` action** (part of `MemoryWritePort`'s own
real surface, or a small, adjacent method -- exact port shape left to
the implementing work package, not fixed by this ADR) sets a record's
`expires_at` to `None` (never expires) rather than extending it by a
fixed second window -- a pinned record is retained indefinitely until
explicitly un-pinned or otherwise deleted, matching the user's own
"anything you want kept longer" framing rather than a bounded
extension.

**`RetrievalPort.retrieve()` (ADR-0048) excludes any record whose
`expires_at` has passed** -- enforced at the query layer, not a
separate, periodic garbage-collection sweep the retrieval path trusts
to have already run. A background sweep that actually removes expired
records from the real vector store (reclaiming space, not just hiding
them from queries) is real, separate implementation work the
implementing work package must still do, but `RetrievalPort`'s own
correctness does not depend on that sweep's timing -- an expired,
not-yet-swept record must never be returned, checked directly by a
real test (acceptance criterion 3, `m4-memory-retrieval.md`).

## Consequences

This is the first real deletion-shaped mechanism this codebase has
ever had. `AuditChain`'s own hash-chained, append-only design (ADR-0026)
is explicitly *not* reused or extended for memory's own retention --
the audit log's own append-only guarantee is a security property (a
tamper-evident record of what happened), while memory's retention is a
privacy property (bounding how long personal content persists); the
two have opposite goals (audit: never delete; memory: delete on
schedule) and must not be conflated into one mechanism. A memory
write's own *occurrence* (that a write happened, hash-chained, digest
of arguments only, per ADR-0027) is still logged permanently via the
existing `AuditChain`, matching every other capability invocation --
only the memorized *content* itself is subject to this ADR's own
retention policy, a real, deliberate distinction worth stating
explicitly so a future reader doesn't assume deleting a memory also
scrubs its own audit trail (it does not, and per ADR-0027 the audit
trail never held the raw value to begin with).

**Real, not-yet-answered question, named rather than defaulted
silently**: whether 90 days is the right real default is empirical,
not something this ADR can settle from first principles -- named as a
real, explicit follow-up in `m4-memory-retrieval.md`'s own "Deferred,
not forgotten" section, not fixed permanently by this document.

**Also real, also open**: this ADR specifies retention for records
`MemoryWritePort` creates going forward. It says nothing about a
user-initiated, explicit "forget X" deletion capability distinct from
TTL-driven expiry (`m4-scoping-notes.md`'s own question 3 named this
as a related but separate question) -- not decided here, a real,
plausible follow-up ADR for the implementing work package to raise if
a real need is found, not assumed unnecessary by this document's own
silence on it.
