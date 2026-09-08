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

## 1. M3's own tag

**What's needed**: cut a real `v0.X` git tag for Milestone 3 (desktop
control), which has been code-complete since WP-56 but was
deliberately left untagged while M4/M5/M6 were tagged out of
sequential order around it.

**Already investigated**: nothing to investigate -- this is a pure
action, not a design question. `CLAUDE.md`'s own opening line states
plainly that M3's tag "remains a deliberately separate, later action"
no pass has touched. See `CHANGELOG.md`'s own tagged-release entries
for what M4/M5/M6 shipped around it.

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

## 5. The audit chain's real, open structural gaps -- two of four closed

**Resolved in part**: the user chose option 1 (7 real decisions
prompt, Decision 6) -- restrictive `0o600` file permissions, now
applied unconditionally on every real `save()`. Raises the bar against
casual/other-local-user tampering. **Updated 2026-09-07**: the
timestamp gap is now closed too -- `AuditRecord` gained a real,
additive `written_at` field (ISO-8601, sourced from a real
`ClockPort`, included in the hash so tampering with it alone is
caught exactly like any other field). **Does not close the remaining
two**, stated plainly, not rounded up:

- **Non-atomic writes**: `save()`'s `Path.write_text()` is still not
  atomic -- a process killed mid-write leaves a truncated, invalid
  JSON file. Investigated directly in `docs/threat-model/v0.md`'s own
  "Phase 10 -- 5 smaller tasks" section (10-phase combined pass), still
  open, unrelated to file permissions.
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
  unrelated to file permissions.

**What's still needed**: a real architecture decision on the remaining
two gaps in `JsonFileAuditStorageAdapter`'s own persistence format.
Full investigation, four real candidate fixes for the
whole-file-replacement/no-tamper-evidence gap specifically, and the
real record of Decision 6's own scope, in
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

## Maintaining this index

Add a new numbered entry here whenever a fresh pass surfaces a real,
undecided item spanning more than its own single work package's scope.
Remove or mark resolved only after the real decision is recorded in
the item's own source doc (an ADR's own Status line, a ROADMAP.md
update, etc.) -- never resolve an entry here first.
