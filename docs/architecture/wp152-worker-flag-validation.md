# Configuration validation: jarvis task worker's numeric flags (WP-152, 2026-09-12)

## Status

Real, implemented. No ADR -- pure CLI input-validation fix, no new
capability, no `Effect`/`Tier` change.

## What was investigated

This project has no config-file loading mechanism anywhere (confirmed
directly, matching this codebase's own already-established finding),
so "configuration validation" was scoped to CLI argument validation.
Checked every numeric flag on `jarvis task worker`, the one subcommand
whose numeric arguments feed directly into unguarded runtime behavior
(a sleep call, a loop bound) rather than only being passed through to
an authorization/query layer that already handles out-of-range input
gracefully.

**Two real, demonstrated bugs, confirmed live before fixing, not
assumed**:

1. `--poll-interval-seconds -1` reached `time.sleep(-1)` completely
   unvalidated, raising a raw, unhandled `ValueError: sleep length
   must be non-negative` -- a real crash with a Python traceback, not
   a clean CLI error.
2. `--max-passes 0` (or any negative value) made continuous mode's own
   `while args.max_passes is None or passes_run < args.max_passes:`
   condition false immediately -- the worker printed its "Running..."
   banner, ran zero passes, and exited `0`, with no indication
   anything unusual happened. A real, silent no-op.

Other numeric flags across the CLI (e.g. `--limit` on several list/
retrieve commands) were spot-checked with a negative value and found
to already degrade gracefully (SQLite/the underlying query layer
already handles a negative `LIMIT` without crashing) -- left
unchanged, since no real bug was found there.

## What was built

Two small, private `argparse` `type=` validators, `_non_negative_float`
and `_positive_int`, each raising `argparse.ArgumentTypeError` with a
clear, specific message -- argparse's own native mechanism, so the
resulting error/exit-code shape (`exit code 2`, a usage line, then the
error) is identical to any other malformed-argument case a user or
script would already recognize, not a new, bespoke error path. Wired
onto `--poll-interval-seconds` (must be `>= 0`) and `--max-passes`
(must be `>= 1`) on `jarvis task worker` only -- the two flags where a
real, demonstrated bug existed.

## What was deliberately not built

- No broader "config validation framework" or schema -- there is no
  config file to validate, and blanket-auditing every numeric flag
  across all 57+ subcommands for hypothetical out-of-range input was
  judged scope creep beyond this work package's own two, concretely
  demonstrated bugs.
- No change to `--limit` flags -- spot-checked, found to already fail
  gracefully, not fixed since nothing was broken.

## Testing

Two new tests prove `--poll-interval-seconds -1` and `--max-passes 0`
each now exit non-zero via a clean `SystemExit` (argparse's own
mechanism) rather than reaching worker code at all.
