# Local browser automation reliability, re-checked (WP-153, 2026-09-12)

## Status

Investigated, **already solved** -- no code change. Identical scope
to item 48 (WP-143, `docs/OPEN_DECISIONS.md`), re-verified rather than
re-investigated from a blank slate.

## What was investigated

Re-checked `adapters/browser_automation.py`/`ports/browser_automation.py`
directly, the same real risk areas WP-143 already covered:

- Timeout handling: `_DEVTOOLS_PORT_TIMEOUT`, `_PAGE_READY_TIMEOUT`,
  `_CDP_CALL_TIMEOUT`, `_GRACEFUL_EXIT_TIMEOUT` are all still real,
  bounded waits.
- `close()`: still correctly treats both `ProcessLookupError` and
  `PermissionError` as "already gone" (WP-115's own PID-reuse fix),
  confirmed unchanged.
- Failure reporting: `BrowserLaunchFailedError`/`BrowserActionFailedError`
  still distinguish launch failure from action failure.

No new reliability gap was found beyond the one WP-143 already
recorded and left open: `browser.close_page` requires the caller to
have kept the exact `PageHandle` a prior `open_page` call returned,
and since every `jarvis` invocation is a fresh, stateless process, a
lost handle means an orphaned headless browser process with no
CLI-level way to discover or clean it up. Closing that would mean a
new, persistent handle-tracking mechanism -- a genuinely new
subsystem, not the smallest safe reliability improvement this work
package asked for.

## What was built

Nothing -- see WP-154 for the one real, distinct gap this session's
review of the browser-automation family *did* find and fix (a missing
URL-scheme precondition on `browser.open_page`, a different risk
category than reliability).
