# ADR-0060: File management (`fs.list_dir`/`fs.move_file`/`fs.delete_file`) effect/tier classification

## Status

Proposed. Mirrors ADR-0055's/ADR-0056's own "build and prove first,
accept after" sequencing exactly -- this ADR records a real,
already-implemented, already-tested classification, not a
pre-implementation proposal. **Do not accept without the user's own
direct review.**

## Date

2026-09-04

## Source

Direct user instruction ("real, local-only default providers, real
file management, then voice grammar/tag/audits"), itself grounded in
the user's own direct, independent inspection of `ports/file_system.py`
tonight, confirming it was 39 lines with a single `read_text` method,
its own docstring stating write/list/delete were deliberately not
built yet -- the one real gap a charter-completeness re-check found in
this codebase's own real, invocable capability set.

## Context

`FileSystemPort`/`fs.read_file` already establish two real precedents
this ADR reuses rather than reinvents: `Effect.EGRESS_LOCAL`/`Tier.ALLOW`
for "extracting real content out to the caller, even though it never
leaves the machine" (`fs.read_file`'s own docstring), and a real,
coarse `allowed_root` scope boundary (`kernel/files.py`'s own
`_resolve_within_scope`, default `Path.home()`) -- an allowlist, not a
denylist of sensitive subpaths, matching this project's own stated
"allowlist-over-denylist posture (ADR-0007's spirit)."

Three new real capabilities need real classification:

- `fs.list_dir` -- listing a directory's real entries. The identical
  shape `fs.read_file` already established: extracting real content
  (names, not file bytes, but still real content) out to the caller.
  No more sensitive than reading one file.
- `fs.move_file` -- relocating a real file or directory, both
  endpoints within the allowed root. Nothing leaves the machine; the
  identical shape `git.push`/attendee-less `create_event`
  (ADR-0057/ADR-0059) already established for "a real write to
  infrastructure the user already owns."
- `fs.delete_file` -- permanently removing a real file. No undo. The
  identical shape `git.force_push`/`memory.forget` already established
  for this codebase's own most consequential, real actions.

**The one real question requiring its own careful treatment, not just
analogy**: does `fs.move_file`/`fs.delete_file` need a *second*,
separate protection on top of the existing `allowed_root` scope check
-- the same real question ADR-0056's `code_write_effect_for`/
`resolve_protected_patterns` answers for the coding agent, by refusing
to write to a target repository's own detected test files?

## Decision

**`fs.list_dir`: `Effect.EGRESS_LOCAL` (floors `Tier.ALLOW`)** --
identical to `fs.read_file`.

**`fs.move_file`: `Effect.WRITE_LOCAL` (floors `Tier.CONFIRM`)** --
identical to `git.push`'s/an attendee-less `create_event`'s own
precedent.

**`fs.delete_file`: `Effect.DESTRUCTIVE | Effect.IRREVERSIBLE` (floors
`Tier.MANUAL_ONLY`, never remote-satisfiable)** -- identical to
`git.force_push`/`memory.forget`.

**Protected-path question: no additional check beyond the existing
`allowed_root` scope boundary, reused unmodified for all three new
capabilities (both endpoints checked for `fs.move_file`).** Real
reasoning, not a silent omission:

1. `resolve_protected_patterns` (ADR-0056) does not semantically
   transfer here. Its real purpose is narrow and specific: detecting a
   *target repository's own* test-file naming convention, so a
   *coding agent* cannot silently corrupt the tests that would catch
   its own bad patches. General file management has no "target
   repository," no test-file convention to detect, and no autonomous
   agent writing on a human's behalf -- reusing that function would be
   a category error, applying a mechanism to a problem it was never
   built to solve, not a reasonable extension of it.
2. This project's own already-stated, already-applied posture
   (`fs.read_file`'s own docstring, directly quoting it: "a single
   coarse boundary, not a denylist of sensitive subpaths (`.ssh/`,
   `.aws/`, etc.) -- consistent with this project's allowlist-over-denylist
   posture... a denylist would create a false sense of completeness")
   already rejected exactly this kind of check once, for reads. Adding
   a bespoke denylist for move/delete now would contradict that
   already-reasoned position without a new, real justification this
   ADR does not find.
3. **The real, structural reason `fs.delete_file` does not need
   pattern-based protection the way the coding agent does**:
   `Tier.MANUAL_ONLY` requires real, physical, per-invocation human
   confirmation -- the user sees exactly which path is about to be
   permanently deleted and can refuse, every single time. ADR-0056's
   own protected-path check exists precisely *because* the coding
   agent's own real writes do not get that same per-write human
   checkpoint (only one outer `Effect.EXECUTE`/`Tier.CONFIRM` gate on
   invoking the agent at all, per `kernel/coding.py`'s own docstring).
   `fs.delete_file` never has that gap: the physical-confirmation
   floor itself is already the real, per-invocation safeguard.
   `fs.move_file` floors at the weaker `Tier.CONFIRM` (remote-satisfiable,
   like an ordinary local write), but moving is real and reversible --
   nothing is lost, matching this ADR's own move/delete asymmetry
   already stated in `ports/file_system.py`'s own module docstring.

## Consequences

**Makes easier**: no new `Effect` member for `fs.list_dir`/`fs.move_file`
(`EGRESS_LOCAL`/`WRITE_LOCAL` already exist and already have their own
domain-level property-test coverage); `fs.delete_file` reuses
`Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`, already covered by
`tests/property/test_capability.py`'s own existing
`test_high_risk_effect_always_at_least_manual_only` -- no new
domain-level property test needed for any of the three.

**Makes harder / real, deliberately accepted limitation**: the
`allowed_root` scope boundary is coarse -- a user's own home directory
still contains real project repositories, dotfiles, and other
real, sensitive-but-not-system-level content `fs.move_file`/
`fs.delete_file` can reach once granted. This ADR treats
`Tier.MANUAL_ONLY`'s own real, physical confirmation requirement as
the operative safeguard for deletion, not a path-pattern filter --
if that judgment turns out to be wrong in practice (a real, future
incident, not a hypothetical), a protected-path mechanism specific to
general file management, not reused from ADR-0056, would need its own
new ADR.

**Real, deliberately narrow scope, stated plainly**: `fs.delete_file`
removes a single real file only -- recursive directory deletion is a
real, separate, more consequential decision this ADR does not make.
`fs.move_file` does handle real directories (`shutil.move`'s own
native behavior), a real, deliberate asymmetry: moving is reversible,
recursive deletion is not.

**Depends on nothing new being built yet, describes real code already
built**: unlike ADR-0055/ADR-0056's own original pre-implementation
provenance, this ADR is written *after* `ports/file_system.py`/
`adapters/file_system.py`/`kernel/capabilities.py`/`kernel/files.py`/
real tests already exist and pass -- see
`docs/threat-model/v0.md`'s own matching note for what was actually
built.
