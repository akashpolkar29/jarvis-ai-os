# ADR-0041: application/reasoning/ gets the same 100%-branch-coverage gate as domain/ and application/policy/

## Status

Accepted

## Date

2026-08-18

## Source

Work package WP-29 planning finding (M2 reasoning-layer reconciliation, per `docs/architecture/m2-reasoning-layer.md` and the WP-28 planning pass)

## Context

ADR-0032 states: *"Coverage gates are configured per-package in CI - starting with src/jarvis/domain and src/jarvis/application/policy - rather than as one repository-wide threshold, so each security-relevant package must earn its own coverage number."* Its own title states the general principle plainly: coverage is gated per-package, not globally, so that a well-tested but low-stakes package elsewhere in the tree can never mathematically compensate for a badly-tested one that actually matters.

`application/reasoning/` (the escalation ladder, arbiter, router, and classification-gating logic — see `m2-reasoning-layer.md` section 7 and the WP-28 planning pass) is exactly the kind of security-relevant package ADR-0032 was written for: it is where ADR-0038's SECRET/DENY enforcement and ADR-0014/ADR-0015's Classification-based gating actually get exercised for reasoning calls, alongside `domain/` and `application/policy/`.

## Decision

`src/jarvis/application/reasoning/` is added to the set of packages held to 100% branch coverage, on the same terms as `src/jarvis/domain/*` and `src/jarvis/application/policy/*`.

## Consequences

The escalation ladder's five invariants, the arbiter's selection/author-exclusion logic, and the classification-gated router cannot ship partially tested and hide behind a well-covered adjacent package, matching the guarantee ADR-0032 already gives `domain/` and `application/policy/`.

**Deliberately not done in this same pass**: adding `uv run coverage report --include="src/jarvis/application/reasoning/*" --fail-under=100` to CLAUDE.md's gate list, `tests/meta/test_gate_integrity.py`'s `required_snippets`, and `.github/workflows/ci.yml` right now, because `src/jarvis/application/reasoning/` does not exist on disk yet — `coverage report --include=...` against a path with zero matching files does not pass vacuously, it errors, which would make CLAUDE.md's own "ALL must pass before any work package is considered done" gate list fail today, for a package that isn't due until WP-30 at the earliest. This mirrors how ADR-0031/import-linter's C3/C4 contracts are *scheduled* in `tests/meta/test_gate_integrity.py`'s `CONTRACT_SCHEDULE` well ahead of being *configured* in `pyproject.toml` — the decision is recorded now, in this ADR, but the actual gate-list edit lands in the same work package that first creates `application/reasoning/` (WP-30 or wherever its first module lands), not before. That work package's own completion is not considered done until this ADR's gate is actually wired in — this is the tracked follow-up, not an open-ended deferral.
