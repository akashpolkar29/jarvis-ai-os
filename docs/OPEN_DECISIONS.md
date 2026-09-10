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
keeping its own exact public contract unchanged; and the
`"stuck"`/`"failed"` task-status terminology unification (item 17,
2026-09-09), closing the one real vocabulary seam item 16 left open;
and a real typed freeform command router (`jarvis do "<text>"`, item
18, 2026-09-09, WP-104), routing deterministically via
`kernel/intent.py`'s own existing grammar first, falling back to
reasoning only when that fails, never executing a capability outside
the existing, small, pre-wired execution boundary; and a real, minimal
local web UI foundation (`jarvis ui`, item 19, 2026-09-09, WP-108), a
client of that same router, never a second execution system, always
local-only and single-threaded by deliberate design; and a real
follow-up turning that UI into a genuinely reliable typed conversation
(item 20, 2026-09-09, WP-110 — renumbered from the originating
prompt's own "WP-109," which a different, real, already-merged work
package already owns), fixing one real message-ordering hazard with
no new router and no new authorization path; and a real, minimal,
in-process task-event model plus EventBus (item 21, 2026-09-10,
WP-111), turning real task-lifecycle transitions into real,
observable events without EventBus ever owning state, executing a
capability, or touching the audit chain; and a real task-execution
trigger from the UI (item 22, 2026-09-10, WP-112), a "Run" button
reusing `authorize_and_run_task` completely unmodified, never
automatic, with the real goal looked up server-side rather than
trusted from the client; and a real fix for the "stuck at running" gap
item 22 itself named (item 23, 2026-09-10, WP-113), widening both real
callers of `authorize_and_run_plan` to a deliberate, documented
`except Exception` so a plan step's own real execution exception
always lands the task/project record at `"failed"` instead of leaving
it stuck (or, for `project.py`, leaving no record at all); and a real
expansion of the conversational execution surface (item 24,
2026-09-10, WP-114) -- `fs.find`/`fs.search_content`/`fs.recent` wired
into the router's own execution boundary, and `communications.list_email`/
`read_email`/`list_calendar_events` given real, typed-router-only
grammar plus a real, direct `await` dispatch (the three are `async`,
`PLAN_STEP_EXECUTORS` is sync-only), gated on `jarvis ui`'s own new,
optional email/calendar connection flags; and the audit chain's
real cross-process lost-write race (item 5, 2026-09-11, WP-115),
closed via a real `fcntl.flock()`-protected re-read-and-merge inside
`save()`, proven by real `multiprocessing.Process` tests -- no
`AuditStoragePort` contract change, no new dependency. All items 1-24
below are resolved, decided, or built -- nothing in this index remains
open as of 2026-09-11 (a real, separate, narrower residual limitation
of item 5's own fix -- a privileged adversary fabricating a wholesale
replacement chain, a genuinely different threat model -- is named in
item 5 itself and in `docs/architecture/audit-log-integrity-scoping-notes.md`,
not tracked as its own numbered item here).

**Standing, accepted limitations** (not bugs -- real, named, deliberate
scope boundaries, none silently dropped): CV templates are always
copied verbatim, never auto-tailored; no Overleaf integration exists;
job-application submission is never automated (ADR-0058); the audit
chain's whole-file-replacement gap (a privileged adversary fabricating
a replacement chain -- a genuinely different threat model from the
now-closed cross-process race) remains open, four real options laid
out, undecided; `piper-tts` (GPL)
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

