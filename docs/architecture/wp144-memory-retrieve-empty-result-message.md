# Memory retrieval quality: honest empty-result message (WP-144, 2026-09-12)

## Status

Real, implemented. No ADR -- no new memory metadata, no new memory
architecture, pure CLI-output fix.

## What was investigated

Checked `jarvis memory retrieve <query>`'s own output against WP-144's
named risk areas (confusing empty results, unclear output, duplicate
results, weak error handling). Found one real, demonstrated issue:
`_print_outcome`'s handling of `outcome.memory_records` looped over
the tuple and printed one line per record -- for a granted recall
that genuinely matched zero records (`records=()`, a real, common
case, not an error), the loop produced **no output at all**,
indistinguishable from the command silently failing to a user
watching the terminal.

**Demonstrated directly, not assumed**: an existing test
(`test_memory_retrieve_subcommand_routes_query_and_limit`) already
exercised exactly this `records=()` case and only asserted
`exit_code == 0`, never checking the (empty) printed output --
confirming the gap was real and previously unnoticed, not
hypothetical.

`jarvis ui`'s own `_summarize_execution_result` already handles this
correctly for `MemoryRecallOutcome` (`"No matching memories found."`)
-- only the CLI path had the gap.

## What was built

`_print_outcome` now prints `"No matching memories found."` when
`memory_records` is a granted, empty tuple -- the identical message
`jarvis ui` already uses, for consistency across both surfaces.

## What was deliberately not built

- No new memory metadata, no provenance-display changes, no
  deterministic-filtering changes -- none were found to be broken.
- No changes to `authorize_and_recall`/`RetrievalPort` -- the
  underlying retrieval behavior was already correct; only the CLI's
  own silent-on-empty presentation was wrong.

## Testing

A new test proves a granted, zero-match recall now prints the real,
honest message; the existing `records=()` test is untouched (it
still only checks routing/exit code, its own original scope).
