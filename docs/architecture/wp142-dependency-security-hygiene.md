# Dependency/security hygiene: pip-audit as a real dev dependency (WP-142, 2026-09-12)

## Status

Real, implemented. No ADR -- a dev-only tooling addition, no
production dependency, no CI gate change.

## What was investigated

CLAUDE.md's own history records several real, past `pip-audit` runs
("Overnight Track 4/5", "Real, dependency/security audit refresh")
-- but `pip-audit` was never actually declared as a project
dependency anywhere; those runs relied on a `pip-audit` that happened
to be available in that session's own environment. Confirmed directly:
`pip-audit` is absent from both `pyproject.toml` and `uv.lock`, and
not installed in this session's own `.venv` before this work package.

## What was built

`pip-audit>=2.10.1` added to `[dependency-groups].dev` in
`pyproject.toml` -- now a real, reproducible, `uv sync`-installed dev
tool, not something a session must happen to have pre-installed.

Run once against this project's own real, freshly-resolved `.venv`:
**no known vulnerabilities found** (one line item skipped honestly,
not silently: the `jarvis` package itself, since it is not published
to PyPI and cannot be audited against it -- expected, not a gap).

## What was deliberately not built

- **No CI gate.** Investigated directly, not assumed: a `pip-audit`
  step's outcome can change over time with *no code change at all* --
  a new CVE published against an already-pinned, otherwise-untouched
  dependency would fail CI on a commit that introduced no real
  regression. This is a genuine non-determinism a CI gate should not
  have (unlike ruff/mypy/pytest, which only ever change result when
  the code under test changes) -- exactly the concern this work
  package's own instructions named ("CI can run deterministically").
  Matches this project's own established, real precedent: every prior
  `pip-audit` run was a deliberate, periodic, manual pass, never a
  CI-gated check.
- No SBOM regeneration, no license-compliance re-scan -- both already
  exist as separate, real, periodic passes (`scripts/generate_sbom.sh`,
  the Phase 9 license audit); out of this work package's own narrow
  scope (dependency vulnerability scanning specifically).

## Testing

All mandatory gates (ruff/mypy/lint-imports/pytest/coverage) re-run
after adding the dependency -- unaffected, since no production or test
source code changed. `pip-audit` itself was run once, manually, as the
real deliverable of this work package; its own clean result is the
evidence, not a new automated test.
