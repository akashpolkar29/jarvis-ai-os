# Worker operability: real, non-zero exit codes on error (WP-132, 2026-09-12)

## Status

Real, implemented. No ADR -- no new `CapabilityId`/`Effect`/`Tier`, no
new task status, no change to `jarvis.kernel.worker` itself. A pure
CLI-layer change to what `jarvis task worker` reports to the OS.

## What was investigated

Inspected `jarvis task worker` (`_run_task_worker`, `cli/main.py`)
against WP-132's own checklist: concise output, deterministic `--once`
behavior, clean handling of no work, useful failure reporting,
graceful repeated passes. Most of this was already correct and needed
no change: `_print_worker_pass` already prints one concise line per
task plus an explicit "no eligible tasks found" line; `--once` and
`--max-passes` are already fully deterministic (proven by existing
tests with no real sleep); Ctrl+C is already handled cleanly.

**One real gap found**: `_run_task_worker` always returned `0`,
regardless of whether any task in a pass genuinely raised (a real
`WorkerTaskOutcome.error`, e.g. a malformed record or a real exception
`authorize_and_run_task` itself raised). A script, cron job, or
systemd unit driving `jarvis task worker --once` (or a bounded
`--max-passes` run) had no way to detect a real failure except by
parsing the printed text -- ordinary Unix exit-code conventions
weren't honored.

## What was built

`_run_task_worker` now returns `1` if any attempted task in the run
had a real `error` (checked via a small, local
`_pass_had_a_real_error` helper), `0` otherwise:

- `--once`: reflects that one pass's own outcome directly.
- Continuous/bounded (`--max-passes`) mode: an error on *any* pass
  during the whole run fails the final exit code, not just the last
  one -- a script watching only the final exit code still learns that
  something went wrong partway through a multi-pass run.
- Unbounded continuous mode (Ctrl+C): the same accumulated flag
  applies if the loop is ever exited normally; interactive use is
  unaffected since a human is watching the printed output regardless.

**What did not change, stated plainly**: a task simply *not claimed*
(lost a real race to another worker/process, `WorkerTaskOutcome.claimed
= False` with no `error`) is not treated as a failure -- this is
already-documented, correct, expected behavior (WP-120), not an error
condition. `jarvis.kernel.worker.run_pending_tasks_once`'s own
tolerant, never-abort-the-pass behavior is completely unchanged; this
is purely about what the CLI process reports to the OS afterward.

## Testing

`test_cli_main.py`: the existing `--once`-with-a-real-error test
updated to assert exit code `1` (previously asserted `0`, which this
work package intentionally changes); a new test proves a "not
claimed, no error" pass still exits `0`; a new `--max-passes` test
proves an error on the *first* of three passes still fails the whole
bounded run's own final exit code.
