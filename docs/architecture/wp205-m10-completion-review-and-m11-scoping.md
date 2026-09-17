# M10 completion review + M11 scoping (WP-205, 2026-09-17)

## Status

Real, read-only architecture review, plus one real recommendation for
what M11 should be. No new capability was implemented here -- per this
work package's own instruction ("do NOT blindly implement" a suggested
list; "inspect the repository and existing open decisions first; do
not resolve policy decisions by guessing"), this is investigation and
documentation only. Concludes M10 (WP-191 through WP-204, the "safe
workflow routing and real user workflows" queue).

## What was checked

- **Gates**: `ruff check .`, `ruff format --check .`, `mypy --strict
  src tests`, `lint-imports`, the full `pytest` suite, and all three
  `--fail-under=100` coverage gates (`domain`, `application/policy`,
  `application/reasoning`) all pass on `main`'s current tip (2084
  passed, 21 skipped, zero failures).
- **Protected-file diff across the entire M10 queue**, not just
  per-work-package spot checks: `git diff --stat d860daa..HEAD --
  src/jarvis/kernel/planning.py src/jarvis/application/planning/executor.py
  src/jarvis/application/planning/planner.py
  src/jarvis/kernel/job_application.py src/jarvis/kernel/job_assistance.py
  src/jarvis/kernel/job_search.py src/jarvis/domain/capability.py
  src/jarvis/kernel/capabilities.py
  src/jarvis/application/reasoning/dispatcher.py
  src/jarvis/application/reasoning/ladder.py
  src/jarvis/ports/synthetic_input.py src/jarvis/kernel/desktop.py`
  returns **empty** -- ADR-0062's per-step authorization/no-batch-pre-
  approval, ADR-0058's no-submission boundary, the reasoning
  escalation ladder, and the Terminal synthetic-input port were never
  touched across WP-191 through WP-204.
- **New `CapabilityId`/`Effect`/`Tier` across the whole queue**: `git
  diff d860daa..HEAD -- src/jarvis/kernel/capabilities.py
  src/jarvis/domain/capability.py` is also empty -- zero added. 45
  capabilities remain statically registered
  (`build_default_registry()`), the same count M10 started with.
- **Registries, counted directly, not assumed**: 45 capabilities, 8
  skills (`build_default_skill_registry()`), 3 workflows
  (`build_default_workflow_registry()`).
- **CLI surface**: 79 `add_parser(` call sites in `cli/main.py`
  (subcommands plus nested subcommand groups).
- **Git activity since `v0.9.0`**: 121 real commits.

## Subsystem-by-subsystem review

- **Router** (`kernel/router.py`, `application/routing/router.py`):
  one router, `authorize_and_route`, unchanged in shape since WP-104 --
  Stage A (deterministic grammar) then Stage B (reasoning fallback),
  now with a third `RouteKind.WORKFLOW_RUN` (WP-191/192/193) alongside
  `DETERMINISTIC_COMMAND`/`COMPLEX_GOAL`/`UNKNOWN`. Still the single,
  real execution choke point for `jarvis do`/`jarvis ui`.
- **Skills** (`domain/skill*.py`, `kernel/skills.py`): purely
  declarative discovery metadata over the real capability registry, 8
  registered (filesystem/tasks/memory/calendar/email/browser/research/
  coding). No execution path of its own -- `jarvis skills list/show`
  are not capabilities, mirroring `jarvis doctor`'s established shape.
- **Workflows** (`domain/workflow*.py`, `application/workflow/composer.py`,
  `kernel/workflows.py`): 3 built-in (Job Search Assistant, Research,
  Coding Assistant), reachable now from typed/natural-language input
  (router, WP-191-196), a scheduled task (WP-203), and proven
  structurally incapable of recursive/cyclic composition (WP-204).
  Still reuses `planning.run_plan`'s own outer gate unmodified for
  every real run -- no second authorization path.
- **Planner** (`application/planning/*`, `kernel/planning.py`):
  ADR-0062 unchanged -- `Tier.ALLOW`-only ceiling, one authorization
  call per step, no batch pre-approval, confirmed untouched by the
  protected-file diff above.
- **Tasks** (`kernel/tasks.py`, `kernel/worker.py`): full lifecycle
  (create/run/status/list/cancel/recover/retry/schedule/worker), now
  also workflow-backed (WP-203) with the identical process-safe claim
  mechanism (WP-120) covering both a reasoning-driven and a workflow-
  driven run.
- **Memory** (`kernel/memory.py`, `adapters/memory.py`): write/
  retrieve/pin/forget/backup/restore/wipe/update/get/compare_and_update
  -- unchanged by M10, still the storage substrate under tasks/
  job-application/project.
