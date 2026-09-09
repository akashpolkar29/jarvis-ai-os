# Open decisions -- one real, single index

Every item below is a real, already-investigated question with no
decision made yet, scattered today across `docs/threat-model/v0.md`,
`docs/ROADMAP.md`, individual ADRs, and scoping notes. This file is
that index -- one real sentence per item on what decision is actually
needed, plus a real link to where the full investigation already
lives. **This document decides nothing.** It does not re-litigate any
investigation, re-open anything already accepted, or recommend an
answer beyond what its own source doc already states. When an item
below is decided, update its own source doc first, then remove or
mark it resolved here -- this file should never be the place a
decision is first recorded.

## Honest status snapshot, 2026-09-09

Not a new task list -- a real, single-glance picture of where things
actually stand right now, for future reference. Kept current at each
pass that touches this file; not re-derived from scratch elsewhere.

**Real and done**: the M0-M2 kernel core; M3 (desktop control,
`v0.7.0`); M4 (memory/retrieval); M5 (browser automation + coding
agent); M6a (communications) and M6b (job assistance); real task
planning (`planning.run_plan`, ADR-0062); the real
"job-application automation" feature set -- search
(`job_search.open_results`), draft (`job_assistance.prepare_application_folder`,
`--record`), and track (the applied-jobs ledger) -- tagged `v0.8.0`,
2026-09-08; and browser/filesystem/calendar CLI completeness plus
voice grammar expansion and a real end-to-end scenario test, tagged
`v0.9.0`, 2026-09-08; and WP-101 (2026-09-08), which closed the audit
chain's non-atomic-writes gap (temp-file-then-`Path.replace`, real
tests proving a simulated mid-save crash leaves the original file
untouched); a real, typed project-goal workflow (`jarvis project
start`/`status`, item 15), closing the original charter's "remember my
projects" gap at the workflow level, `Tier.ALLOW`-only bounded by
ADR-0062's own already-accepted v1 ceiling; and a real, persistent
Task/TaskStore (`jarvis task create/run/status/list`, item 16,
2026-09-09), which `project.py` is now folded into, sharing storage,
keeping its own exact public contract unchanged. All items 1-4 and
6-16 below are resolved, decided, or built; only item 5 (one of the
audit chain's four real structural gaps -- the cross-process race)
remains genuinely open.

**Standing, accepted limitations** (not bugs -- real, named, deliberate
scope boundaries, none silently dropped): CV templates are always
copied verbatim, never auto-tailored; no Overleaf integration exists;
job-application submission is never automated (ADR-0058); the audit
chain's cross-process race remains open (item 5); `piper-tts` (GPL)
and the `icalendar-searcher` transitive dependency (AGPL, its real
code path empirically avoided but the package itself still present)
are both kept, by real, direct user decision; `job-application list`'s
broad-recall-then-filter approximation can miss an old entry in a very
large store; two CLI naming inconsistencies (`memory`'s nested shape,
`fs.read_file`'s bare `read`) are left as-is.

**What only the user can do next**: the three real, physical
verifications no unattended pass can supply (a live, end-to-end voice
loop utterance; Terminal's synthetic-typing RemoteDesktop portal
dialog; installing/testing the ChatGPT desktop app, if one ever ships
for Linux); deciding whether CV auto-tailoring is ever worth building,
and if so, defining a real, safe placeholder convention in his own
template first; deciding whether to pursue Overleaf integration if he
ever upgrades off the Free plan; a real architecture decision on the
audit chain's one remaining structural gap, the cross-process race
(item 5).

## 1. ~~M3's own tag~~ -- RESOLVED 2026-09-06

**Resolved**: M3 (desktop control) was tagged `v0.7.0`, 2026-09-06, a
real, direct user decision, with its two real, accepted gaps (Terminal's
synthetic-typing portal call has never fired; the ChatGPT desktop app
was never tested) stated plainly in the tag's own message, mirroring
how M2/M5 were each tagged with accepted gaps. **A real, one-off drift
found and fixed while writing this file's own Task 5 status summary**:
this item was left claiming the tag was still needed for two days
after it was actually cut -- no pass had come back to close it out
until now. See `CHANGELOG.md`'s own `[0.7.0]` entry (itself added
retroactively the same day `v0.8.0` was tagged) and `git show
v0.7.0` for the real, full tag message.

## 2. ~~ADR-0061 (memory backup/restore classification)~~ -- RESOLVED 2026-09-05

**Resolved**: `docs/adr/0061-memory-store-backup-restore-effect-tier-classification.md`
is now **Accepted (2026-09-05, directly by the user, in conversation,
after direct review of the ADR's own full, verbatim text)** -- accepted
as-written, no changes requested. `memory.backup`:
`Effect.WRITE_LOCAL`/`Tier.CONFIRM`; `memory.restore`:
`Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`/`Tier.MANUAL_ONLY`. See the
ADR's own updated Status section for a real, honest scope note:
`memory.wipe` reuses the identical classification in code but was
never itself the subject of this or any ADR document -- this
acceptance covers exactly what ADR-0061's own text describes
(backup/restore), not `memory.wipe` by extension.

## 3a. `piper-tts` (GPL-3.0-or-later) -- RESOLVED 2026-09-05

**Resolved**: a real, direct user decision (7 real decisions prompt,
Decision 3) -- `piper-tts` stays. Reasoning (the user's own judgment
call, not a legal conclusion this project asserts with certainty):
GPL's copyleft obligations trigger on *distribution*, and this project
is currently used personally/privately, not distributed as a packaged
binary to third parties. **Flagged for real re-examination if the
project's distribution model ever changes** (e.g. a built
binary/installer published to others) -- see
`docs/architecture/license-alternatives-research.md`'s own "Real
decision recorded" section for the full reasoning, and
`docs/architecture/secrets-license-sbom-audit-phase9.md`'s own
matching update.

## 3b. ~~`icalendar-searcher` (AGPL-3.0-or-later)~~ -- RESOLVED 2026-09-05

**Resolved**: the real `server_expand=True` mitigation (7 real
decisions prompt, Decision 4) was tested empirically against a real,
local Radicale server. Confirmed real: `icalendar_searcher.Searcher.check_component`
(the substantive filtering/expansion logic) was invoked zero times
under the new call shape, versus at least once under a real positive
control using the old shape. Applied as `adapters/calendar.py`'s own
permanent configuration
(`calendar.search(..., event=True, server_expand=True)`, replacing the
deprecated `date_search()`), with a real regression test
(`tests/integration/test_icalendar_searcher_server_expand.py`)
proving both results against a real server, every time it runs. The
dependency remains in `uv.lock` (a transitive dependency of `caldav`
itself, not directly removable) but is no longer exercised at runtime.
See `docs/architecture/license-alternatives-research.md`'s own updated
section for the full methodology, including one real, precise, non-
obvious finding: `caldav`'s own migration docstring example
(`expand=True` alongside `server_expand=True`) does NOT fully avoid
the AGPL code path -- only `server_expand=True` alone, with `expand`
left at its own default, does.

## 4. ~~Two real, structural CLI naming inconsistencies~~ -- RESOLVED 2026-09-05

**Resolved**: the user reviewed both (7 real decisions prompt,
Decision 5) and chose to leave both as-is -- not worth a real,
user-facing, potentially script-breaking rename this deep into the
project. `memory` keeps its nested subcommand group
(`memory write`/`retrieve`/...); `fs.read_file`'s CLI command stays
bare `read`. See `docs/architecture/plugin-architecture-and-cli-ux-audit-phase8.md`'s
own "Real decision recorded" section. No code changed.

## 5. The audit chain's real, open structural gaps -- three of four closed

**Resolved in part**: the user chose option 1 (7 real decisions
prompt, Decision 6) -- restrictive `0o600` file permissions, now
applied unconditionally on every real `save()`. Raises the bar against
casual/other-local-user tampering. **Updated 2026-09-07**: the
timestamp gap is now closed too -- `AuditRecord` gained a real,
additive `written_at` field (ISO-8601, sourced from a real
`ClockPort`, included in the hash so tampering with it alone is
caught exactly like any other field). **Updated 2026-09-08 (WP-101)**:
the non-atomic-writes gap is now closed too -- `save()` writes the
full new content to a temp file in the same directory, sets its
permissions, then `Path.replace()`s it over the real path in one
atomic, indivisible OS-level step; a crash, kill, or power loss at any
point before the replace leaves the real file exactly as it was, never
truncated or partially written, proven by a real test simulating a
failure mid-save. **Does not close the one remaining gap**, stated
plainly, not rounded up:

- ~~Non-atomic writes~~ -- **CLOSED 2026-09-08 (WP-101)**:
  `save()` now writes atomically (temp-file-then-`Path.replace`). See
  `src/jarvis/adapters/audit_storage.py::JsonFileAuditStorageAdapter.save`'s
  own docstring and `docs/architecture/audit-log-integrity-scoping-notes.md`'s
  own updated note for the full account.
- ~~No timestamp field~~ -- **CLOSED 2026-09-07**: `AuditRecord.written_at`
  is real, additive, hash-included. A real, deliberate breaking
  change to the on-disk format, stated plainly, not silently papered
  over: a pre-2026-09-07 chain file has no `written_at` key at all, so
  loading one raises a plain `KeyError` -- there is no migration path,
  by construction, mirroring ADR-0027's own already-accepted precedent
  for this exact file format. See `jarvis.domain.audit`'s own module
  docstring and `docs/architecture/audit-log-integrity-scoping-notes.md`'s
  own updated note for the full account.
- **Cross-process race**: two independent processes racing to save the
  same `--chain-path` file still causes the second `save()` to
  silently overwrite the first's new record entirely -- still open,
  unaffected by atomicity (each individual `save()` is now
  all-or-nothing, but atomicity says nothing about which of two
  racing writers wins). A real fix needs file locking or a real
  `AuditStoragePort` contract change (e.g. an append-only format), a
  genuine architecture decision, not built here.

**What's still needed**: a real architecture decision on the one
remaining gap in `JsonFileAuditStorageAdapter`'s own persistence
format -- the cross-process race. Full investigation, four real
candidate fixes for the whole-file-replacement/no-tamper-evidence gap
specifically, and the real record of Decision 6's own scope, in
`docs/architecture/audit-log-integrity-scoping-notes.md`'s own "Real
decision recorded and implemented" section.

## 6a. ~~Task planning~~ -- IMPLEMENTED 2026-09-05

**Resolved/built**: real, direct instruction to implement
`m7-task-planning-design.md` and ADR-0062. `planning.run_plan`
(`Effect.EXECUTE`/`Tier.CONFIRM`) is a real, invocable capability --
`application/planning/planner.py` (plan generation + structural
validation), `application/planning/executor.py` (ADR-0062's own core
"no batch pre-approval" decision, made real), `kernel/capability_dispatch.py`
(a real, new generic dispatch registry, closing a real gap found
during implementation -- `authorize_by_id()` alone never performs a
capability's real action), and `kernel/planning.py` (the composition
root). No `Dispatcher`/`EscalationLadder` code was touched. ADR-0062
is now **Accepted**, by relayed instruction, not the user's own
independent reading after the fact -- stated plainly in its own
Status section. Deliberately minimal: only four real capabilities
(`fs.read_file`, `fs.list_dir`, `git.status`, `memory.retrieve`) are
wired into the dispatch registry; a further, real restriction to
`Tier.ALLOW`-only steps (narrower than ADR-0062's own stated
`Tier.ALLOW`/`Tier.CONFIRM` ceiling) was added during implementation
-- see the ADR's own closing note and `executor.py`'s own module
docstring for why. Retry/replan and plan-preview (real, open
sub-questions in the design doc) remain genuinely unbuilt.

**Updated 2026-09-06**: `planning.run_plan` is now real, CLI-reachable
via `jarvis plan run "<goal>"` -- no change to the outer gate or any
plan step's own separate authorization, only a new argument-parsing
and dispatch entry point. `communications.list_email`/
`communications.read_email` (real, already-implemented, `Tier.ALLOW`
capabilities that had never had a CLI entry point -- a real, named gap
from the adapter-failure-resilience pass) are likewise now
CLI-reachable, via `jarvis email list`/`jarvis email read
<message-id>`. See `docs/protocol/README.md`'s subcommand table.

## 6b. ~~LSP-based code intelligence (minimal, non-LSP half)~~ -- IMPLEMENTED 2026-09-05

**Resolved/built**: real, direct instruction to implement
`m7-code-context-design.md`. `application/coding/context.py`'s
`inject_referenced_file_context` folds real, bounded content of files
a task literally names into the task text, tagged
`Trust.UNTRUSTED_EXTERNAL`. Wired as a real, explicit **opt-in**
(`include_referenced_file_context: bool = False` on `CodingTaskRequest`/
`authorize_and_run_coding_task`) -- every existing caller's exact
prior behavior is unchanged unless it opts in, a deliberate
compatibility decision, not silently defaulted on. **Real, deliberately
deferred scope, not built**: the design's own second file-selection
heuristic (files a prior failed attempt's own evidence references, on
a retry climb) -- only the first (task-text-naming) half is
implemented. Full LSP integration itself also remains unbuilt, real,
open future scope if the simpler mechanism proves insufficient.

## 7. ~~Job search (LinkedIn/Indeed)~~ -- RESOLVED 2026-09-06

**Resolved/built**: `docs/architecture/job-search-scoping-notes.md`'s
own real finding (both LinkedIn's and Indeed's current Terms of
Service explicitly prohibit automated scraping/bot access,
corroborated by both sites' own `robots.txt`, and neither offers a
realistic official API for an individual, non-commercial tool) is
resolved by the user's own real decision: assisted browsing, not
automation. `job_search.open_results` (`kernel/job_search.py`,
`jarvis job-search "<keywords>" --site linkedin|indeed [--location
<loc>]`) builds a real, correct search-results URL and opens it in the
user's own, real, ordinary Brave browser (the same real,
already-live-verified `BravePort`/`BraveCliAdapter` mechanism
`desktop.brave_open_url` uses) -- a human does the actual searching
and reading; JARVIS never reads, scrapes, or extracts any listing
content. Mechanically enforced, not just documented:
`tests/meta/test_job_search_no_content_reading.py` proves
`kernel/job_search.py` never imports `BrowserAutomationPort` and never
calls a content-reading method. See the scoping notes' own
"Resolution" section for the full account, including a real, live
finding made during implementation (Indeed's own bot detection
actively blocked a one-time headless-CDP verification load, while
LinkedIn's succeeded) that further confirms why this capability
deliberately uses the real, ordinary Brave mechanism rather than the
headless one. Automated listing extraction remains **explicitly out
of scope**, not merely deferred -- a future capability that did read
page content would still need to resolve the ToS finding this
document already established.

## 8. ~~Extending `planning.run_plan` past `Tier.ALLOW`~~ -- DECIDED 2026-09-07

**Decided**: the user reviewed all three real options
(`docs/architecture/planning-tier-extension-scoping-notes.md`'s own
new-optional-kwarg / parallel-function-layer / leave-as-is options)
and chose to leave the v1 `Tier.ALLOW`-only restriction in place,
permanently for now -- no `Provenance`/`Trust` injection seam will be
built. A real, considered decision, not an oversight: no real
capability currently needs a `Tier.CONFIRM`-or-above plan step. See
that document's own "Decision" section for the full account,
including what would justify revisiting it (a real, concrete future
capability that genuinely needs a higher-tier plan step) and the
separate, still-open `Tier.MANUAL_ONLY` question that survives this
decision unresolved.

## 9. ~~Retry/replan for a failed plan step~~ -- DECIDED 2026-09-07

**Decided**: the user reviewed
`docs/architecture/planning-retry-replan-scoping-notes.md`'s own real
options and chose no retry/replan for now -- a denied or failed plan
step continues to simply end the plan, exactly as `execute_plan()`
already behaves. A real, considered decision: `planning.run_plan`
isn't in real, heavy use yet, so bounded retry/replan would be
speculative complexity for a problem that hasn't actually occurred.
See that document's own "Decision" section for the full account,
including what would justify revisiting it (a real plan failing in
practice in a way retry or replan would concretely have helped).

## 10. ~~Dynamic/out-of-tree plugin loading~~ -- DECIDED 2026-09-07

**Decided**: the user reviewed
`docs/architecture/dynamic-plugin-loading-scoping-notes.md`'s own real
structural finding (same-process code cannot be trusted to honestly
declare its own `Effect`/`Tier`) and chose not to pursue either real
mitigation (process-level sandboxing or a tier floor for dynamic
descriptors), and not to build any loading mechanism, at this time --
no real out-of-tree plugin use case exists yet. **This remains a real,
standing, accepted limitation of the current in-process plugin model,
stated plainly, not silently implied as resolved or safe.** See that
document's own "Decision" section for the full account, including what
would justify revisiting it (a real, concrete request or need for
out-of-tree plugin distribution) and the minimum bar named for
whatever gets built at that point (at least the tier floor mitigation,
seriously weighing process-level sandboxing).

## 11. ~~Monthly application-folder drafting~~ -- RESOLVED/BUILT 2026-09-08

**Resolved/built**: `job_assistance.prepare_application_folder`
(`jarvis prepare-application`) implements the user's own real,
existing workflow -- a per-month folder with a `CV` subfolder and a
`Cover Letter` subfolder, each holding `.tex` files -- as a real,
local capability. Creates the two subfolders and copies the user's
own real CV/cover-letter template files into them verbatim (never
parsing or rewriting their LaTeX content), then reuses
`job_assistance.draft` completely unmodified to draft a real, separate
cover-letter body fragment (`body.tex`) -- never auto-inserted into
the copied template; the user adds one real `\input{body.tex}` line to
his own template, once, by hand. Dynamic-effect classification mirrors
`git.push`/`git.force_push`'s own already-accepted precedent exactly:
`Effect.WRITE_LOCAL`/`Tier.CONFIRM` ordinarily, escalating to
`Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`/`Tier.MANUAL_ONLY` when
`--force` is used to overwrite a real, already-existing application
folder -- without `--force`, an existing folder fails cleanly before
authorization even runs (`ApplicationFolderAlreadyExistsError`),
proven by a real test that the first call's own content survives
untouched.

**No Overleaf integration of any kind exists or is planned**, stated
plainly: confirmed via Overleaf's own documentation that git access is
a paid-plan feature, and the user is on the Free plan. This is purely
local file drafting -- uploading to Overleaf (or not) remains the
user's own manual step afterward, unchanged from today. A real,
explicit v1 scope limit, not an oversight: the CV template is copied
only, never auto-tailored to the specific application; real tailoring
of clearly-delimited CV fields is a separate, future decision that
would first need the user to define a real, safe placeholder
convention in his own template.

## 12. ~~Applied-jobs ledger~~ -- RESOLVED/BUILT 2026-09-08

**Resolved/built**: `jarvis.kernel.job_application` (`jarvis
job-application record`/`jarvis job-application list`) closes a real,
original charter gap -- "store the data of applied job roles" -- as a
real, thin structured-content *convention* on top of the already-real
`memory.write`/`memory.retrieve` capabilities, exactly as required: no
new port, adapter, or `CapabilityId` was built.

**Investigation finding, confirmed before writing any code**:
`MemoryRecord.value: Tainted[object]`, `SqliteMemoryAdapter.write()`,
`memory_effect_for()`, and `MemoryWriteAuthorizer.authorize_write[T]`
already supported arbitrary JSON-serializable structured values (the
WP-65-era "str-only" limitation this codebase's own history already
flagged as narrowed, with "no real caller yet" -- this is that real
caller). Only `authorize_and_remember`'s own public parameter was
narrower than everything downstream of it; retyped from `text: str` to
`value: object`, confirmed backward-compatible by checking every real
call site passes it positionally, none by the old `text=` keyword.

**The real "distinguishing tag" mechanism**: `MemoryRecord` has no
tag/category field, and `RetrievalPort`'s only real interface
(`retrieve(query, *, limit)`) is a cosine-similarity-ranked top-K
search -- confirmed directly, no exact/prefix-match primitive exists
anywhere in this codebase today. Rather than inventing a new
`MemoryRecord` field (explicitly ruled out), each job-application
record embeds a fixed `"kind": "job_application"` marker key inside
its own JSON value; `list` recalls broadly (a fixed, generous internal
limit) and filters precisely on that marker afterward. **A real,
named limitation, not hidden**: a store holding far more distinct
memories than that internal limit could, in principle, rank an older
job-application record below the cutoff and have it go unlisted -- an
inherent consequence of reusing a similarity-ranked retrieval
mechanism with no exact filter, out of this work package's own scope
to fix (would need a real `RetrievalPort` interface change).

Effect/tier: both functions reuse `authorize_and_remember`/
`authorize_and_recall` completely unmodified, so there is no separate
classification to review -- `record` is exactly `memory.write`'s
(`Effect.WRITE_LOCAL`/`Tier.CONFIRM`, `Classification.PUBLIC`); `list`
is exactly `memory.retrieve`'s (`Effect.READ_LOCAL`/`Tier.ALLOW`).

## 13. ~~prepare-application --record wiring, README workflow docs, v0.8.0 tag~~ -- RESOLVED/BUILT 2026-09-08

**Resolved/built**: `prepare-application` gained a real, additive
`--record` flag -- a granted folder creation also calls
`job_application.record` automatically (`status=drafted`, the real
folder just created, derived from `outcome.cv_path`'s own parent's
parent). Omitting it leaves behavior exactly as before, proven by a
real test that the ledger function is never even called without the
flag. A real, end-to-end kernel test (not just a CLI-mock test) proves
the full prepare -> record -> list chain recovers the correct folder
path.

A real "Job-application workflow" section was added to `README.md`
(search -> draft `--record` -> track, submission always manual --
ADR-0058), and a real drift was found and fixed while verifying
`docs/protocol/README.md`'s subcommand table rather than assuming it
was current: its own summary line had miscounted 38 where the table
itself always correctly listed 39 (now 41, after `job-application
record`/`list`).

This whole real feature set (search/draft/track) plus the real M7
task-planning implementation and the "7 real decisions" pass was
tagged `v0.8.0`, 2026-09-08, a real, direct user decision -- see
`CHANGELOG.md`'s own `[0.8.0]` entry and the tag's own real, annotated
message (`git show v0.8.0`) for the full account, including the five
real, standing limits it names plainly.

## 14. ~~Browser/fs/calendar CLI completeness, voice grammar expansion, e2e test, v0.9.0 tag~~ -- RESOLVED/BUILT 2026-09-08

**Resolved/built**: three real, sequential prompts closed out the last
known CLI/voice completeness gaps. `jarvis browser
open/screenshot/inspect-dom/close` wired the four already-real
`browser.*` capabilities to the CLI for the first time. Glassdoor and
Google were both investigated live as new job-search-site candidates
and both rejected on the same robots.txt/ToS grounds that already
ruled out LinkedIn/Indeed; `jarvis find-careers-page "<company>"`
(`job_search.find_careers_page`) was added instead, opening a real
DuckDuckGo "<company> careers" search in the user's own browser.
`fs.find`/`fs.search_content`/`fs.recent` (`jarvis fs
find/search-content/recent`) added real, recursive, scope-bounded
local-file search, with a real, adversarially-proven re-validation
step against every raw `rglob` result (a `..`-bearing pattern or a
real symlink can otherwise escape `allowed_root`). The one remaining
real gap in desktop/communications CLI wiring
(`communications.list_calendar_events`) was closed with `jarvis
calendar list-events`. Four new two-word voice commands (`find files`,
`search files`, `recent files`, `careers page`) were added, each
proven not to bypass its own real tier floor. One real, hermetic,
non-skip-gated end-to-end test now proves `fs.search_content ->
job_search.open_results -> job_assistance.draft ->
job_application.record/list` compose correctly with real data flowing
across all four capability boundaries.

Tagged `v0.9.0`, 2026-09-08, a real, direct user decision (the
original request, "tag M3 and cut v0.7.1," was found stale against
real git state -- M3 was already `v0.7.0`, and `v0.9.0` was the
correct next sequential slot for this completed work). Immediately
after, a real documentation-consistency audit found and fixed four
real drifts: `pyproject.toml`'s `version` field was still `"0.6.0"` (a
real functional bug -- `jarvis --version` was reporting it directly);
`README.md`'s status paragraph and capability count (40) were both
stale; `CLAUDE.md`'s own opening line and "Current Status" section had
never been updated for M6/`v0.6.0` or either of `v0.8.0`/`v0.9.0`. See
`CHANGELOG.md`'s own `[0.9.0]` entry and the tag's own real, annotated
message (`git show v0.9.0`) for the full account, including the four
real, standing limits it names plainly.

