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

## 3b. ~~`icalendar-searcher` (AGPL-3.0-or-later)~~ -- RESOLVED 2026-09-05

**Resolved**: the real `server_expand=True` mitigation (7 real
decisions prompt, Decision 4) was tested empirically against a real,
local Radicale server. Confirmed real: `icalendar_searcher.Searcher.check_component`
(the substantive filtering/expansion logic) was invoked zero times
under the new call shape, versus at least once under a real positive
control using the old shape. Applied as `adapters/calendar.py`'s own
permanent configuration
(`calendar.search(..., event=True, server_expand=True)`, replacing the
deprecated `date_search()`), with a real regression test
(`tests/integration/test_icalendar_searcher_server_expand.py`)
proving both results against a real server, every time it runs. The
dependency remains in `uv.lock` (a transitive dependency of `caldav`
itself, not directly removable) but is no longer exercised at runtime.
See `docs/architecture/license-alternatives-research.md`'s own updated
section for the full methodology, including one real, precise, non-
obvious finding: `caldav`'s own migration docstring example
(`expand=True` alongside `server_expand=True`) does NOT fully avoid
the AGPL code path -- only `server_expand=True` alone, with `expand`
left at its own default, does.

## 4. ~~Two real, structural CLI naming inconsistencies~~ -- RESOLVED 2026-09-05

**Resolved**: the user reviewed both (7 real decisions prompt,
Decision 5) and chose to leave both as-is -- not worth a real,
user-facing, potentially script-breaking rename this deep into the
project. `memory` keeps its nested subcommand group
(`memory write`/`retrieve`/...); `fs.read_file`'s CLI command stays
bare `read`. See `docs/architecture/plugin-architecture-and-cli-ux-audit-phase8.md`'s
own "Real decision recorded" section. No code changed.

## 5. The audit chain's real, open structural gaps -- one of four closed 2026-09-05

**Resolved in part**: the user chose option 1 (7 real decisions
prompt, Decision 6) -- restrictive `0o600` file permissions, now
applied unconditionally on every real `save()`. Raises the bar against
casual/other-local-user tampering. **Does not close the other three**,
stated plainly, not rounded up:

- **Non-atomic writes**: `save()`'s `Path.write_text()` is still not
  atomic -- a process killed mid-write leaves a truncated, invalid
  JSON file. Investigated directly in `docs/threat-model/v0.md`'s own
  "Phase 10 -- 5 smaller tasks" section (10-phase combined pass), still
  open, unrelated to file permissions.
- **No timestamp field**: `AuditRecord` records `sequence`/`decision`/
  `previous_hash`/`record_hash` only -- no wall-clock time at all.
  Named directly in `kernel/audit.py`'s own module docstring, still
  open, unrelated to file permissions.
- **Cross-process race**: two independent processes racing to save the
  same `--chain-path` file still causes the second `save()` to
  silently overwrite the first's new record entirely -- still open,
  unrelated to file permissions.

**What's still needed**: a real architecture decision on the remaining
three gaps in `JsonFileAuditStorageAdapter`'s own persistence format.
Full investigation, four real candidate fixes for the
whole-file-replacement/no-tamper-evidence gap specifically, and the
real record of Decision 6's own scope, in
`docs/architecture/audit-log-integrity-scoping-notes.md`'s own "Real
decision recorded and implemented" section.

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
