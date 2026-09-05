# ADR-0061: Memory-store backup/restore (`memory.backup`/`memory.restore`) effect/tier classification

## Status

**Proposed** -- built and tested (10-phase combined pass, Phase 5,
2026-09-05), not yet reviewed by the user. Flagged here, exactly as
ADR-0060 originally was, for the user's own later review of this
document's full text before acceptance -- not treated as accepted by
this pass itself.

## Date

2026-09-05

## Source

Direct instruction (10-phase combined pass, Phase 5: "real memory-store
backup/restore"). No prior scoping note exists for this capability;
classified here directly, following ADR-0060's own established
"build the real thing, classify it honestly, flag for review" sequence
for a work package with no interactive back-and-forth available.

## Context

`SqliteMemoryAdapter` (`adapters/memory.py`) persists every memorized
value to one real SQLite file -- including, by this project's own
existing, already-accepted design (ADR-0049), values classified
`Classification.SECRET` at write time. `memory.write`'s dynamic-effect
resolution only escalates to an unconditional `DENY` when a
`SECRET`-classified value would leave the machine to a cloud provider
-- local storage of such a value in `memory.sqlite3` is not itself
denied. This means the real memory store, as it exists today, may
already contain real, unencrypted secret-shaped plaintext at rest --
an existing, accepted fact this ADR does not change, but must account
for honestly when classifying an action that duplicates the *entire*
store's content into a new file.

Two real, new capabilities need classification:

- `memory.backup` -- copy the real, complete, live memory store to a
  caller-chosen destination path. Reversible in the narrowest sense
  (the original store is untouched), but it is also the one action in
  this codebase that can place a full copy of every SECRET-classified
  value ever memorized at an arbitrary new location in one call --
  meaningfully different from `fs.move_file`'s "one already-existing
  file, no new copy of its content" shape.
- `memory.restore` -- replace the real, live memory store's entire
  content with a backup file's. Not narrowly reversible: whatever the
  live store held immediately before this call that the backup file
  does not itself contain is gone, the same "no built-in undo" finality
  `memory.forget`/`git.force_push` already established, but at the
  scale of the *whole store* rather than one record.

## Decision

**`memory.backup`: `Effect.WRITE_LOCAL` (floors `Tier.CONFIRM`)** --
matching `fs.move_file`'s own precedent for "a real write to
infrastructure the user already owns, nothing leaves the machine."
Considered and rejected: a stronger floor (e.g. treating this as
`Effect.EGRESS_SENSITIVE`) on the theory that a full copy of
potentially-SECRET content is inherently riskier than the taxonomy's
ordinary local write. Rejected because `EGRESS_SENSITIVE`/
`EGRESS_SECRET` describe content leaving the *machine* (ADR-0049's own
scope, "cloud provider" specifically) -- a backup file, wherever it
lands, is still local disk, the same boundary `fs.move_file`/
`fs.read_file` already treat as `WRITE_LOCAL`/`EGRESS_LOCAL`. The real
risk this ADR does recognize (a backup landing somewhere less
protected, e.g. a synced folder) is a consequence of *where* the
caller points `destination_path`, not a new category of effect this
taxonomy has a member for; ADR-0004 closes the taxonomy to ad hoc
extension, and no existing member honestly fits better than
`WRITE_LOCAL`.

**`memory.restore`: `Effect.DESTRUCTIVE | Effect.IRREVERSIBLE` (floors
`Tier.MANUAL_ONLY`, never remote-satisfiable)** -- identical to
`memory.forget`/`git.force_push`, extended here to a whole-store
replacement rather than one record. `Tier.MANUAL_ONLY`'s real,
physical, per-invocation confirmation is the operative safeguard,
mirroring ADR-0060's own reasoning for `fs.delete_file`: the user sees
exactly which backup file is about to overwrite the live store and can
refuse, every single time.

**No new protected-path or content-inspection check for either
capability.** Considered and rejected, mirroring ADR-0060's own
reasoning for `fs.move_file`/`fs.delete_file`: `resolve_protected_patterns`
(ADR-0056) is a category error here for the same reason ADR-0060 already
gave (no target repository, no autonomous agent acting on a human's
behalf); a content-based scan of the backup file for SECRET-shaped
data before restoring would require guessing at another system's own
data shapes with no reliable signal, and would contradict this
project's own allowlist-over-denylist posture in a new, more fragile
way than a path denylist would. `Tier.MANUAL_ONLY`'s physical
confirmation is judged the sufficient, structural safeguard for
`memory.restore`'s destructive half; `memory.backup`'s `Tier.CONFIRM`
matches every other local-write capability's own existing bar.

**Implementation mechanism: SQLite's own real online-backup API
(`sqlite3.Connection.backup()`), not a raw file copy.** A plain
`shutil.copy` of a live SQLite file risks copying a torn, mid-write
snapshot if a write happens to be in flight; `Connection.backup()` is
SQLite's own real, documented mechanism for producing a consistent
copy of a database that may be concurrently open elsewhere, and is
used in both directions here: `backup()` copies the live connection's
content into a fresh connection opened at `destination_path`;
`restore()` opens the backup file as its own source connection and
copies its content into the live, already-open connection, achieving
an atomic-per-SQLite's-own-guarantee in-place replacement without
closing and reopening the store out from under any other code holding
a reference to the same adapter instance.

## Consequences

**Makes easier**: no new `Effect` member needed for either capability
(`WRITE_LOCAL`/`DESTRUCTIVE`/`IRREVERSIBLE` already exist, already
covered by the taxonomy's own domain-level property tests); both
capabilities are static (fixed effects, not value-dependent), so they
register directly in `build_default_registry()` exactly like
`fs.move_file`/`fs.delete_file`/`memory.forget`, no dynamic-effect
authorizer class needed.

**Makes harder / accepted cost**: `memory.backup`'s `Tier.CONFIRM`
floor is remote-satisfiable, meaning a backup containing real SECRET-
classified plaintext can be created without a human physically present
-- accepted here as consistent with every other `WRITE_LOCAL`
capability in this codebase (none of which distinguish "this write's
content happens to be more sensitive" from an ordinary write), not
re-litigated as a new, backup-specific concern this ADR invents. A
future ADR could reconsider this specifically if the user judges
`memory.backup`'s access to the *entire* store's content, in one call,
warrants a stronger floor than a single file's `fs.move_file` action
does -- named here as real, open, unresolved scope, not decided by
this pass.

**Left genuinely open, not decided here**: whether a *partial* restore
(merging a backup's content into the live store rather than replacing
it wholesale) is ever wanted. This ADR classifies only the
whole-store-replacement shape actually built; a merge-based restore
would be new scope requiring its own ADR, not assumed here.
