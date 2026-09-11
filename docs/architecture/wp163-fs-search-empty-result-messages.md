# Safe file operation UX: honest empty-result messages (WP-163, 2026-09-12)

## Status

Real, implemented. No ADR -- pure CLI-output fix, no new capability,
no change to search behavior or path/security checks.

## What was investigated

Checked `jarvis fs find`/`search-content`/`recent` for the same class
of gap WP-144 already found and fixed in `jarvis memory retrieve`:
a granted, zero-match result printing nothing at all.

**Confirmed live, all three, not assumed**: `_print_fs_search_outcome`
looped over `outcome.fs_paths`/`outcome.fs_content_matches` and
printed one line per real match -- for a granted result with zero
matches (`()`, a real, common case, not an error), the loop produced
no output at all beyond the `GRANTED` line, indistinguishable from the
command silently failing to a user watching the terminal. Reproduced
directly against this real machine's own home directory (`fs find
"*.this_pattern_matches_nothing_xyz123"`, `fs search-content` with a
nonsense query, `fs recent --limit 0`) before fixing.

## What was built

`_print_fs_search_outcome` now prints `"No files found."` when
`fs_paths` is a granted, empty tuple (covers both `fs find` and `fs
recent`, which share that field), and `"No matching lines found."`
when `fs_content_matches` is a granted, empty tuple (`fs
search-content`) -- the identical "print an honest line instead of
nothing" fix WP-144 already established for `jarvis memory retrieve`.

## What was deliberately not built

- No change to `fs.find`/`fs.search_content`/`fs.recent`'s own search
  logic, scope checks, or the `capped` reporting mechanism -- all
  already correct; only the empty-result presentation was wrong.
- No change to `authorize_and_find_files`/`authorize_and_search_content`/
  `authorize_and_list_recent_files`.

## Testing

Three new tests (one per subcommand) prove a granted, zero-match
result now prints the real, honest message; existing non-empty-result
tests are untouched.
