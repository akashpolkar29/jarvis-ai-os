# Release readiness audit (WP-159, 2026-09-12)

## Status

Real, implemented. Two concrete documentation inconsistencies found
and fixed; no code changed.

## What was checked

`pyproject.toml`'s `version` (`0.9.0`, matches the real, current
`v0.9.0` tag — no drift), `jarvis --version` (reads
`importlib.metadata`, reports `0.9.0` correctly, confirmed live),
README.md, CHANGELOG.md, CLI `--help` text (already mechanically
gated against internal ADR/WP-reference leaks by an existing
meta-test), the installation path (`uv sync --all-groups` — correct,
only one dependency group exists), the test suite and CI (all gates
green as of WP-157's own review), and `docs/protocol/README.md`'s own
CLI-completeness claim.

## Real findings, fixed

1. **README.md's "Privacy model"/"License" sections were stale**:
   both stated "two real, unresolved dependency-license findings"
   (`piper-tts` GPL, `icalendar-searcher` AGPL) — but both were
   genuinely resolved by direct user decision on 2026-09-05
   (`docs/OPEN_DECISIONS.md` items 3a/3b): `piper-tts` was kept, on
   the user's own judgment that GPL's copyleft triggers on
   distribution and this project is not currently distributed;
   `icalendar-searcher`'s real invocation was mitigated to zero via
   `adapters/calendar.py`'s own `server_expand=True`, verified live
   against a real server. Fixed to report both real outcomes, not the
   stale "not yet resolved" framing.
2. **`docs/protocol/README.md`'s own subcommand table was missing five
   real, already-shipped `task` subcommands**: `cancel`/`retry`/
   `schedule`/`recover`/`worker` (built in WP-117/121/122/126/120
   respectively) had no row at all, despite the table's own stated
   purpose ("what does this subcommand actually call"). Added, with
   the same capability-id/flags format every other row uses. The
   table's own running "N real subcommands" count line had also
   separately fallen behind its own convention (several real rows
   were added over time without the count ever being incremented) —
   noted plainly rather than silently re-synced to a number that could
   not be reconstructed with confidence; a direct count (80 table
   rows) was reported instead of continuing the drifted sequence.

## What was deliberately not built

- No new release features, no CHANGELOG rewrite — WP-124 through
  WP-157 are already individually present in `CHANGELOG.md`'s
  `[Unreleased]` section (confirmed by direct check); investigation-
  only work packages (this session's own WP-151/153/155/156/157)
  correctly have no CHANGELOG entry, matching this project's own
  established "CHANGELOG records shipped changes" convention.
- No version bump, no tag — `0.9.0` remains the correct, current,
  already-tagged version; whether a new tag is warranted is a
  separate, already-flagged recommendation (WP-157/`docs/OPEN_DECISIONS.md`
  item 58), not this work package's own decision to make.

## Testing

Lightweight validation only, per this queue's own documentation-only
guidance: `ruff format --check` on both edited files, and a direct,
live check that the two facts restated in README.md (`server_expand`
usage, both `docs/architecture/*` files cited) are real and exist.
