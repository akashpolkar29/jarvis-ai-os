# Email/calendar read experience: honest empty-result messages (WP-164, 2026-09-12)

## Status

Real, implemented. No ADR — pure CLI-output fix, read-only, no new
capability, no send/create functionality touched.

## What was investigated

Checked `jarvis email list`/`jarvis calendar list-events` for the same
class of gap WP-144/WP-163 already found and fixed elsewhere: a
granted, zero-result response printing nothing at all.

**Confirmed by direct code inspection**: `_print_outcome`'s handling
of `outcome.email_summaries`/`outcome.calendar_events` looped over the
tuple and printed one line per real item — for a granted result with
zero matches (an empty inbox folder, no events in the requested
range), the loop produced no output beyond the `GRANTED` line,
identical to the already-fixed `memory retrieve`/`fs find`/
`search-content`/`recent` gap.

## What was built

Prints `"No messages found."`/`"No events found."` when
`email_summaries`/`calendar_events` is a granted, empty tuple — the
same message style WP-144/WP-163 already established.

## What was deliberately not built

- No change to `communications.list_email`/`list_calendar_events`,
  `ImapEmailAdapter`, `CalDavCalendarAdapter`, pagination/limit
  handling, or connection-error reporting (`EmailConnectionError`
  already reports cleanly) — all already correct.
- No change to `communications.send_email`/`create_calendar_event` —
  out of scope, read-only work package.
- No new connector abstraction.

## Testing

Two new tests (one per subcommand) prove a granted, zero-result
response now prints the real, honest message; existing non-empty-
result and denied tests are untouched.
