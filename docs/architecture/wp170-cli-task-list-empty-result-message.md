# CLI: honest empty-result message for jarvis task list (WP-170, 2026-09-12)

## Status

Real, implemented. No ADR — pure CLI-output fix, no new capability, no
behavior change to `task.list` itself.

## What was investigated

Continuing the same sweep WP-169 started (auditing every `is not
None: for x in ...: print(...)` loop in `_print_outcome`/its sibling
helpers), checked `_print_task_outcome`'s own `task_records` handling.

**Confirmed live, not assumed**: `jarvis task list --status cancelled`
against a real store with no matching tasks printed nothing at all
beyond the `GRANTED` line — the identical silent-empty gap already
fixed five times this session. `jarvis ui`'s own `_summarize_task_list`
(the same file's UI-side equivalent) already handled this correctly
(`"No tasks found."`) — only the CLI's own `_print_task_outcome` had
the gap.

## What was built

`_print_task_outcome` now prints `"No tasks found."` when
`task_records` is a granted, empty tuple — the identical message
`jarvis ui`'s own `_summarize_task_list` already uses, for consistency
across both surfaces (the same pattern WP-144 already established
between the CLI and UI for `memory retrieve`).

## What was deliberately not built

- No change to `authorize_and_list_tasks`/`task.list`'s own query or
  filtering logic — only the empty-result presentation was wrong.
- No change to `--scheduled-only`'s own filtering (WP-140) — reuses
  the same `task_records` field and print path, unaffected by this
  fix, confirmed by the existing, still-passing
  `test_task_list_scheduled_only_filters_to_real_scheduled_tasks`.

## Testing

One new test proves a granted, zero-match `task list` now prints the
real, honest message; the existing non-empty and `--scheduled-only`
tests are untouched.