## 15. ~~Typed project-goal workflow (`jarvis project start`/`status`)~~ -- RESOLVED/BUILT 2026-09-08

**Resolved/built**: closes the original charter's "remember my
projects... continue yesterday's project" gap at the *workflow*
level -- distinct from `fs.recent`'s file-level support, which already
existed and covers a different real need (finding recently-touched
files on disk, not tracking a project goal's own attempt history).
`jarvis project start "<goal>"` is a thin, real composition wrapping
the already-real, already-Accepted `planning.run_plan` (ADR-0062)
completely unmodified -- no new planning/execution engine -- plus a
real, structured `memory.write` status record on a granted, attempted
plan, mirroring `job-application record`'s own "structured value on
top of unmodified memory" convention exactly (item 12). `jarvis
project status "<goal>"` retrieves the most recent matching record via
`memory.retrieve`, unmodified. Neither reuses a `Decision`-shaped
return for every real case: `PlanningError`/`PlanValidationError`
still propagate exactly as `jarvis plan run` already does, with the
added, real side effect that the failure reason is now durably
recorded first.

**A real, load-bearing finding, investigated before building, not
assumed** (see `kernel/project.py`'s own module docstring for the full
account): the working prompt that requested this assumed "stuck"
already meant "a `Tier.CONFIRM` step blocks mid-plan awaiting the
user." That signal cannot occur in the real, current code --
`application/planning/executor.py` restricts `planning.run_plan` to
`Tier.ALLOW`-only steps (narrower than ADR-0062's own stated ceiling,
a deliberate, already-documented v1 restriction), so any step above
`ALLOW` fails the whole plan's own pre-flight validation before any
step runs at all, rather than pausing one step for confirmation.
"Stuck" was redefined, by the user's own direct choice, to reuse the
real, reachable signals instead (`PlanningError`/`PlanValidationError`,
plus a defensively-handled but not-currently-reachable denied-step
case) -- not the assumed, nonexistent mid-plan-pause signal.

**A real, plainly-stated limit, not rounded up to "done"**:
"fully autonomous project completion" is not real for any plan
containing a `Tier.CONFIRM`-or-above step -- today's `Tier.ALLOW`-only
v1 ceiling means such a plan simply cannot be proposed and validated
at all, so `project start` fails closed (a real "stuck" status,
honestly reported) rather than silently completing part of the work.
Extending the planner past `Tier.ALLOW` was already investigated and
explicitly deferred (item 8) -- this item does not reopen that
decision. No retry or replan was added either, matching the
already-accepted 2026-09-07 decision
(`docs/architecture/planning-retry-replan-scoping-notes.md`) not to
build either mechanism yet.

## 16. ~~Persistent Task/TaskStore (`jarvis task create/run/status/list`)~~ -- RESOLVED/BUILT 2026-09-09

**Resolved/built, WP-107, a real, direct user decision (2026-09-09,
"Fold project.py into tasks.py, start WP-107")**: a real, general Task
system, `jarvis.kernel.tasks`, built on two new real memory
primitives -- `MemoryWritePort.update_value()` (mutate an existing
record's value in place) and `RetrievalPort.get_by_identifier()` (a
real, exact, O(1) lookup by key, not the broad-recall-then-filter
approximation `job-application list`/`project status` both still use
for a *list*). Investigated before building: `SqliteMemoryAdapter.pin()`
already ran a real `UPDATE ... WHERE identifier = ?`, so the storage
engine already supported in-place mutation -- only the public
port/composition surface for updating a record's own *value* was
missing, no new storage engine, no schema break.

**Deliberately split into `authorize_and_create_task`/
`authorize_and_run_task`, not one combined function**: not because
today's synchronous CLI needs the split, but so a later
background-execution UI layer (already scoped in a separate UI
architecture proposal) can return a real task id before a plan
finishes running, without a breaking rework of this module's own
public shape. `authorize_and_get_task`/`authorize_and_list_tasks`
round out the lifecycle. Manually smoke-tested end to end against a
real local Ollama server, which genuinely hallucinated an invalid
capability id mid-test -- a live `PlanningError`, correctly caught,
correctly transitioned the task to `"failed"` with the real reason,
correctly re-raised, correctly retrieved afterward by both `jarvis
task status` and `jarvis task list`.

**`jarvis.kernel.project` folded in, per the user's own explicit
choice (Option B from a prior design pass, not decided unilaterally)**:
`jarvis project start`/`jarvis project status` keep their own exact,
already-tested, already-live-verified public contract byte-for-byte
unchanged (same `Decision` semantics -- `planning.run_plan`'s own
outer gate, never the task-record write's; same `"completed"`/
`"stuck"` vocabulary; same "denied outer gate writes nothing" rule) --
but now delegate their own real writes to `tasks.py`'s shared helpers,
sharing the same `"kind": "task"` storage marker rather than a
separate `"project_goal"` one. **One real, stated vocabulary seam left
open, not hidden**: `tasks.py`'s own two-phase functions write
`"failed"` for the identical real situation `project.py` still writes
`"stuck"` for (preserving its own unchanged public contract) -- so
`jarvis task list` will show a mix of both words for what is,
underneath, the same real outcome, depending on which entry point
created the task. Not unified here, since doing so would mean
changing `project.py`'s own public `state` value, exactly the breaking
change the fold was constrained not to make.

**Real, named states not yet reachable, stated honestly**:
`"waiting_approval"` and `"cancelled"` exist in `VALID_TASK_STATUSES`
for a future planner extension/cancel verb, neither built yet -- see
`kernel/tasks.py`'s own module docstring. A cross-check with the
running "who else needs `memory.get`/`memory.update`" question: no
other existing capability's own classification needed to change; both
are additive.

## Maintaining this index

Add a new numbered entry here whenever a fresh pass surfaces a real,
undecided item spanning more than its own single work package's scope.
Remove or mark resolved only after the real decision is recorded in
the item's own source doc (an ADR's own Status line, a ROADMAP.md
update, etc.) -- never resolve an entry here first.
