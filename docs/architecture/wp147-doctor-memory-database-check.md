# jarvis doctor: memory/task-store database check (WP-147, 2026-09-12)

## Status

Real, implemented. `jarvis doctor` already existed (built 2026-09-05,
"Task 4" of the 5-mixed-real-tasks prompt) -- this closes the one real
gap found checking it against WP-147's own checklist (database, task
store, audit storage, worker/scheduler configuration, runtime
dependencies): the memory/task-store database was never checked at
all, only the audit-chain directory.

## What was built

`_check_memory_database_accessible()` -- a real, read-only,
side-effect-free check against the default `memory.sqlite3` path (the
same store both `memory.*` and `task.*` capabilities use):

- Missing entirely: reported as a real, honest, **non-failing**
  informational state ("not yet created -- will be created on first
  write"), not probed further.
- Present: opened strictly read-only (`mode=ro`), then a real query
  against `sqlite_master` (not a bare `SELECT 1`, which SQLite never
  needs to touch the file's own schema for) forces SQLite to validate
  the file's actual format -- catching real corruption, not just
  "the path exists."

**A real bug caught by the test itself, not shipped**: the first
version used `SELECT 1`, a constant expression -- confirmed directly
that SQLite answers it without ever validating the underlying file,
so a garbage/corrupted file was silently reported "accessible." Fixed
to `SELECT name FROM sqlite_master LIMIT 1` before this was committed.

## What was deliberately not built

- No `sqlite3.connect()` against a non-existent path -- that call
  silently creates an empty file, a real side effect a read-only
  diagnostic must never have. The missing-file case is checked with
  `Path.exists()` first and never opened at all.
- No repair/recreation of a corrupted database -- `doctor` only
  reports; WP-147's own hard boundary ("no repairs, no destructive
  actions") is unchanged.

## Testing

Three new tests cover missing/accessible/corrupted real SQLite files
directly against `_check_memory_database_accessible()`; a fourth,
empirical test proves `jarvis doctor` itself never creates the
database file as a side effect (mirroring the existing, identical
proof for the audit chain).
