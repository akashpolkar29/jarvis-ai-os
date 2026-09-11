# Task progress / execution-history presentation (WP-124, 2026-09-12)

## Status

Real, implemented. No ADR -- purely additive CLI presentation over
data every real task record already stores; no new stored field, no
change to `TaskGetOutcome`/`TaskListOutcome`/`update_task_status`'s own
shape.

## What was missing

`jarvis task status`/`jarvis task list` (`_print_one_task_record`,
`src/jarvis/cli/main.py`) printed a task's identifier, goal, status,
top-level `reason`, and `scheduled_at` -- but never the record's own
`updated_at` (when it last genuinely changed -- stored since WP-107)
or WP-121's own durable `attempts` history (every concluded execution
attempt, not just the current terminal one). A user retrying a task
twice, for example, had no way to see the *first* failure's own reason
once a second attempt overwrote the top-level `status`/`reason`
fields -- the history was real and durably stored, just never
surfaced anywhere.

## What was built

Two additive print lines/blocks in `_print_one_task_record`, the one
shared helper `task status` and `task list` both already call:

- `updated_at` is now always printed (mirrors `jarvis project
  status`'s own existing, precedented `updated_at` line exactly).
- If `attempts` is a non-empty list, a compact `attempts (N):` section
  follows, one line per attempt (`#<n> <status> <started_at> ->
  <ended_at>`), with an indented `reason:` line only when that
  specific attempt's own reason is not `None`.

Backward compatible by construction: a pre-WP-121 record has no
`attempts` key at all (`data.get("attempts")` is `None`, not a list),
so the section is simply omitted -- no crash, no empty header.

## What was deliberately not built

- No change to `TaskGetOutcome`/`TaskListOutcome`/any kernel function
  -- this is presentation only, reusing data these already return.
- No JSON output mode, no `--verbose`/`--compact` flag -- the existing
  plain-text format gained two pieces of already-stored information,
  nothing configurable was added.
- No attempt-history rendering in `jarvis ui`'s frontend -- a real,
  separate, browser-side follow-up, not this work package's scope.

## Testing

`tests/unit/test_cli_main.py`: a new test proves `updated_at` is
printed for `task status`; a new test proves a real, two-attempt
history renders correctly, including a `None`-reason attempt printing
no `reason:` line (a real branch-coverage case, not just the happy
path); a new test proves a task with no `attempts` key at all prints
no `attempts` section. One existing test
(`test_task_list_subcommand_prints_a_stale_warning_only_for_the_stale_task_id`)
was fixed to check membership within each task's own printed block
rather than assuming the stale warning is the literal next line after
the identifier -- an assumption the new `updated_at` line (which now
always intervenes) broke.
