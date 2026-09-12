# jarvis ui: honest empty-result messages for fs.* results (WP-168, 2026-09-12)

## Status

Real, implemented. No ADR — pure chat-response-text fix, no new
capability, no behavior change to any real capability.

## What was investigated

Following the same class of gap already fixed three times this
session (`jarvis memory retrieve`, `jarvis fs find/search-content/
recent`, `jarvis email list`/`calendar list-events` — all CLI-side),
checked whether `jarvis ui`'s own chat-response summarizer
(`cli/ui_server.py::_summarize_execution_result`) had the identical
gap for its own, separate code path.

**Confirmed live, not assumed**: `_summarize_find_files`/
`_summarize_search_content`/`_summarize_recent_files` returned `None`
for both a *denied* result (`matches is None`) and a *granted, empty*
result (`matches == ()`) — conflating two genuinely different states.
Returning `None` makes the caller's own dispatch loop fall all the way
through every other result-shape check to a generic
`f"Ran {capability_id}."` fallback. A real, empty `fs.find` search via
`jarvis ui` therefore said `"Ran fs.find."`, not an honest "no
results" message — reproduced directly with a real `FileFindOutcome(
matches=())` before fixing. `_summarize_memory_recall`/
`_summarize_list_email`/`_summarize_list_calendar_events` (the same
file) already handled this correctly, only the three `fs.*` helpers
(WP-114) had the gap.

## What was built

All three helpers now return the honest, already-established message
(`"No files found."`/`"No matching lines found."`, matching WP-163's
own CLI message strings exactly) for a genuinely granted-but-empty
result, while still correctly returning `None` — falling through to
the generic fallback, unchanged — for an actually denied result
(`matches is None`). The distinction between "denied" and "granted,
empty" is now explicit (`is None` vs. falsy-but-not-`None`), not
conflated.

## What was deliberately not built

- No change to `fs.find`/`fs.search_content`/`fs.recent`'s own
  authorization or search logic — only the chat-text rendering of an
  already-correct result.
- No change to the CLI's own `_print_fs_search_outcome` (WP-163,
  already correct) or any other summarizer in this file.

## Testing

Rewrote the one existing test that had encoded the old, buggy
fall-through behavior for a *granted* empty result
(`test_summarize_execution_result_for_an_empty_find_files_falls_back`)
into two tests: one proving the new, correct granted-empty message,
one proving a genuinely *denied* result still falls through exactly as
before. Two new, analogous tests added for `search_content`/`recent`'s
own granted-empty case. 100% branch coverage maintained on
`cli/ui_server.py`.
