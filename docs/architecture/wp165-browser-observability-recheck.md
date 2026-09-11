# Browser session observability, re-checked (WP-165, 2026-09-12)

## Status

Investigated, **already solved** — no code change. This is the third
independent pass over `adapters/browser_automation.py`'s reliability/
observability this session (after WP-143 and WP-153, both already
recorded in `docs/OPEN_DECISIONS.md`), specifically re-checking the
diagnostic angles WP-165 named.

## What was investigated

- **Navigation/timeout failures**: confirmed real, bounded timeouts
  exist for every real network-facing step (`_DEVTOOLS_PORT_TIMEOUT`,
  `_PAGE_READY_TIMEOUT`, `_CDP_CALL_TIMEOUT`, `_GRACEFUL_EXIT_TIMEOUT`),
  each raising a clear, specific `BrowserLaunchFailedError`/
  `BrowserActionFailedError` message (e.g. `"Page never reached
  readyState=complete within 15.0s."`), not a raw, unexplained
  `TimeoutError`/`OSError`/`WebSocketException` — those three are
  already caught and wrapped at every real call site.
- **Browser startup failure**: `BrowserLaunchFailedError` already
  distinguishes a failed launch from a failed in-page action
  (`BrowserActionFailedError`) — confirmed by direct inspection, not
  assumed.
- **Current URL / navigation state**: `PageHandle` does not store the
  URL it was opened with — checked whether this is a real gap.
  Concluded it is not: the caller always already knows the URL (they
  supplied it to `open_page` themselves), and every subsequent command
  (`screenshot`/`inspect-dom`/`close`) needs the handle's own four
  fields anyway (`jarvis` is stateless between invocations, WP-115's
  own already-documented reason). Adding URL storage would duplicate
  information the caller already has.
- **Cleanup**: the one real, already-known, already-recorded gap
  (`browser.close_page` requiring a kept `PageHandle`, else an orphaned
  process with no CLI-level discovery) is unchanged — closing it needs
  a new, persistent handle-tracking subsystem, explicitly out of this
  work package's own "observability only" scope, matching WP-143's
  identical conclusion.

## What was deliberately not built

- No `PageHandle.url` field, no new diagnostic capability, no change
  to timeout values or error types — all already correct.
- No handle-tracking/orphan-cleanup subsystem — a real, separate,
  larger design decision, already flagged (item 48), not this work
  package's to build.

## Conclusion

No new gap found beyond what WP-143/WP-153 already recorded. See
`docs/OPEN_DECISIONS.md` items 48 and 54 for the full prior
investigations this one confirms rather than repeats.
