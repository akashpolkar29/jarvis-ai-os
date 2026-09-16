# Skills platform review + next-milestone preparation (WP-180)

## Status

Review only, plus documentation catch-up (ROADMAP.md, OPEN_DECISIONS.md,
CLAUDE.md). No source code changed in this work package.

## Checklist, each verified directly, not assumed

- **No duplicate router**: `git diff` across the whole WP-171-180
  range shows exactly one router file (`kernel/router.py`) modified,
  never duplicated, plus its Stage-B counterpart
  (`application/routing/router.py`) extended in place. No new router
  module exists anywhere in the tree.
- **No duplicate authorization path**: `AuthorizationOrchestrator(`
  construction sites were grepped across `kernel/*.py` before and
  after this queue -- the WP-177 `audit.py` change adds zero new
  construction sites (it filters an already-authorized result set
  after the fact, never authorizes anything a second way).
- **No capability bypass**: every `Skill` is pure data (`id`, `name`,
  `description`, `domain`, `capability_ids`, `instructions`, `tags`)
  with no `Effect`, no `Tier`, and no callable -- structurally
  incapable of invoking anything. Every capability a skill names is
  still invoked exactly as it always was.
- **No new unnecessary effects/tiers**: `git diff a2b4465..HEAD --
  src/jarvis/domain/capability.py src/jarvis/kernel/capabilities.py`
  is empty. Zero new `CapabilityId`/`Effect`/`Tier` anywhere in this
  entire ten-work-package queue.
- **Skills are declarative/orchestration metadata, not uncontrolled
  execution**: confirmed by the type definition itself
  (`domain/skill.py`) and by every one of the eight registered skills
  -- none carries an `instructions` field containing anything but
  prose guidance, never executable content.
- **Task lifecycle remains authoritative**: `kernel/tasks.py` was not
  touched by this queue at all.
- **Planner safety remains intact**: `application/planning/executor.py`
  (ADR-0062's own per-step authorization) was not touched.
  `application/planning/planner.py` (prompt generation) was not
  touched either -- WP-175 only changed the *router's* Stage-B prompt,
  a separate module.
- **Audit remains authoritative**: `domain/audit.py` (the hash chain
  itself) was not touched. `kernel/audit.py` gained one read-time
  filter parameter, changing no write path and no record schema.
- **SECRET/cloud boundary intact**: `application/reasoning/classification.py::egress_effect_for`
  (the function that floors `Classification.SECRET` at unconditional
  `Tier.DENY` for any cloud call, ADR-0038) was not touched, reviewed
  directly in WP-176, confirmed unchanged.
- **CLI/UI continue to work**: live-smoke-tested this session, not
  just unit-tested -- `jarvis skills list`, `jarvis skills show
  research`, `jarvis skills show coding`, `jarvis do --help`, and a
  real `jarvis audit-history --skill filesystem` run against a real,
  on-disk chain file (correctly isolating a real `fs.list_dir` call
  from an unrelated `ping` call). `jarvis ui` was not touched by this
  queue and its own existing test suite (`cli/ui_server.py`'s tests)
  passed unmodified throughout.
- **No regression**: the full suite grew from 1863 passing tests
  (start of this queue, WP-171) to 1911 (end, WP-180) with zero
  failures at any point along the way; all three mandatory 100%
  coverage gates (`domain/*`, `application/policy/*`,
  `application/reasoning/*`) stayed green after every single work
  package, not just at the end.

## Gates -- final, complete run for this report

```
uv run ruff check .              -- pass
uv run ruff format --check .     -- pass
uv run mypy --strict src tests   -- pass
uv run lint-imports               -- 6 contracts kept, 0 broken
uv run pytest -m "not integration" -- 1911 passed, 21 skipped, 0 failed
domain/*            coverage: 100%
application/policy/*     coverage: 100%
application/reasoning/*  coverage: 100%
```

(Skipped tests are the pre-existing, environment-gated ones --
live-credential/live-display/live-GPU cases this project has always
skipped outside their own specific environments, unrelated to this
queue.)

## OPEN_DECISIONS.md / ROADMAP.md / ADR index / version state

- All 63 real ADRs confirmed `Accepted` (checked each one's own
  `## Status` section line directly, not a narrative mention of the
  word "Proposed" elsewhere in a doc). No new ADR was needed by this
  queue.
- `docs/OPEN_DECISIONS.md` gained two new items from this queue: **71**
  (the missing generic web-search capability, WP-178 -- genuinely
  undecided, the user's own call whether/how to build it) and **72**
  (Desktop/Git has no `Skill` yet -- not an open question, a
  deliberately deferred, purely additive future extension, noted so a
  later pass doesn't mistake it for an oversight). Neither resolved
  here, per this work package's own explicit "do not resolve open
  policy decisions by assumption" instruction.
- `docs/ROADMAP.md` gained one condensed entry for WP-171-180, plus an
  honest note that WP-158 through WP-170 (48 real, merged work
  packages predating this queue) were never condensed into that file
  -- a real, pre-existing gap, not introduced or closed by this pass,
  named rather than silently left implicit.
- `CLAUDE.md`'s own "Current Status" section had the identical gap,
  one level more consequential (it is the project's own primary
  onboarding document) -- also named directly, and this queue's own
  real work appended after it.
- **Version state**: `pyproject.toml` still reads `"0.9.0"`; the most
  recent real tag is `v0.9.0`. WP-167 (2026-09-12) already assessed
  the repository as ready for `v0.10.0`, the correct next sequential
  slot -- unchanged by this review, still true. **Not bumped or
  tagged here** -- per this queue's own explicit instruction
  ("DO NOT create a release tag unless the repository's established
  process explicitly permits automatic tagging"), and this project's
  own long-standing precedent that both tagging and the `version`
  field bump happen together, as one real, user-authorized action, not
  separately.

## Recommendation

The repository is coherent, all gates are green, and the new skills
platform is real, tested, and live-verified. `v0.10.0` remains the
correct next tag whenever the user chooses to cut it -- this review
finds nothing that should block that decision, but doesn't make it.
