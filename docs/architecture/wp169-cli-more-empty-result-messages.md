# CLI: more honest empty-result messages (WP-169, 2026-09-12)

## Status

Real, implemented. No ADR — pure CLI-output fix, no new capability, no
change to any real capability's own logic.

## What was investigated

Following the same class of gap already fixed four times this session
(`memory retrieve`, `fs find`/`search-content`/`recent`, `email list`/
`calendar list-events`, and `jarvis ui`'s own separate summarizer),
audited the rest of `_print_outcome`'s `is not None: for x in ...:
print(...)` loops for the identical silent-empty pattern.

**Confirmed live, not assumed**: `jarvis list-dir <empty-but-real-dir>`
printed nothing beyond the `GRANTED` line, and `jarvis audit-history
--capability-id <filter matching nothing>` did the same — both real,
reachable, granted-but-empty states, not errors. `jarvis
list-docker-containers` shares the identical code shape (`if outcome.
docker_containers is not None: for container in ...: print(...)`) and
would have the same gap for a genuinely empty container list — reasoned
structurally and confirmed via a new, mocked test (this session's
development machine has real containers running for other test
infrastructure, so a live, zero-container reproduction wasn't
attempted; the mocked test proves the fix regardless).

## What was built

`_print_outcome` now prints an honest message for each of four cases
when the granted result is genuinely empty: `"(empty directory)"` for
`list-dir` (matching `jarvis ui`'s own already-correct
`_summarize_dir_list` wording exactly), `"No containers found."` for
`list-docker-containers`, `"No matching audit records found."` for
`audit-history`, and `"The generated plan has no steps."` for `plan
run`.

**A real, initially-wrong assumption caught before shipping**: this
work package first assumed `plan_step_records` could never be
genuinely empty, since a plan structurally must have at least one step
by the time it executes. Checked directly against
`application/planning/planner.py::generate_plan`'s own docstring
before finalizing that claim — it says otherwise: an empty plan is
"valid, if useless" when the reasoning provider proposes zero steps,
and "callers decide whether an empty plan is itself an error." No
caller currently rejects one, so `jarvis plan run` was fixed too,
alongside the other three.

## What was deliberately not built

- No change to `fs.list_dir`/`docker.list_containers`/`audit.history`'s
  own authorization or query logic — only the empty-result
  presentation was wrong.
- No change to `jarvis ui`'s own summarizers — `_summarize_dir_list`
  was already correct; `docker.list_containers`/`audit.history` have
  no UI-side summarizer at all (neither is wired into the router's
  execution boundary), so there was nothing to fix there.

## Testing

Four new tests (one per subcommand) prove a granted, genuinely empty
result now prints the real, honest message; existing non-empty-result
and denied tests are untouched.
