# jarvis end-to-end smoke suite, re-checked (WP-156, 2026-09-12)

## Status

Investigated, **already solved** -- no code change.

## What was investigated

Whether a real, end-to-end smoke-test mechanism already exists.
**Confirmed, two real, complementary layers already exist and both
still pass**:

1. `tests/e2e/test_cli_smoke.py` -- a single, real, freshly-spawned
   `python -m jarvis.cli ping` OS-process invocation, specifically to
   catch packaging/entry-point-level breakage (an import-time error,
   a typo'd module path) that a direct, in-process `main(argv)` call
   structurally cannot catch, since the test process already has
   successful import state. Deliberately narrow by design -- its own
   docstring states the reasoning directly: everything else is tested
   more cheaply via `tests/unit/test_cli_main.py`'s 229 direct-call
   tests.
2. `tests/integration/test_end_to_end_scenarios.py` -- three real,
   hermetic-where-possible scenario tests chaining genuinely-existing
   capabilities through real (non-mocked) code paths: `fs.read_file`
   -> `memory.write` -> `memory.retrieve`; a recalled memory feeding a
   real `coding.run_task` call then `git.status`/`commit`/`status`
   (skipif-guarded on a real, local Ollama server); and
   `fs.search_content` -> `job_search.open_results` ->
   `job_assistance.draft` -> `job_application.record`/`list`, the
   real, hermetic, non-skip-gated one (WP-99's own addition to
   `v0.9.0`).

Both were confirmed still passing as part of this session's own full
gate-suite runs throughout (`uv run pytest -q`).

## Why this was not expanded

A genuinely broader smoke suite (e.g. one subprocess invocation per
subcommand family) was considered and rejected: `test_cli_smoke.py`'s
own docstring already states the precise, narrow reason a subprocess-
level test exists at all (catching packaging breakage, not argument-
level correctness) -- multiplying that same check across many
subcommands would add real CI time for a class of bug (import-time/
packaging errors) that is structurally either present for the whole
package or absent from it; one real invocation already tests the
import path every subcommand shares.

## What was deliberately not built

- No new smoke test file, no expansion of either existing mechanism --
  both already satisfy the real, distinct purposes a "smoke suite"
  and an "end-to-end suite" serve in this codebase, and no new gap was
  found in either.