- **EventBus** (`domain/events.py`): `TaskCreated`/`TaskStatusChanged`
  plus M9's `WorkflowRunDenied`/`Started`/`StepCompleted`/`Halted`/
  `Completed` -- synchronous, in-process, no lock (matches the
  single-threaded `jarvis ui` server's own established reasoning).
- **Audit** (`domain/audit.py`, `adapters/audit_storage.py`): hash-
  chained, `0o600` permissions, atomic writes (WP-101), the cross-
  process lost-write race closed (WP-115). One real, deliberately
  accepted-open gap remains (whole-file replacement by a privileged
  adversary) -- a different, harder threat model, not part of this
  queue's scope, tracked in `audit-log-integrity-scoping-notes.md`.
- **Authorization** (`domain/policy.py`,
  `application/policy/orchestrator.py`): one real choke point,
  `AuthorizationOrchestrator.authorize_by_id()`/`authorize()`, still
  100%-covered, unchanged by M10 beyond gaining the new `WORKFLOW_RUN`
  route as one more real caller of the same, existing surface.
- **CLI/UI**: `jarvis do`/`jarvis ui` both route every request through
  the identical `authorize_and_route`; `jarvis ui`'s own
  `_HANDLED_ROUTING_ERRORS` tuple gained `WorkflowCompositionError`
  (WP-202) so a workflow-specific failure reports precisely, not
  generically. No second execution path exists in either surface.

## M10's own real, honest residual findings (not new, restated for completeness)

- `docs/OPEN_DECISIONS.md` item 74: `fs.search_content`'s matched
  lines carry no `Tainted`/`Provenance` wrapper -- pre-existing
  (WP-94), surfaced by WP-198, not a workflow-layer deficiency, not
  fixed.
- `docs/OPEN_DECISIONS.md` items 52/62: task/job-application record
  retention policy -- genuinely open, needs the user's own decision
  (auto-pin vs. a longer default vs. accept the shared 90-day
  default). Not resolved here, per this work package's own explicit
  instruction not to resolve policy decisions by guessing.
- Not tagged. `v0.10.0` remains the correct next sequential slot
  (unchanged assessment from item 67, WP-167) -- tagging is the user's
  own decision, per this project's entire standing history.

## M11 recommendation: a generic, non-job-specific web-search capability

**The single highest-value missing capability, identified by direct
inspection of `docs/OPEN_DECISIONS.md`, not by guessing from a
suggested list.** Item 71 (found during WP-178, the Research skill's
own foundation work) names a real, concrete, already-diagnosed gap:
`browser.open_page` requires an already-known, literal URL -- it has
no query parameter and builds no search URL of its own.
`job_search.open_results`/`job_search.find_careers_page`
(`kernel/job_search.py`) do build a real search-engine query URL, but
both are narrowly, structurally scoped to job search and are forbidden
by a real meta-test
(`tests/meta/test_job_search_no_content_reading.py`) from ever reading
page content -- the opposite of what a general "gather and read"
research step needs.

**Why this, not the suggested list (GitHub/Gmail/Calendar/browser
research/job-search aggregation/document workflows/notifications)**:
Gmail/Calendar already exist (M6a, IMAP/CalDAV, vendor-neutral by
design -- ADR-0021 forbids vendor names, ruling out a literal "Gmail"
integration anyway); job-search aggregation is explicitly out of scope
by ADR-0058 (no auto-apply, and `job_search.*`'s own content-reading
ban is a deliberate safety boundary, not a gap to remove);
"notifications" and "document workflows" have no real, concrete,
already-diagnosed gap behind them anywhere in this repository's own
`docs/OPEN_DECISIONS.md` -- building either would mean inventing scope
rather than closing a real, found one. Item 71's gap, by contrast, is
already investigated, already has a real, plausible design sketched
(mirror `job_search.find_careers_page`'s own already-proven, ToS-
checked DuckDuckGo pattern: `Effect.EXECUTE`/`Tier.CONFIRM`, opens a
real search-results page in the user's own ordinary Brave browser, no
scraping), and directly unblocks the Research skill/workflow this
session's own M9/M10 queues already built -- today, a research request
naming a source by name rather than URL has no capability to discover
that URL on its own, a real, immediately-felt limitation of already-
shipped functionality, not a speculative new feature area.

**Not implemented here, deliberately**: this capability would touch
`browser.*`/egress, which this project's own established review
pattern requires a new ADR for before building, however small (see
item 71's own closing line). Per this work package's own instruction
("do NOT blindly implement"; "do not resolve policy decisions by
guessing"), the recommendation is surfaced for the user's own review
and ADR authorship, not built unilaterally. If the user accepts this
direction for M11, the natural next step is a short ADR proposal
(mirroring ADR-0060's own "build and classify honestly, flag for
review" sequence used for `fs.list_dir`/`move_file`/`delete_file`) --
not a full implementation pass until that ADR is at least drafted.

**Secondary, lower-priority candidates worth naming, not recommended
first**: the retention-policy decision (items 52/62) is real and
open, but is a policy question, not a missing capability -- resolving
it requires the user's own answer, not more investigation. The
`fs.search_content` provenance gap (item 74) is real but lower-impact
(an internal consistency issue, not a missing user-facing capability)
and would mean changing an already-shipped return shape used by
several existing callers -- a genuinely separate, larger work package
in its own right if the user wants it closed.
