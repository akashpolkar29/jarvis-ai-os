# Open decisions -- one real, single index

Every item below is a real, already-investigated question with no
decision made yet, scattered today across `docs/threat-model/v0.md`,
`docs/ROADMAP.md`, individual ADRs, and scoping notes. This file is
that index -- one real sentence per item on what decision is actually
needed, plus a real link to where the full investigation already
lives. **This document decides nothing.** It does not re-litigate any
investigation, re-open anything already accepted, or recommend an
answer beyond what its own source doc already states. When an item
below is decided, update its own source doc first, then remove or
mark it resolved here -- this file should never be the place a
decision is first recorded.

## 1. M3's own tag

**What's needed**: cut a real `v0.X` git tag for Milestone 3 (desktop
control), which has been code-complete since WP-56 but was
deliberately left untagged while M4/M5/M6 were tagged out of
sequential order around it.

**Already investigated**: nothing to investigate -- this is a pure
action, not a design question. `CLAUDE.md`'s own opening line states
plainly that M3's tag "remains a deliberately separate, later action"
no pass has touched. See `CHANGELOG.md`'s own tagged-release entries
for what M4/M5/M6 shipped around it.

## 2. ~~ADR-0061 (memory backup/restore classification)~~ -- RESOLVED 2026-09-05

**Resolved**: `docs/adr/0061-memory-store-backup-restore-effect-tier-classification.md`
is now **Accepted (2026-09-05, directly by the user, in conversation,
after direct review of the ADR's own full, verbatim text)** -- accepted
as-written, no changes requested. `memory.backup`:
`Effect.WRITE_LOCAL`/`Tier.CONFIRM`; `memory.restore`:
`Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`/`Tier.MANUAL_ONLY`. See the
ADR's own updated Status section for a real, honest scope note:
`memory.wipe` reuses the identical classification in code but was
never itself the subject of this or any ADR document -- this
acceptance covers exactly what ADR-0061's own text describes
(backup/restore), not `memory.wipe` by extension.

## 3a. `piper-tts` (GPL-3.0-or-later) -- RESOLVED 2026-09-05

**Resolved**: a real, direct user decision (7 real decisions prompt,
Decision 3) -- `piper-tts` stays. Reasoning (the user's own judgment
call, not a legal conclusion this project asserts with certainty):
GPL's copyleft obligations trigger on *distribution*, and this project
is currently used personally/privately, not distributed as a packaged
binary to third parties. **Flagged for real re-examination if the
project's distribution model ever changes** (e.g. a built
binary/installer published to others) -- see
`docs/architecture/license-alternatives-research.md`'s own "Real
decision recorded" section for the full reasoning, and
`docs/architecture/secrets-license-sbom-audit-phase9.md`'s own
matching update.

## 3b. `icalendar-searcher` (AGPL-3.0-or-later)

**What's needed**: whether the real `server_expand=True` mitigation
(tested under Decision 4 of the same prompt) actually avoids invoking
`icalendar-searcher`'s own code, and if so, whether to apply it
permanently; if not, the same personal-use reasoning as `piper-tts`
above, pending the user's own further input.

**Already investigated**: `docs/architecture/secrets-license-sbom-audit-phase9.md`
(10-phase combined pass, Phase 9) first found this.
`docs/architecture/license-alternatives-research.md` (3 combined
tasks, Task 3) confirmed the real usage pattern, quoted the real,
relevant AGPL license text directly, and found the real,
no-new-dependency `server_expand=True` mitigation candidate,
unverified against a real server at the time. See this same prompt's
own Decision 4 for the real, empirical test result.

## 4. Two real, structural CLI naming inconsistencies

**What's needed**: a decision on whether to rename either (a real,
user-facing, potentially script-breaking change) or leave both as
historical accretion.

**Already investigated**: `docs/architecture/plugin-architecture-and-cli-ux-audit-phase8.md`
(10-phase combined pass, Phase 8) found both and named them plainly:
`memory` is the only capability family using a nested subcommand group
(`memory write`/`retrieve`/...) instead of the flat, hyphenated style
every other family uses; `fs.read_file`'s own CLI command is bare
`read` (no noun), unlike its later siblings `list-dir`/`move-file`/
`delete-file`. Neither has been renamed.

## 5. The audit chain's real, open structural gaps

**What's needed**: a real architecture decision on the persistence
format `JsonFileAuditStorageAdapter` uses -- this project's own hard
gates have repeatedly named this format itself as off-limits to touch
without that decision being made first.

**Already investigated, four real, distinct gaps, not one**:

- **Non-atomic writes**: `save()`'s `Path.write_text()` is not atomic
  -- a process killed mid-write leaves a truncated, invalid JSON file.
  Investigated directly in `docs/threat-model/v0.md`'s own "Phase 10 --
  5 smaller tasks" section (10-phase combined pass), connected there to
  the same root gap named below, not treated as a separate new problem.
- **No timestamp field**: `AuditRecord` records `sequence`/`decision`/
  `previous_hash`/`record_hash` only -- no wall-clock time at all.
  Named directly in `kernel/audit.py`'s own module docstring (the
  `audit.history` CLI command's real composition root) as a real,
  current limitation of the format, not a bug in that command itself.
- **Cross-process race**: two independent processes racing to save the
  same `--chain-path` file causes the second `save()` to silently
  overwrite the first's new record entirely.
- **Whole-file-replacement / no tamper-evidence at the file level**: no
  protection exists against the entire chain file being wholly
  replaced with a fabricated-but-self-consistent history.

  Both of the last two are investigated in full, with four real,
  named candidate fixes and no recommendation forced, in
  `docs/architecture/audit-log-integrity-scoping-notes.md`
  (property-matrix/fuzzing/concurrency pass, Track 3).

## 6. M7's two scoped-but-undecided questions

**What's needed**: whether either is worth building as new,
real scope, and if so, what.

**Already investigated, real evidence gathered, nothing built**:
`docs/architecture/m7-scoping-notes.md` --

- **"Intelligent task planning"**: the charter names this capability;
  the real finding is that `Dispatcher`/`EscalationLadder` climb three
  fixed rungs for one already-specified task and never decompose a
  goal into a multi-step, cross-capability plan -- the "maps to M2's
  reasoning layer" claim repeated elsewhere is not an accurate full
  capability match.
- **LSP-based code intelligence**: `coding.run_task` currently sends a
  provider no real file content at all (`build_prompt()` never touches
  the filesystem) -- the real, reframed question is whether *any*
  repository context should reach the prompt, not specifically whether
  it must be LSP-shaped.

## Maintaining this index

Add a new numbered entry here whenever a fresh pass surfaces a real,
undecided item spanning more than its own single work package's scope.
Remove or mark resolved only after the real decision is recorded in
the item's own source doc (an ADR's own Status line, a ROADMAP.md
update, etc.) -- never resolve an entry here first.
