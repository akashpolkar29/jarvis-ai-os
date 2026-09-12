# v0.10.0 milestone preparation (WP-167, 2026-09-12)

## Status

Real, read-only review. No tag created — per this work package's own
explicit instruction, tagging is not automated by this pass; this
project has no established automated tagging/release convention
(confirmed by checking `.github/workflows/ci.yml` directly: no
tag/release step exists anywhere in it). Closes this session's
10-work-package queue (WP-158 through WP-167).

## What was checked

- **Tests**: full suite green on `main`'s current tip
  (1854 passed, 1 skipped, 1 known pre-existing failure --
  `test_launch_with_allow_display_can_really_display_a_real_gui_app`,
  an environment-dependent GUI-display test with no real display in
  this CI/dev environment, unrelated to this queue's own changes).
- **CI**: every one of WP-158 through WP-166's real commits confirmed
  green via GitHub Actions before merging, verified directly, not
  assumed.
- **Documentation**: `CHANGELOG.md`'s `[Unreleased]` section, `docs/
  ROADMAP.md` (caught up by WP-158), and `docs/OPEN_DECISIONS.md`
  (66 numbered items, sequentially numbered, no gaps or duplicates)
  are all current as of this review.
- **Version metadata**: `pyproject.toml`'s `version = "0.9.0"` matches
  the real, current `v0.9.0` tag exactly; `jarvis --version` confirmed
  live to report `jarvis 0.9.0` correctly via `importlib.metadata`.
- **CLI**: 72 real subparsers, 45 statically-registered capabilities --
  both unchanged from WP-157's own review, correctly, since this
  queue added no new capability. `docs/protocol/README.md`'s
  subcommand table (80 rows, fixed to be current by WP-159) needed no
  further update.
- **Safety boundaries**: no new `CapabilityId`/`Effect`/`Tier` was
  added anywhere in WP-158 through WP-166 (checked directly, not
  assumed) -- every fix in this queue was either a pure documentation
  correction or an additive error-message/precondition improvement
  reusing existing classifications unmodified (`UnsupportedUrlSchemeError`,
  `SandboxUnavailableError` are new *exception* types, not new
  authorization primitives).
- **Known limitations**: exactly two genuinely open items remain in
  `docs/OPEN_DECISIONS.md` (52: task/job-application retention policy;
  48: browser orphaned-process cleanup, needing a new subsystem), plus
  the separately-tracked audit-chain wholesale-replacement question
  (`docs/architecture/audit-log-integrity-scoping-notes.md`). All
  three already require the user's own decision, not something this
  review resolves.

## Git activity this queue

83 real commits landed on `main` since `v0.9.0` (72 from before this
queue started, 11 from WP-158 through WP-166's own real merges) --
counted directly via `git log --oneline v0.9.0..HEAD`, not estimated.

## Assessment

**The repository is coherent and in good order for a version
milestone.** Every real gate passes, documentation is internally
consistent (no stale claims found by this review beyond what WP-159/
WP-160 already fixed), and no regression was introduced. Per this work
package's own explicit instruction, no tag is created here -- that
decision, and the choice of version number, remain the user's own, the
same standing pattern every prior tag in this project's history has
followed (`v0.1.0` through `v0.9.0`, `docs/ROADMAP.md`'s own "Rolling-
wave planning" section).

If the user chooses to tag, `v0.10.0` is the correct, next sequential
slot (no existing tag claims it).

## What was deliberately not built

- No git tag, no version bump in `pyproject.toml` -- both are the
  user's own decision per this work package's explicit instruction.
- No further code changes -- this is a review, not a fix pass; no new
  gap was found beyond the three already-known, already-flagged items
  above.
