# Task diagnostic snapshot: created_at (WP-141, 2026-09-12)

## Status

Real, implemented. No ADR -- no new persistence, no new command, no
secrets exposed, no execution. A single, additive print/JSON field
over data every real task record already stores.

## What was investigated

WP-141 asked whether a new, dedicated `jarvis task inspect <id>`
command combining goal/status/timestamps/schedule/attempts/stale/due
would be useful. Checked directly against the *existing*
`jarvis task status <id>` (`_print_one_task_record`, shared by `task
status`/`task list`) and `GET /api/tasks/<id>` (`jarvis ui`): both
already print/return goal, status, reason, `scheduled_at`, `due`,
`updated_at`, `attempts`, and a stale warning (WP-124/125/130). The
**one** real, missing field was `created_at` -- stored on every task
record since WP-107, never printed or returned anywhere.

Building a separate `jarvis task inspect <id>` command at this point
would have been near-total duplication of `_print_one_task_record`'s
existing output -- not a genuinely new, distinct diagnostic view. The
smaller, more honest fix was adding the one missing field to the
already-existing, already-shared output path instead.

## What was built

- `_print_one_task_record` (`cli/main.py`, shared by `jarvis task
  status`/`jarvis task list`) now prints `created_at` immediately
  after `reason`.
- `GET /api/tasks/<task_id>` (`jarvis ui`) now also returns
  `created_at` in its JSON response, alongside the fields WP-130
  already added.

## What was deliberately not built

- No new `jarvis task inspect` command -- would have duplicated
  existing output for no real, additional value.
- No new stored field -- `created_at` was already stored; this is
  presentation only.

## Testing

Existing tests for both `jarvis task status` and `GET
/api/tasks/<id>` extended with a `created_at` assertion each,
proving the one real, previously-missing field now appears
alongside everything already printed/returned. No new test file
needed -- both call sites already had dedicated coverage.
