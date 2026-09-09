# ADR-0063: `memory.update`/`memory.get` effect/tier classification

## Status

**Accepted (2026-09-09, directly by the user, in conversation, after
direct review of this ADR's own full, verbatim text).**

Built and classified directly, following ADR-0060's/ADR-0061's own
established "build the real thing, classify it honestly, flag for
review" sequence for a work package with no interactive back-and-forth
available at the time it was built. Surfaced in full afterward --
read fresh off disk in conversation, not from memory or a summary --
and the user accepted it as written, no changes requested. The
classification stands exactly as written below: `memory.update` is a
dynamic-effect capability, its own distinct capability id from
`memory.write`; `memory.get` is a static `Effect.READ_LOCAL`/
`Tier.ALLOW` capability, mirroring `memory.retrieve`'s own precedent.
This satisfies the same "reviewed the document, not merely relayed a
decision" bar ADR-0057/ADR-0058/ADR-0059/ADR-0060/ADR-0061 each
already met.

## Date

2026-09-09

## Source

Direct instruction ("Fold project.py into tasks.py, start WP-107").
No prior scoping note exists for either capability; classified here
directly, mirroring ADR-0061's own identical situation.

## Context

`jarvis.kernel.tasks` (WP-107) needed two real, new memory primitives
that did not exist before this work package:

- Every existing write path (`MemoryWritePort.write()`) only ever
  inserts a *new* record with a fresh identifier. Nothing could
  mutate an existing record's own stored *value* in place without
  discarding its identity -- a real `Task`'s own status transitions
  (`created` → `running` → `completed`/`failed`) need exactly this:
  the same task id, repeatedly updated, not a new record per
  transition.
- Every existing read path (`RetrievalPort.retrieve()`) is a
  similarity-ranked, top-K *query* -- an approximation, not an exact
  lookup, already carrying a real, accepted, named limitation
  (`job_application.list`/`project.status`: a large enough store can
  rank a wanted record below the query's own `limit`). A caller that
  already has a real identifier (a UI tracking a task it itself
  created, as one real example) deserves an exact, O(1) lookup, not
  an approximation.

Investigated before building, not assumed: `adapters/memory.py::SqliteMemoryAdapter.pin()`
already runs a real `UPDATE memory_records SET expires_at = NULL WHERE
identifier = ?` -- the underlying SQLite storage engine already
supports in-place mutation by key. Only the public port/composition
surface for updating a record's own *value* (not just its
`expires_at`) was missing. No new storage engine, no schema break.

Two real, new capabilities need classification:

- `memory.update` -- replace an existing record's value in place.
- `memory.get` -- look up one existing record by its own real
  identifier, exactly, no ranking involved.

## Decision

**`memory.update`: a dynamic-effect capability, deliberately not
registered in `build_default_registry()`** -- the identical reason
`memory.write` is not (ADR-0049): the correct `Effect` depends on the
*new* value's own real classification, which no static
`CapabilityDescriptor` can express. `memory_effect_for()` (ADR-0049,
unmodified) resolves the effect exactly as it already does for
`memory.write` -- `Classification.PUBLIC` content (a task's own
goal/status/reason strings, the only real caller today) floors
`Effect.WRITE_LOCAL`/`Tier.CONFIRM`; the identical, already-existing
unconditional `DENY` floor would apply to a hypothetical future caller
updating a record to `Classification.SECRET` content, exactly as
`memory.write` already guarantees for a fresh write. A distinct
capability id from `memory.write` (`application/memory/writer.py::MEMORY_UPDATE_CAPABILITY_ID`,
`"memory.update"`) rather than folding into `memory.write`'s own id:
the audit chain should be able to tell "a new record was created"
apart from "an existing one was mutated in place" when read back
later -- the same reasoning `memory.pin`/`memory.forget` each already
got their own id rather than reusing `memory.write`'s, applied here to
the dynamic-effect side of the port for the first time.

**`memory.get`: a static, fixed-effect capability, `Effect.READ_LOCAL`
(floors `Tier.ALLOW`)** -- registered in `build_default_registry()`,
authorized via the ordinary `authorize_by_id()` path, identical
reasoning to `memory.retrieve`'s own existing registration: reading
one already-known record by its own identifier carries no
classifiable content of its own (the identifier itself is not the
record's content), so there is nothing for a dynamic-effect resolution
to vary on.

**No new protected-record or content-inspection check for either
capability.** Considered and rejected, mirroring ADR-0060's/ADR-0061's
own identical reasoning: `memory.update`'s own dynamic-effect
resolution already provides the real, content-sensitive gate this
taxonomy has a mechanism for (the same `SECRET`-DENY floor
`memory.write` already enforces); a caller-side identifier is not
classifiable content a new check could meaningfully act on beyond
what `memory.get`'s `RetrievalPort.get_by_identifier()`'s own real,
existing SECRET-exclusion (ADR-0050's amendment, applied identically
to this new lookup path) and expiry-exclusion (ADR-0051) already
guarantee.

## Consequences

**Makes easier**: no new `Effect` member needed for either capability
(`WRITE_LOCAL`/`READ_LOCAL` already exist); `memory.get` is static, so
it registers directly, no dynamic-effect authorizer class needed;
`memory.update` reuses `MemoryWriteAuthorizer`'s own existing shape,
extended with one new method (`authorize_update`) rather than a new
class.

**Makes harder / accepted cost**: `memory.update`'s `Tier.CONFIRM`
floor is remote-satisfiable for `Classification.PUBLIC` content,
meaning a task's own status can be transitioned without a human
physically present -- accepted here as consistent with `memory.write`'s
own identical, already-accepted floor for the identical classification,
not re-litigated as a new, update-specific concern.

**Left genuinely open, not decided here**: whether `memory.update`
should ever support a genuine *partial* merge (updating only some
fields of a structured value) rather than the whole-value replacement
actually built. `kernel/tasks.py::update_task_status()` already works
around this at the composition-root level (a real read-modify-write,
preserving fields the caller does not intend to change) rather than
pushing a merge primitive into the port itself -- a deliberate,
minimal-surface choice, not assumed permanent; a future ADR could
revisit this if more callers than `tasks.py` need the same pattern.
