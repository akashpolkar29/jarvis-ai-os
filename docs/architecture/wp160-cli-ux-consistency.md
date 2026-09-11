# CLI UX consistency (WP-160, 2026-09-12)

## Status

Real, implemented. One concrete documentation inconsistency found and
fixed; no CLI behavior changed.

## What was checked

- **Help text**: already mechanically gated against internal ADR/WP-
  reference leaks by an existing meta-test; no new leak found.
- **GRANTED/DENIED output format**: confirmed a single, consistent
  format across every top-level invocation (`f"{label}: {status}
  (tier={tier}, reasons={reasons})"`), used at exactly one call site
  and reused everywhere. Per-plan-step lines use a deliberately
  narrower format (`step: <capability_id> <status>`, no tier/reasons)
  — checked and judged not a real inconsistency, since a step shares
  its outer decision's own tier context and already has its own
  established precedent from `planning.run_plan` (ADR-0062).
- **Command naming**: the two real, structural naming inconsistencies
  already found and reviewed by the user (`docs/OPEN_DECISIONS.md`
  item 4 — `memory`'s nested-subcommand shape vs. everything else's
  flat commands; `fs.read_file`'s bare `read` vs. its siblings'
  noun-including names) remain the user's own accepted, left-as-is
  decision; every subcommand added since (`task`/`browser`/`fs`/
  `email`/`calendar`) already follows one of those two established
  shapes consistently, no new inconsistency introduced.
- **Exit codes**: a real, concrete gap. `docs/protocol/README.md`'s own
  "Exit codes" section named only 6 example exception types from an
  early era of this project; the real, current `cli/main.py::main()`
  except tuple has since grown to 24 real exception types (most
  recently `UnsupportedUrlSchemeError`, WP-154, this same session) —
  never updated to match. Confirmed by direct count, not assumed.

## What was built

Rewrote the "Exit codes" section to describe the real behavior
generically (a caught, operational exception -> `1`) rather than
enumerating a list that has already gone stale twice and will keep
drifting as new capabilities are added — pointing at `cli/main.py::
main()`'s own except tuple as the authoritative source, the same "see
the real source for a volatile exact list" pattern this document
already uses for the CI package list. Also documented `argparse`'s own
exit code `2` (previously unmentioned) and `jarvis task worker`'s own,
real, narrower exit-code semantic (WP-132) as an explicit, named
exception to the "granted vs. denied" framing, since that command is
never itself authorized.

## What was deliberately not built

- No CLI behavior change — every finding here was a documentation gap,
  not a real inconsistency in what the CLI actually does.
- No redesign of per-step plan output, confirmation-flag naming, or
  command-naming shapes — all already reviewed, either previously
  accepted by the user (item 4) or newly confirmed consistent.

## Testing

Lightweight validation: `ruff format --check` on the edited file;
direct counting of the real except tuple against the doc's own,
previous claim before rewriting it.