## 5. ~~The audit chain's real, open structural gaps~~ -- ALL FOUR CLOSED 2026-09-11 (WP-115)

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
failure mid-save.

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
- ~~Cross-process race~~ -- **CLOSED 2026-09-11 (WP-115)**: two
  independent processes racing to save the same `--chain-path` file no
  longer silently discard either one's own record. `save()` now
  re-reads the file's real, current content under a real, cross-process
  `fcntl.flock()`, held only for its own critical section, and
  correctly re-parents each caller's own new records onto the disk's
  *current* tail (via `AuditChain.append()`, completely unmodified)
  rather than blindly overwriting with a possibly-stale in-memory
  copy. No `AuditStoragePort` contract change, no new dependency
  (`fcntl` is Linux stdlib) -- see
  `docs/architecture/audit-chain-process-safety.md` for the full
  account, including the real, necessary semantic change this required
  (`save()` no longer means "overwrite with exactly this chain") and
  what remains a genuinely different, out-of-scope threat model (a
  privileged adversary fabricating a wholesale replacement chain,
  the real, separate "whole-file replacement" gap below).

**What remains, stated precisely, not rounded up**: WP-115 closes the
*lost-update* race between legitimate JARVIS processes -- it is not,
and was never intended to be, a signing/HMAC/external-anchor defense
against a privileged adversary with filesystem write access willing to
fabricate an entire, freshly-self-consistent replacement chain (the
real, separate "whole-file replacement" gap,
`docs/architecture/audit-log-integrity-scoping-notes.md`'s own four
laid-out options, still genuinely undecided -- a different threat
model, not addressed by WP-115 and not claimed to be).

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
separate `"project_goal"` one. ~~**One real, stated vocabulary seam
left open, not hidden**: `tasks.py`'s own two-phase functions write
`"failed"` for the identical real situation `project.py` still writes
`"stuck"` for -- so `jarvis task list` will show a mix of both words
for the same real outcome, depending on which entry point created the
task.~~ **CLOSED, WP-109, 2026-09-09** (direct user decision: "resolve
the stuck vs failed terminology inconsistency before WP-104"): the
canonical, stored status is now `"failed"` everywhere, unconditionally
-- `project.py` no longer writes `"stuck"` to storage at all, and its
own former, near-duplicate derivation copy was deleted in favor of
directly importing `tasks.derive_result_status` (now the one, real,
public, canonical copy). `project.py`'s own public `state`
return value and `jarvis project status`'s own printed text still say
`"stuck"`, translated only at that module's own return/print boundary
-- the real ambiguity `jarvis task list` would otherwise keep showing
is closed; see item 17 below for the full account, including the one
real, explained exception this leaves (`ProjectStatusOutcome.record`'s
own raw stored value is `"failed"`, not translated, since this module
will not fabricate a record claiming something different was stored).

**Real, named states not yet reachable, stated honestly**:
`"waiting_approval"` and `"cancelled"` exist in `VALID_TASK_STATUSES`
for a future planner extension/cancel verb, neither built yet -- see
`kernel/tasks.py`'s own module docstring. A cross-check with the
running "who else needs `memory.get`/`memory.update`" question: no
other existing capability's own classification needed to change; both
are additive.

## 17. ~~`"stuck"` vs `"failed"` task-status terminology~~ -- RESOLVED/BUILT 2026-09-09

**Resolved/built, WP-109, a real, direct user decision ("resolve the
stuck vs failed terminology inconsistency before WP-104")**. Required
investigation performed first, not assumed: every real use of
`"stuck"`/`"failed"`/`VALID_TASK_STATUSES`/status serialization across
`kernel/project.py`, `kernel/tasks.py`, `cli/main.py`, and their own
tests was mapped before any change. Finding: of the three real
status-producing branches, two (`PlanningError`/`PlanValidationError`;
the currently-unreachable `aborted=True` case) were genuine
duplicates -- identical trigger, identical reason text, two separate
string literals and two near-duplicate private derivation functions.
A third (`tasks.authorize_and_run_task`'s own "outer gate denied after
the task record already existed" branch) has no `project.py`
equivalent at all -- a real, new condition the two-phase
create-then-run design introduced, not a naming question, left
untouched.

**The real fix**: the canonical, stored status for "the planner did
not complete successfully" is now `"failed"`, everywhere, for every
real caller -- `project.py`'s own, former, near-duplicate
`_state_for_result` copy was deleted; it now imports `tasks.py`'s own
(renamed, now-public) `derive_result_status` directly. `project.py`'s
own public `ProjectStartOutcome.state` and `jarvis project status`'s
own printed CLI text still say `"stuck"` -- one real, narrow
translation (`_CANONICAL_TO_PROJECT_STATE`) applied only at that
module's own return/print boundary, preserving its already-shipped,
already-tested, already-live-verified contract exactly, per the
user's own explicit instruction. **One real, explained exception, not
hidden**: `ProjectStatusOutcome.record` -- the raw `MemoryRecord`
`authorize_and_get_project_status` returns -- now genuinely contains
`status: "failed"` for a project-created failure, not `"stuck"`.
Translating that too would mean this function fabricating a record
claiming `"stuck"` was literally persisted when it was not; the CLI's
own printed text is translated instead, exactly where a human actually
reads the word.

**Live-verified, not just unit-tested**: a real `jarvis project
start` → `jarvis project status` round trip against a genuine local
Ollama hallucination printed `state: stuck`; `jarvis task list`
reading the identical, same underlying stored record printed
`status=failed` -- the real ambiguity is closed, the CLI's own
existing user-facing text for `project status` is unchanged. No new
ADR -- a pure internal-representation/presentation fix, no new
capability, no authorization-semantics change.

## 18. ~~Typed freeform command router (`jarvis do "<text>"`)~~ -- RESOLVED/BUILT 2026-09-09

**Resolved/built, WP-104, a real, direct user decision**. A router,
not an autonomous agent, per the prompt's own explicit instruction --
it identifies what a typed request is and where it should go; it
never solves a goal itself.

**Stage A (deterministic)** reuses `kernel/intent.py`'s own,
already-existing `resolve_intent()` directly, unmodified -- the
prompt's own explicit instruction not to duplicate command
definitions when an existing source of truth can be safely reused. A
small, bounded normalizer strips a fixed set of filler words ("please"/
"can you"/trailing "?") before calling it; no new command grammar was
invented.

**Stage B (reasoning fallback)**, `application/routing/router.py`,
mirrors `application/planning/planner.py`'s own `generate_plan` shape
exactly: a strict JSON schema out, validated structurally, a named
capability id checked against the real, live `CapabilityRegistry`
before it can be trusted. **Confidence is never model-supplied, as a
structural property, not a policy one**: the schema sent to the model
has no `confidence` field at all, so there is nothing for a model to
inflate to force execution -- `RouteResult.confidence` is a fixed,
real, informational-only constant assigned in code.

**The router never executes a capability directly, at any stage, as a
structural property**: `kernel/router.py`'s `authorize_and_route` only
ever executes a `DETERMINISTIC_COMMAND` route whose capability id is
already one of the (currently four) entries in the existing,
already-wired `PLAN_STEP_EXECUTORS` table, or creates (never runs) a
new task for a `COMPLEX_GOAL` route via WP-107's own
`authorize_and_create_task`. A real, registered capability the
reasoning fallback names but that has no wired executor (e.g.
`git.force_push`) is reported back, never executed -- proven directly
by a real test. No new `CapabilityId` was invented; every real action
this router can ever cause still passes through the existing
authorization choke point unmodified.

**A real, deliberate design correction made during implementation,
not a silent omission**: `resolve_intent()` can report
`AmbiguousJobSearchSite` (a job-search command recognized, but missing
its site clause) as well as genuine `UnrecognizedIntent`. The first
draft escalated both to Stage B uniformly -- caught live, while writing
this work package's own tests, as a real quality regression: Stage A
already has a more precise answer (which exact clause is missing) than
a reasoning call could supply with less information. Fixed so only a
genuine `UnrecognizedIntent` escalates; an `AmbiguousJobSearchSite`
returns its own specific clarifying detail directly, spending no
reasoning call at all.

**New CLI entry point**: `jarvis do "<text>"` -- the one, single,
canonical typed freeform entry point named in the prompt, no
aliases added. See `docs/protocol/README.md`'s own updated subcommand
table.

## 19. ~~UI foundation + local application boundary (`jarvis ui`)~~ -- RESOLVED/BUILT 2026-09-09

**Resolved/built, WP-108, a real, direct user decision**. A real,
minimal local web UI foundation -- a client of the existing
application layer, never a second execution system. Every real
`POST /api/command` request reaches `kernel.router.authorize_and_route`
(WP-104) completely unmodified.

**A real, investigated documentation finding, not silently routed
around**: `jarvis.ipc`'s own docstring claims it "may depend on
... `jarvis.kernel`," the natural-sounding home for a UI-to-kernel
boundary. Checking the real, enforced C1 layered-architecture contract
(`pyproject.toml`) found the opposite is true: layers are ordered
`cli, kernel, ipc, adapters, application, ports, domain, ui`, and
import-linter's own `layers` contract only permits an earlier layer to
import a later one -- `kernel` sits *before* `ipc`, so `ipc`
structurally cannot import it. `git log -- src/jarvis/ipc/` confirms
the package has never had any real content beyond that one stale,
aspirational docstring. Not fixed here (a real, separate decision --
widen C1, or correct the docstring); the server lives in `jarvis.cli`
instead, which already may import `kernel` and is already the
established home for a continuous, foreground process (`_run_listen`'s
own `Gtk4PhysicalConfirmationAdapter`/serve-until-interrupted
precedent).

**Single-threaded by deliberate design**: `http.server.HTTPServer`, not
`ThreadingHTTPServer`. Every real `authorize_and_*` composition
function (including `authorize_and_route`) does its own `chain_path`
load-append-save per call -- safe for the CLI's "one process, one
request" shape, but concurrent HTTP requests inside one long-running
server process racing to load-append-save the same file would
reproduce the already-documented, still-open cross-process race (item
5), now reachable from a single local process. Serializing all request
handling removes that new exposure entirely -- an acceptable trade for
a genuinely single-user, local chat interface.

**Local-only, by construction**: always binds `127.0.0.1`; no
`--host`/bind-address flag exists anywhere, on purpose, proven by a
real test.

**Authorization, unchanged**: a `DETERMINISTIC_COMMAND` route only
actually executes if wired in `PLAN_STEP_EXECUTORS`; a real,
registered-but-unwired capability (e.g. `git.force_push`) is reported
back as `"unwired_capability"`, never invoked. A `COMPLEX_GOAL` route
creates, never runs, a task via `authorize_and_create_task`.
`UiServerConfig.physical_confirmation_available`/
`remote_confirmation_available` apply uniformly to every request for
the server's whole lifetime, set once at launch, defaulting `False`
like every other subcommand -- a real, deliberate choice not to treat
"the request came from localhost" as an implicit confirmation signal,
which would have been a real, silent reinterpretation of ADR-0013's
own physical-presence guarantee.

**Conversation/Task/Memory kept genuinely separate**: no conversation
history is persisted server-side anywhere; the browser's own JS keeps
the visible message list in memory only. No UI message is ever
auto-written to memory; no history lives in `TaskStore`.

**Voice**: the mic button is a real, disabled placeholder only -- no
microphone/wake-word/voice code of any kind was added or touched.

New files: `src/jarvis/cli/ui_server.py`, `src/jarvis/cli/ui_static/index.html`.
New CLI entry point: `jarvis ui [--port] [--chain-path] [--database-path]
[--physical-confirmation-available] [--remote-confirmation-available]`.
No new `CapabilityId`/`Effect`/`Tier`, no ADR. 100% branch coverage on
`ui_server.py`; 27 new server tests (including two real, unmocked
integration tests proving the HTTP boundary genuinely uses the real
router) plus 5 new CLI-wiring tests. See
`docs/architecture/wp108-ui-foundation.md` for the full design and
`docs/protocol/README.md`'s own updated subcommand table.

## 20. ~~UI conversation + typed input end-to-end~~ -- RESOLVED/BUILT 2026-09-09

**Resolved/built, WP-110, a real, direct user decision**. A real,
frontend-focused follow-up to WP-108, turning the existing `jarvis ui`
into a genuinely reliable typed conversation experience.

**A real naming collision, found before writing any code**: the
originating prompt called this "WP-109" -- a real, different,
already-merged work package (task-status terminology unification,
item 17) already owns that number in this repository's own git
history. Labeled WP-110 instead, the next real, sequential, available
number -- the same "real git state wins over a prompt's own requested
label" resolution this project already established for the
`v0.3.0`/`v0.7.1` tag-numbering collisions.

**The one real, load-bearing bug found and fixed**: the old `send()`
only disabled the Send button, not the text input, and its `keydown`
handler had no re-entry guard at all -- two rapid Enters (or typing a
second message before the first response arrived) could fire two
concurrent requests whose responses could resolve out of order,
visually reordering the conversation. Fixed with a real `isSending`
flag checked synchronously at the top of `send()`.

**Everything else was additive, not a rebuild**: a real, removable
"Thinking..." bubble replaces the old separate status line;
`renderResponse()` now distinguishes every real backend `type`
(`task_created` gets a "Task created"/`Task ID:`/`Status:` block,
`denied` gets an "Authorization required" heading, the rest render as
clear plain text); one small, additive backend field
(`task_status`, always `"created"` for a granted task-creation route
-- a real, always-true fact about `authorize_and_create_task`, WP-107,
never invented). Confirmed by direct inspection before writing
anything: empty/whitespace-input rejection and stuck-loading-state
recovery were **already correct** in WP-108's own original code
(`.finally()` already unconditionally re-enabled the UI on any
outcome) -- neither was rebuilt.

**One router only, unchanged**: no `ui_router.py`/`frontend_router.py`/
`browser_intent.py` of any kind exists; the frontend still only calls
`POST /api/command`, which still only calls the exact same,
unmodified `kernel.router.authorize_and_route` (WP-104). Security
(localhost-only, single-threaded), authorization (ADR-0058, ADR-0062,
no localhost-as-physical-confirmation inference), and Conversation/
Task/Memory separation are all unchanged from WP-108.

**Testing**: 3 new backend tests (`tests/unit/test_ui_server.py`) for
the `task_status` field, including a real HTTP round trip. **A real,
stated limitation, not hidden**: this repository has no JS test
framework and no browser-automation dependency capable of simulating
keystrokes/clicks (`ports/browser_automation.py`'s own real port only
reads pages, never drives one). The actual, shipped, unmodified
`<script>` was instead executed live against a minimal, hand-rolled
DOM stub and the real, running server (Node's own built-in `fetch`,
no mocking) -- 16 real checks, all passing, proving the re-entry
guard, the pending-bubble lifecycle, disabled/re-enabled input states,
empty-input rejection, and real-network-failure recovery all work
against the real production code. This verification genuinely
happened but is not part of the repeatable, committed gate suite --
matching this project's own established precedent for GUI-adjacent
code with no automated coverage (`ui/confirm/dialog.py`'s own "needs a
real display" note), stated plainly as a real, standing gap.

See `docs/architecture/wp110-ui-conversation.md` for the full account.

## 21. ~~Task progress + event infrastructure~~ -- RESOLVED/BUILT 2026-09-10

**Resolved/built, WP-111, a real, direct user decision**. A real,
minimal, in-process event model (`jarvis.domain.events`:
`TaskCreated`/`TaskStatusChanged`, deliberately two types, not five --
see that module's own docstring for why) plus a synchronous,
deterministic `EventBus` (subscribe/publish/unsubscribe, no
concurrency, no lock -- a considered choice, not an oversight, since
no real concurrent caller exists anywhere in this codebase today).

**Events are derived from real state changes, never fabricated**:
`kernel.tasks.write_task_record`/`update_task_status` -- the two, and
only two, real places stored task state ever changes -- publish their
own event only after the underlying write/update was actually
granted. Proven directly against the real `authorize_and_create_task`/
`authorize_and_run_task` call chain, never a fake `Task` object.

**Subscriber-failure semantics, a real, explicit decision**: a
subscriber that raises is logged (never silently swallowed) but never
propagates to the publisher and never blocks other subscribers -- the
real state change an event describes already happened and is
unaffected by a subscriber's own bug.

**UI delivery is polling, not SSE, for a structural reason**:
`jarvis.cli.ui_server`'s own `HTTPServer` is deliberately
single-threaded (WP-108) -- a long-lived SSE connection would block
that one thread from handling any other request. `GET /api/tasks/<task_id>`
instead re-reads the real, authoritative task store directly per call
(no `EventBus` involvement), which also solves browser reconnection
for free: a refreshed browser gets the same real, current answer
back regardless of what it missed.

**A real, honest, stated limitation**: `kernel.router.authorize_and_route`
never runs a task (a `COMPLEX_GOAL` route creates, never runs -- WP-104's
own unchanged design), so no real `TaskStatusChanged` event can ever
originate from the router itself today -- only a separate
`jarvis task run` invocation (a different process) can produce one.
The status-recovery endpoint is unaffected by this, since it reads
the real, shared task store, not this server's own in-process event
history.

**Audit chain, authorization, and job-submission boundaries all
explicitly untouched**: no event is ever written to the audit chain
and no audit record is ever derived from one; `EventBus.publish()`
structurally cannot execute a capability, grant authorization, approve
a task, or change a `Tier`; ADR-0058/ADR-0062 were not modified.

New file: `src/jarvis/domain/events.py`. New endpoint:
`GET /api/tasks/<task_id>` (`jarvis.cli.ui_server`). `event_bus` is a
new, optional, default-`None` parameter on
`write_task_record`/`update_task_status`/`authorize_and_create_task`/
`authorize_and_run_task`/`authorize_and_route` -- every existing caller
that never passes one behaves byte-for-byte as before, proven
directly. No new `CapabilityId`/`Effect`/`Tier`, no ADR. 100% coverage
maintained on `domain/events.py`, `kernel/router.py`, and
`cli/ui_server.py`; 29 new tests across three files. Roadmap numbering
checked directly before starting -- WP-111 was genuinely the next
available number, no collision this time. See
`docs/architecture/wp111-task-events.md` for the full design.

## 22. ~~Task-execution trigger from the UI~~ -- RESOLVED/BUILT 2026-09-10

**Resolved/built, WP-112, a real, direct user decision**. Closes the
real gap WP-111 left open: `kernel.router.authorize_and_route`'s own
`COMPLEX_GOAL` handling only ever creates a task, never runs one, so
there was no way, from `jarvis ui` alone, to make a created task
actually execute.

**One new endpoint, zero new authorization logic**: `POST /api/tasks/<task_id>/run`
reuses `kernel.tasks.authorize_and_run_task` completely unmodified --
the exact same function `jarvis task run` already calls, the exact
same outer gates and per-step authorization (ADR-0062), unchanged.
The real, current goal is looked up server-side via
`authorize_and_get_task` first -- the browser never supplies its own
copy, so it cannot request a real plan run for a different goal than
the one the task was actually created for.

**Never automatic**: task creation and task running remain two real,
separately-triggered actions -- a `COMPLEX_GOAL` route still only ever
creates a task; running one requires a second, explicit HTTP request
the frontend only sends on a real user click of a real "Run" button,
mirroring `jarvis task create`/`jarvis task run`'s own established
two-verb separation (WP-107).

**A real, pre-existing limitation found while building this, not
introduced by it, confirmed directly**: `authorize_and_run_task` only
catches `(PlanningError, PlanValidationError)` -- a real, uncaught
exception from *within* a plan step's own execution (e.g.
`PathOutsideAllowedScopeError`) leaves the task's own stored status at
`"running"` permanently. `jarvis task run` (the CLI) has the identical
property today; not fixed here, since `authorize_and_run_task` was
deliberately not modified -- a genuine, separate architectural
decision, not a drive-by fix. Live-verified directly: a real task run
three times against a real hallucinated out-of-scope path was left at
`"running"` each time, each attempt still cleanly reported as a `400`
to the caller (the endpoint's own exception handling works correctly;
the underlying kernel function's own status bookkeeping is the real,
separate gap).

**Frontend "Run" button, disabled after use**: on a granted response
it shows `"Started"` and stays disabled (preventing an easy,
accidental duplicate run, since re-running is not unsafe -- every step
is still individually authorized -- just confusing/wasteful); on any
real failure it re-enables so the user can retry. No progress is
fabricated.

New endpoint: `POST /api/tasks/<task_id>/run` (`jarvis.cli.ui_server`).
No new `CapabilityId`/`Effect`/`Tier`, no ADR. 100% coverage maintained
on `cli/ui_server.py`; 6 new backend tests plus real, live frontend
verification (button click -> real POST -> real response -> real DOM
update, both success and failure paths). Roadmap numbering checked
directly first -- WP-112 was genuinely the next available number. See
`docs/architecture/wp112-task-execution-trigger.md` for the full
account.

## 23. ~~Task left stuck at "running" on an uncaught plan-step exception~~ -- RESOLVED/BUILT 2026-09-10

**Resolved/built, WP-113**. Closes the real, pre-existing limitation
item 22 (WP-112) found and deliberately did not fix: `authorize_and_run_task`'s
own exception handling caught only `(PlanningError, PlanValidationError)`
-- a real exception raised from *within* a plan step's own wrapped
`authorize_and_*` call (e.g. `PathOutsideAllowedScopeError`,
`GitCommandFailedError`, `OSError`, `sqlite3.Error` -- anything a
capability currently wired into `kernel.capability_dispatch.PLAN_STEP_EXECUTORS`
can really raise) propagated all the way out uncaught, leaving the
task's own stored status at `"running"` permanently.

**The fix**: both real callers of `authorize_and_run_plan` -- `kernel.tasks.authorize_and_run_task`
and `kernel.project.authorize_and_start_project` -- widened their own
`except (PlanningError, PlanValidationError)` clause to a deliberate,
documented `except Exception`, each still re-raising the identical,
unmodified exception afterward (the caller sees exactly what it saw
before this fix); only the task/project record's own stored status
changed, from "never updated" to "failed," with the real exception's
own type and message as the reason.

**A second, real, related gap found while investigating, not just the
one item 22 already named**: `kernel.project.authorize_and_start_project`
writes no intermediate "running" record at all (unlike `tasks.py`'s own
create-then-run split), so a step-execution exception there did not
leave a task "stuck" -- it left **no status record whatsoever** for the
goal, a real, silent gap of its own, also closed by the same widening.

**Deliberately broad, not a curated exception list, and why**: only
four capabilities are wired into `PLAN_STEP_EXECUTORS` today
(`fs.read_file`, `fs.list_dir`, `git.status`, `memory.retrieve`), and
their own real exception types were investigated directly (not
guessed) to scope this fix -- but a curated tuple naming only today's
four would silently reintroduce this exact bug the next time
`PLAN_STEP_EXECUTORS` gains a capability with a new exception type.
`except Exception` (never `BaseException` -- `KeyboardInterrupt`/`SystemExit`
still propagate immediately, unaffected) is the deliberate, structural
choice instead, documented plainly in both functions' own docstrings
and inline comments as a considered, named exception to this project's
own general preference for precise, curated exception lists over
blanket catches.

Two new real regression tests (`test_tasks_kernel.py`,
`test_project_kernel.py`), each driving a real, structurally-valid
plan naming the real `fs.read_file` capability against a path outside
its `allowed_root`, proving the real `PathOutsideAllowedScopeError`
still propagates to the caller while the stored record now correctly
shows `"failed"`. No new `CapabilityId`/`Effect`/`Tier`, no ADR --
this is a pure error-handling correctness fix to an already-classified
code path, not a new authorization decision. Roadmap numbering checked
directly first -- WP-113 was genuinely the next available number (the
one `WP-124` reference in `CLAUDE.md` is a proposed implementation-order
range from an unbuilt UI-architecture artifact, not a real, built work
package). See `docs/architecture/wp113-task-stuck-at-running-fix.md`
for the full account.

## 24. ~~Expanding the conversational execution surface~~ -- RESOLVED/BUILT 2026-09-10

**Resolved/built, WP-114**. Closes a real gap a repository audit
found: `fs.find`/`fs.search_content`/`fs.recent` already had
voice/typed grammar (`kernel/intent.py`) but were never wired into
`kernel.capability_dispatch.PLAN_STEP_EXECUTORS`, the router's own real
execution boundary -- typing "find files *.py" was *recognized* but
never *run*. `communications.list_email`/`read_email`/
`list_calendar_events` had no grammar at all.

**The fix**: the three `fs.*` capabilities were added to
`PLAN_STEP_EXECUTORS` directly (no port needed, real safe defaults).
The three `communications.*` reads needed a different mechanism: their
own `authorize_and_*` functions are `async def`, but `PlanStepExecutor`
is sync-only -- wrapping the async call in `asyncio.run()` inside a
sync executor raises `RuntimeError` from inside
`authorize_and_route`'s own already-running event loop (confirmed by a
real failing test before fixing). `kernel.router.authorize_and_route`
now `await`s these three directly, in three new branches, only when
the matching `email_port`/`calendar_port` was supplied to that
specific call.

**New grammar lives in `kernel.router`, deliberately not in the shared
`kernel.intent.resolve_intent()`** -- two real, independent reasons:
(1) these three capabilities need a real, pre-configured port with no
safe default, and `kernel.voice_loop`'s own dispatch has no branch for
them, ending in an unguarded dict lookup that would `KeyError` for a
newly-resolvable voice phrase -- a real regression this work package's
hard boundary (no voice changes) forbids introducing; (2) calendar
"today"/"tomorrow"/"this week" needs a `ClockPort`, and
`resolve_intent()` is deliberately pure/clockless. Confined entirely to
`kernel.router` (never imported by `kernel.voice_loop`), so this
structurally cannot affect voice.

**A real collision found and fixed during implementation**:
`resolve_intent()`'s own pre-existing `"read <path>"` command happily
(mis)resolved `"read email <id>"` to `fs.read_file` with
`path="email <id>"`. Fixed by checking the new grammar *before*
`resolve_intent()`, not as an `UnrecognizedIntent` fallback -- proven
by a dedicated regression test that an ordinary `"read notes.txt"`
still resolves correctly.

`jarvis ui` gained seven new, entirely optional flags
(`--email-imap-host`/`--email-smtp-host`/`--email-username`/
`--email-password-reference`, `--calendar-caldav-url`/
`--calendar-username`/`--calendar-password-reference`) mirroring
`jarvis email list`/`jarvis calendar list-events`'s own existing flag
names exactly -- all-or-nothing per port, no credentials committed
anywhere, the existing keyring-reference mechanism reused unmodified.
Omitting them behaves byte-for-byte as before.

No new `CapabilityId`/`Effect`/`Tier`, no ADR, no second router, no
direct UI-to-capability path. `communications.send_email`/
`create_calendar_event` (the two write capabilities) are completely
untouched -- still dynamic-effect, never registered, never in any
executor table, still `Tier.MANUAL_ONLY` (ADR-0059). The frontend
(`index.html`) needed zero changes -- it already renders `"response"`/
`"unwired_capability"` generically. Roadmap numbering checked directly
first -- WP-114 was genuinely the next available number. See
`docs/architecture/wp114-conversational-execution-surface.md` for the
full account, including the real inspection table (which capabilities
already had what) and every named limitation.

## Maintaining this index

Add a new numbered entry here whenever a fresh pass surfaces a real,
undecided item spanning more than its own single work package's scope.
Remove or mark resolved only after the real decision is recorded in
the item's own source doc (an ADR's own Status line, a ROADMAP.md
update, etc.) -- never resolve an entry here first.
