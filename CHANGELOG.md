# Changelog

All notable changes to this project are documented here. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
adapted for a pre-1.0, pre-alpha project: version numbers follow the
real git tags in this repository, not a formal SemVer promise about
API stability (none is made yet). Every entry below is drawn directly
from this project's own real, tagged release messages and
`docs/ROADMAP.md` -- nothing here is invented or rounded up beyond
what those real sources state. For the full, unrounded, continuously
updated account of every real gap and finding at each milestone, see
`CLAUDE.md`'s own "Current Status" section and
`docs/threat-model/v0.md` -- this file is a scannable summary, not a
replacement for either.

## [Unreleased]

### Added

- `jarvis ui` (WP-108) -- a real, minimal, local-only (`127.0.0.1`)
  web chat interface, a client of the existing `jarvis do` router
  (WP-104) never a second execution system. Single-threaded by
  deliberate design to avoid a new, concurrent-request version of the
  audit chain's already-documented cross-process race. See
  `docs/architecture/wp108-ui-foundation.md`.
- WP-110: turned `jarvis ui` into a genuinely reliable typed
  conversation -- distinct rendering per real response type
  (task-created, authorization-required, plain response) and a
  small, additive `task_status` field. See
  `docs/architecture/wp110-ui-conversation.md`.
- WP-111: real task progress + event infrastructure -- a minimal,
  in-process event model (`jarvis.domain.events`) plus a synchronous
  `EventBus`, wired into `kernel.tasks`'s two real state-change
  points. `GET /api/tasks/<task_id>` (polling, not SSE/WebSockets --
  the UI server is deliberately single-threaded) lets the browser
  recover real task status after a disconnect. Audit chain and
  authorization both explicitly untouched -- events observe state,
  they do not own or authorize anything. See
  `docs/architecture/wp111-task-events.md`.
- WP-112: a real task-execution trigger from the UI --
  `POST /api/tasks/<task_id>/run` reuses `kernel.tasks.authorize_and_run_task`
  completely unmodified (same outer gates, same per-step
  authorization, ADR-0062, unchanged). Never automatic -- task
  creation and running remain two separate, explicitly-triggered
  actions. The real, current goal is looked up server-side, never
  trusted from the client. See
  `docs/architecture/wp112-task-execution-trigger.md`.
- WP-114: expanded the conversational execution surface -- `fs.find`/
  `fs.search_content`/`fs.recent` (already had voice/typed grammar,
  never wired into the router's own execution boundary) now actually
  execute through `jarvis do`/`jarvis ui`. `communications.list_email`/
  `read_email`/`list_calendar_events` gained real, typed-router-only
  grammar (e.g. "list emails", "read email <id>", "what's on my
  calendar today/tomorrow/this week") plus a real, direct dispatch
  inside `authorize_and_route`, gated on `jarvis ui`'s seven new,
  optional `--email-*`/`--calendar-*` connection flags. No new
  `CapabilityId`/`Effect`/`Tier`; `communications.send_email`/
  `create_calendar_event` remain untouched, still `Tier.MANUAL_ONLY`.
  See `docs/architecture/wp114-conversational-execution-surface.md`.
- WP-116: real, read-only stale-running-task detection -- a task still
  `"running"` more than 30 minutes past its own last `updated_at` (a
  process crash leaves no in-process exception to catch) is now
  surfaced as a warning by `jarvis task status`/`list`, never
  auto-transitioned -- only a human can safely tell a crashed task
  apart from a genuinely slow one. No new `CapabilityId`/`Effect`/
  `Tier`, no ADR. See
  `docs/architecture/stale-running-task-detection.md`.
- WP-117: real task cancellation -- `jarvis task cancel <task_id>`,
  the first code path to ever reach the long-reserved `"cancelled"`
  status. Reuses `authorize_and_get_task`/`update_task_status`
  (`memory.update`, ADR-0063) completely unmodified. Only a `"created"`
  or `"running"` task may be cancelled; a terminal-status task is
  refused with a real reason. Does not interrupt any in-flight
  execution -- there is none to interrupt in this architecture. No new
  `CapabilityId`/`Effect`/`Tier`, no ADR. See
  `docs/architecture/task-cancellation.md`.
- WP-119: a real "Cancel" button and `POST /api/tasks/<task_id>/cancel`
  endpoint in `jarvis ui`, reusing `authorize_and_cancel_task`
  (WP-117) completely unmodified -- the web UI's own counterpart to
  `jarvis task cancel`. An unknown-but-well-formed task id returns a
  real, granted "not found" result, not an HTTP 404. No new
  `CapabilityId`/`Effect`/`Tier`, no ADR. See
  `docs/architecture/wp119-task-cancellation-from-ui.md`.
- WP-120: a real, process-safe background worker, `jarvis task worker`
  -- discovers every "created" task and claims-and-runs each through
  the exact, unmodified `authorize_and_run_task`. A new, real
  compare-and-swap primitive (`MemoryWritePort.compare_and_update_value`)
  protects the "created" -> "running" transition -- initially built on
  SQLite `BEGIN IMMEDIATE`, later replaced with `fcntl.flock()` on a
  dedicated lock file after real CI runs proved `BEGIN IMMEDIATE` alone
  insufficient against the actual root cause (a "running" -> "running"
  CAS re-claim bug, fixed the same day -- see
  `docs/architecture/wp120-background-worker.md`'s own "Four real
  findings" section) -- proven by real `multiprocessing.Process` tests
  that two independent processes can never both execute the same task.
  Foreground by default, no hidden daemonization; `--once` for one
  pass, `--max-passes` for a deterministic, scriptable continuous
  mode. No new task status, no new `CapabilityId`/`Effect`/`Tier`, no
  ADR. See `docs/architecture/wp120-background-worker.md`.
- WP-121: `jarvis task retry <task_id>` -- a real, explicit retry verb
  permitting only a `"failed"` task to be retried (narrower than
  `jarvis task run`'s own existing re-run permissiveness), delegating
  unmodified to `authorize_and_run_task` so it automatically inherits
  WP-120's own process-safe claim protection with zero new locking
  code. Every task record gained a real, additive, backward-compatible
  `"attempts"` execution-history field -- one entry per concluded
  attempt, appended, never replacing an earlier one. No new
  `CapabilityId`/`Effect`/`Tier`, no ADR. See
  `docs/architecture/wp121-task-retry-and-history.md`.
- WP-122: `jarvis task schedule <task_id> --at <iso8601>` -- real,
  deterministic one-time local task scheduling. No new task status --
  one new, additive, backward-compatible `scheduled_at` field;
  scheduling only permits a task currently `"created"` (excluding
  `"failed"`, since scheduling is not a back-door retry). A naive
  timestamp is rejected; the accepted value is canonicalized to UTC.
  The worker's own discovery gained one pure, local due-time filter --
  the real duplicate-execution protection is entirely inherited from
  WP-120's own claim mechanism, proven by a new, real
  `multiprocessing.Process` test racing the worker itself. No
  recurrence, no natural-language scheduling, no UI/voice exposure --
  all explicitly out of scope. No new `CapabilityId`/`Effect`/`Tier`,
  no ADR. See `docs/architecture/wp122-local-task-scheduling.md`.

### Fixed

- WP-118: `authorize_and_run_task` no longer silently resumes an
  already-`"cancelled"` task -- a real gap WP-117 itself opened (before
  it, no task could reach `"cancelled"`, so the missing status check
  was harmless). `jarvis task run <id> <goal>` on a cancelled task now
  refuses, returning `status="cancelled"` with a real reason, never
  attempting the "running" transition or any plan execution. A
  `"completed"`/`"failed"` task remains freely re-runnable by design.
  No new `CapabilityId`/`Effect`/`Tier`, no ADR. See
  `docs/architecture/run-refuses-cancelled-task.md`.

- WP-115: the audit chain's real cross-process lost-write race --
  two independent processes racing to save the same `--chain-path`
  file no longer silently discard either one's own record.
  `JsonFileAuditStorageAdapter.save()` now re-reads the file's current
  content under a real, cross-process `fcntl.flock()` (held only for
  its own critical section) and re-parents the caller's own new
  records onto the disk's current tail via `AuditChain.append()`,
  unmodified, rather than blindly overwriting with a possibly-stale
  in-memory copy. No `AuditStoragePort` contract change, no new
  dependency. Proven by real `multiprocessing.Process` tests. See
  `docs/architecture/audit-chain-process-safety.md`.
- A real `PermissionError` gap in `browser_automation.py`'s process
  liveness check (`_process_is_really_gone()`), surfaced by WP-115's
  own new multiprocessing test suite shifting real PID allocation on
  a CI runner -- `os.kill(pid, 0)` raises `PermissionError`, not
  `ProcessLookupError`, when `pid` has been recycled to an unrelated,
  other-user-owned process after the one this adapter launched
  already exited. Now treated identically to `ProcessLookupError`;
  both `os.killpg()` call sites in the same module widened the same
  way.
- WP-113: a task left stuck at `"running"` permanently when a plan
  step's own real execution raised an exception other than
  `PlanningError`/`PlanValidationError` (e.g. `PathOutsideAllowedScopeError`,
  `GitCommandFailedError`) -- `kernel.tasks.authorize_and_run_task` and
  `kernel.project.authorize_and_start_project` (which had the same gap,
  but left no status record at all instead of a stuck one) both widened
  their exception handling to a deliberate, documented
  `except Exception`, re-raising the identical exception afterward
  while correctly recording `"failed"` first. See
  `docs/architecture/wp113-task-stuck-at-running-fix.md`.
- WP-110: a real message-ordering hazard in `jarvis ui` -- two rapid
  Enter presses (or typing a second message before the first response
  arrived) could fire two concurrent requests whose responses could
  resolve out of order, visually reordering the conversation. Fixed
  with a real re-entry guard.

- `pyproject.toml`'s `version` field, stale at `0.6.0` since four real
  tags ago -- `jarvis --version` was reporting a materially wrong
  version. Bumped to `0.9.0`. A real documentation-consistency audit
  (WP-100) also refreshed `README.md`'s status paragraph and
  capability count, and `CLAUDE.md`'s opening line and "Current
  Status" section, all stale by the same margin.
- Audit chain non-atomic writes (WP-101): `JsonFileAuditStorageAdapter.save()`
  now writes to a temp file and `Path.replace()`s it over the real
  path in one atomic step, closing the "a crash mid-write can leave a
  truncated file" gap named in `docs/OPEN_DECISIONS.md` item 5. Does
  not close that item's one remaining gap, the cross-process race
  between two legitimate writers.

## [0.9.0] - 2026-09-08

Browser/filesystem/calendar CLI completeness, voice grammar expansion,
and a real end-to-end proof -- three real, sequential prompts tagged
together. Full detail in `CLAUDE.md`'s own "Current Status" section.

### Added

- `jarvis browser open/screenshot/inspect-dom/close` -- real CLI entry
  points for the four already-real `browser.*` capabilities.
  `screenshot`/`inspect-dom`/`close` take a real `PageHandle`'s four
  explicit fields as required flags, since every `jarvis` invocation
  is a fresh process with no shared in-memory adapter state.
- `jarvis find-careers-page "<company>"` -- opens a real "<company>
  careers" DuckDuckGo search in the user's own, real, ordinary Brave
  browser. DuckDuckGo, not Google -- Google's own `robots.txt`
  disallows `/search` broadly and its ToS conditions automated access
  on robots.txt compliance, the same real finding that ruled out
  LinkedIn/Indeed; DuckDuckGo's `robots.txt` affirmatively allows the
  query path.
- `jarvis fs find "<pattern>"` / `jarvis fs search-content "<query>"`
  / `jarvis fs recent [--limit N]` -- real, recursive, scope-bounded
  local-file search (`fs.find`/`fs.search_content`/`fs.recent`),
  reusing `fs.list_dir`'s/`fs.read_file`'s existing
  `Effect.EGRESS_LOCAL`/`Tier.ALLOW` classification. Every result is
  re-validated against the existing scope boundary before being
  returned, since `Path.rglob`-based enumeration can otherwise escape
  it via a `..`-containing pattern or a symlink. `fs.search_content`
  has real file-size (1 MB) and file-count (5,000) caps, reported
  honestly via a real `capped` flag/stderr warning.
- `jarvis calendar list-events --start --end --caldav-url --username
  --password-reference` -- the one real, remaining
  `kernel/communications.py` capability
  (`communications.list_calendar_events`) with no CLI entry point,
  found by a direct re-check of every registered
  `browser.py`/`communications.py`/`desktop.py` composition function.
- Voice grammar: `find files <pattern>`, `search files <query>`,
  `recent files`, `careers page <company>` -- four new two-word
  command keywords, all real, already-registered static capabilities.
  Voice never bypasses any real tier floor (proven by real tests for
  both the ALLOW-tier `fs.*` commands and the CONFIRM-tier
  `find_careers_page`).

### Changed

- Nothing -- this tag is additive only.

### Security / real, honest findings

- Two candidate job-search sites (Glassdoor, Google's own job-search
  page) were investigated live and **neither was added** -- both
  failed the same robots.txt/ToS bar that already ruled out
  LinkedIn/Indeed.
- Voice grammar deliberately omits `browser open/screenshot/
  inspect-dom/close` (three of the four need a real `PageHandle`'s
  technical fields recited aloud) and `calendar list-events` (needs a
  pre-configured `calendar_port` plus two spoken ISO-8601 timestamps).

## [0.8.0] - 2026-09-08

A real "job-application automation" milestone, tagged directly by the
user: search (assisted browsing, no scraping) -> draft (a real, local
CV/Cover-Letter folder, template copied verbatim, a real AI-drafted
cover-letter body) -> track (the applied-jobs ledger) -- plus the
real, separate M7 task-planning implementation and a "7 real
decisions" pass resolving several previously-open items. Full detail
in `CLAUDE.md`'s own "Current Status" section.

### Added

- `job_search.open_results` (`jarvis job-search <keywords> --site
  linkedin|indeed`) -- real, assisted browsing only: opens a real
  search-results URL in the user's own browser, never reads or
  scrapes listing content. See
  `docs/architecture/job-search-scoping-notes.md` for the real
  ToS/robots.txt check behind this.
- `job_assistance.prepare_application_folder` (`jarvis
  prepare-application <job title> <company>`) -- creates a real,
  local `<base>/<Month Year>/CV/` and `.../Cover Letter/` folder pair,
  copies the user's own real LaTeX templates verbatim (never
  auto-tailored), and drafts a real, separate cover-letter body
  (`body.tex`) via `job_assistance.draft`, unmodified. No Overleaf
  integration of any kind -- git access is a paid-plan feature and the
  user is on the Free plan.
- `jarvis.kernel.job_application` (`jarvis job-application record
  <company> <role> --status ...` / `jarvis job-application list
  [--status ...]`) -- the applied-jobs ledger. A real, thin
  structured-content convention layered directly on the already-real
  `memory.write`/`memory.retrieve` capabilities (a `"kind":
  "job_application"` marker key inside the stored JSON value), not a
  new capability, port, or adapter. `authorize_and_remember`'s own
  `text: str` parameter was retyped to `value: object` to support
  this -- the domain/adapter/application layers already supported
  structured values; only this one public signature was the real
  bottleneck.
- `prepare-application --record` -- an additive convenience flag: a
  granted folder creation also calls `job_application.record`
  automatically (`status=drafted`, the real folder just created).
  Omitting it leaves behavior exactly as before.
- `planning.run_plan` (`jarvis plan run <goal>`) -- real, invocable
  task planning (ADR-0062): a new layer above `Dispatcher` (never a
  modification to it), every proposed step individually authorized,
  never pre-approved in bulk. `coding.run_task` also gained real,
  opt-in file-context injection (off by default, every existing
  caller's behavior unchanged).
- `communications.list_email`/`read_email` wired into the CLI
  (`jarvis email list` / `jarvis email read <message-id>`) -- both
  already-real, already-tested capabilities had no CLI entry point
  until this pass.
- A real, additive `written_at` field on `AuditRecord` (`ClockPort`
  now threaded through every kernel composition function's own audit
  trail).
- Voice grammar for `plan <goal>` and `search jobs <keywords> on
  linkedin|indeed`, mirroring `kernel/intent.py`'s own established
  keyword-command pattern -- neither bypasses its own real tier floor.

### Changed

- `icalendar-searcher`'s real AGPL code path is now empirically
  avoided (`caldav`'s own `server_expand=True`, verified live against
  a real Radicale server) -- the dependency remains transitively
  present via `uv.lock` but is no longer exercised at runtime.
- The audit chain's own JSON file now gets restrictive `0o600`
  owner-only permissions on every save, including re-tightening an
  already-existing, looser-permissioned file.

### Fixed

- `docs/protocol/README.md`'s own subcommand-count summary line had
  drifted by one (claimed 38 where the table itself always correctly
  listed 39) -- corrected while verifying the table's real, current
  content rather than assuming it was still accurate.

### Decided (no code changed)

- ADR-0061 (memory backup/restore classification): **Accepted**,
  directly by the user, after direct review of its full text.
- `piper-tts` (GPL-3.0-or-later): kept, not switched -- the user's own
  judgment call that GPL's copyleft trigger (distribution) does not
  yet apply to this project's current, personal/private use.
- Two real, structural CLI naming inconsistencies (`memory`'s nested
  subcommand shape; `fs.read_file`'s bare `read`): left as-is -- not
  worth a user-facing, potentially script-breaking rename this deep
  into the project.
- Extending `planning.run_plan` past `Tier.ALLOW`, retry/replan for a
  failed plan step, and dynamic/out-of-tree plugin loading: all three
  real, open scoping questions were reviewed and left as-is for now,
  each recorded with its own real reasoning.

## [0.7.0] - 2026-09-06

**A real, retroactive CHANGELOG fix, found while preparing `v0.8.0`**:
this tag was never given its own entry here, even though it was
created 2026-09-06 -- the section below is exactly what
`[Unreleased]` used to say at the time, only retitled. Two large,
sequential passes shipped in this range: a 10-phase combined pass, and
a 5-mixed-real-tasks pass. This tag's own headline decision, "tag M3
now, with its two real, accepted gaps stated plainly," is recorded in
the real, annotated tag message itself (`git show v0.7.0`), not
duplicated here. Full detail in `CLAUDE.md`'s "Current Status" and the
individual docs under `docs/architecture/` each phase/task produced.

### Added

- `memory.backup`/`memory.restore`/`memory.wipe` capabilities and CLI
  subcommands (`jarvis memory backup/restore/wipe`) -- real,
  SQLite-online-backup-based whole-store copy/replace/wipe. Classified
  in ADR-0061 (**Proposed**, not yet reviewed by the user).
- `audit.history` capability and `jarvis audit-history` CLI command --
  view the real, persisted audit chain's own history (no timestamp
  shown, since none exists in the real record shape).
- `jarvis doctor` -- a new, real self-diagnostics command (Python
  version, `git`/`docker`/`bwrap` presence, GTK4, `libportaudio`,
  GPU/CUDA, local Ollama reachability, audit-chain directory
  writability). Deliberately not a capability -- no action taken, no
  audit record.
- `jarvis --version`, reading the real, installed package version.
- Real content in `jarvis.plugin_api` (previously a docstring only) --
  a narrow, stable re-export of `jarvis.domain`'s capability-authoring
  vocabulary, plus a real, minimal example plugin
  (`docs/plugin-guide/example_plugin.py`) mechanically proven to
  import only from `plugin_api`/stdlib.
- A real, generated Sphinx API reference (`docs/api/`), built from
  existing docstrings, with a CI step confirming it builds.
- A real CycloneDX SBOM (`docs/architecture/sbom.cyclonedx.json`,
  regenerable via `scripts/generate_sbom.sh`).
- Real kernel-path performance benchmarks
  (`poc/wp67_kernel_benchmark.py`,
  `docs/architecture/kernel-performance-benchmarks.md`).
- A real, thorough memory-retrieval quality evaluation
  (`poc/retrieval_quality_eval.py`) -- 84.0% top-1 accuracy, 92.0%
  top-3 recall on a real, deliberately-hard 25-query set.

### Changed

- `README.md`, `docs/protocol/README.md`, and `CONTRIBUTING.md` were
  all significantly stale (some still describing Milestone-0-only
  state) -- rewritten to reflect current, real status.
- `pyproject.toml`'s own `version` field, never once bumped since the
  project's first commit, corrected from `"0.1.0.dev0"` to `"0.6.0"`
  to match the most recent real tag.
- `.github/workflows/ci.yml` now installs `libportaudio2` explicitly
  (previously an undeclared, implicit dependency on the CI runner
  image's own default contents).

### Fixed

- A corrupted `memory.sqlite3` file crashed the CLI/voice loop with a
  raw traceback instead of a clean error (`sqlite3.Error` was missing
  from the broad except tuples in `cli/main.py` and
  `kernel/voice_loop.py`).
- `adapters/calendar.py` silently accepted naive (timezone-less)
  ISO-8601 datetimes, which would create ambiguous "floating time"
  calendar events -- now rejected with a clear error.
- Three `--help` strings leaked internal ADR reference numbers into
  user-facing text.
- `CdpBrowserAutomationAdapter` had never actually been structurally
  proven to satisfy `BrowserAutomationPort` -- its own contract test's
  docstring falsely claimed it was checked elsewhere; it wasn't.
- A reST inline-literal parsing bug in `adapters/embedding.py`'s own
  docstring (broke Sphinx's build).

### Security

- Full-history secrets scan (two independent tools) found no real
  secrets anywhere in this repository or its git history.
- Confirmed, via a new, real end-to-end test, that indirect
  prompt-injection payloads embedded in a coding task description
  cannot manufacture a false "tests passed" result -- verdicts come
  from a real subprocess exit code, never model text.
- License audit found two real, unresolved dependency-license concerns
  for this MIT-licensed project: `piper-tts` (GPL-3.0-or-later,
  imported directly in-process) and `icalendar-searcher`
  (AGPL-3.0-or-later, a real, exercised dependency of the calendar
  adapter). Not resolved -- flagged for the user's own decision. See
  `docs/architecture/secrets-license-sbom-audit-phase9.md`.

## [0.6.0] - 2026-09-04

M6a (communications/productivity) and M6b (job assistance),
code-complete, tagged together.

### Added

- **M6a**: real `EmailPort`/`CalendarPort` (`ImapEmailAdapter` via
  `imaplib`+`smtplib`; `CalDavCalendarAdapter` via `caldav`);
  `communications.list_email`/`read_email`/`list_calendar_events`
  (`Effect.EGRESS_LOCAL`/`Tier.ALLOW`); dynamic-effect
  `authorize_and_send_email`/`authorize_and_create_calendar_event`,
  gated by `EmailSendAuthorizer`/`CalendarEventAuthorizer`. Real CLI
  callers: `jarvis send-email`/`jarvis create-calendar-event`.
- **M6b**: "no auto-apply" resolved as a structural boundary (ADR-0058),
  enforced by a real AST-based meta-test proven against an empty
  package before any capability code existed. `job_assistance.draft`
  reuses M2's `UnverifiableTaskHandler`, plus a new
  `DraftStoragePort`/`LocalDraftStorageAdapter`. Real CLI caller:
  `jarvis draft <task>`.
- Real, local-only default reasoning/coding providers (a locally
  running Ollama server, `qwen2.5:0.5b`, no cloud credential) for
  `coding.run_task`/`job_assistance.draft`, plus real CLI callers
  (`jarvis code`, `jarvis draft`).
- Real file management: `fs.list_dir`/`fs.move_file`/`fs.delete_file`
  join `fs.read_file`. Real CLI callers: `jarvis list-dir`/`move-file`/
  `delete-file`.
- Voice grammar for `send-email`/`create-calendar-event` ("send email"/
  "create event" keywords in `kernel/intent.py`).

### Changed

- ADR-0059: email-send and attended-calendar-event creation corrected
  from the remote-satisfiable `Tier.CONFIRM` to `Tier.MANUAL_ONLY`
  (`Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`) after a real
  charter-conformance gap was found -- the project's own founding
  charter requires manual, physical confirmation for sending emails,
  never voice/remote alone.

### Known gaps at this tag

No real, live-credentialed test against a real mailbox/calendar; no
real cloud-provider default for coding/drafting (deliberate); ADR-0060
(file management) was still Proposed at tag time; calendar start/end
times in voice grammar are matched verbatim, not parsed from natural
language. M3 (desktop control) remains untagged, a deliberate,
separate choice.

## [0.5.0] - 2026-09-01

M5 (browser automation + coding agent + minimal Console UI),
code-complete.

### Added

- Real, live-verified browser automation (`CdpBrowserAutomationAdapter`
  -- a hand-written CDP client over `websockets`, a real headless
  Brave instance, a real captured screenshot, a real DOM query).
- A real, end-to-end-proven coding-agent authorization chain
  (`Effect.CODE_WRITE`/`Effect.PROTECTED_PATH_WRITE`, ADR-0056; a
  disposable, `SandboxPort`-backed workspace per climb, ADR-0055; a
  finite-retry-budget coding-loop wrapper, `run_coding_task`;
  `coding.run_task` as the outer authorization gate).
- A real, minimal Console UI (`ConsolePort`/`GtkConsoleAdapter`, a
  detached GTK4 subprocess per line), wired into `browser.open_page`.

### Known gaps at this tag

`coding.run_task` had no default `dispatcher_factory` yet (closed in
`v0.6.0`); no voice grammar for `coding.run_task` yet; LSP-based code
intelligence -- half of this milestone's own original scope -- was
never built. ADR-0055/ADR-0056 accepted on relayed instruction, not
the user's own independent reading of the final text (a real,
stated distinction from M0-M4's own ADRs).

## [0.4.0] - 2026-08-31

M4 (memory & retrieval), code-complete, plus a same-day gap-closure
pass (WP-65).

### Added

- Real `MemoryWritePort`/`RetrievalPort`/`EmbeddingPort` ports,
  `SqliteMemoryAdapter` (brute-force cosine similarity, a real
  benchmark-backed decision over `sqlite-vec`), `fastembed`/
  `BAAI/bge-small-en-v1.5` embeddings.
- 90-day default retention with explicit pinning (ADR-0051);
  write-time SECRET denial (ADR-0049) and retrieval-time SECRET
  filtering (ADR-0050).
- Real, invocable `memory.write`/`memory.retrieve` capabilities.
- WP-65 gap closure (same day): a real GC sweep
  (`MemoryWritePort.sweep_expired()`), a real "forget" capability,
  `memory.pin`'s first real caller, and real
  `jarvis memory write/retrieve/forget/pin` CLI subcommands.

### Known gaps at this tag

ADR-0054 (`ClockPort`/`IdPort`) was accepted unilaterally, mid-
implementation, by the pass itself, not by the user at the time --
flagged for retroactive review (later ratified directly by the user,
2026-09-04). M3 remains untagged, a deliberate choice this pass did
not touch.

## [0.3.0] - 2026-08-19

M2 (multi-model reasoning layer), code-complete.

### Added

- `ReasoningPort` abstraction over multiple trusted providers, no
  vendor names in `domain`/`application`/`ports` (ADR-0021).
- An escalation ladder trying deterministic fixes and self-repair
  before consulting a second provider (ADR-0022); an arbiter that
  selects one candidate unmodified, never merging (ADR-0023); a
  reviewing model that must produce a failing test, not a verdict
  (ADR-0024); zero weight for a provider's own test scoring its own
  candidate (ADR-0025).
- New ports/adapters: `ReasoningPort` (`FamilyAReasoningAdapter`,
  `FamilyBReasoningAdapter`, `LocalReasoningAdapter`,
  `CassetteRecorder`/`CassettePlayer`), `ValidationPort` (`Build`/
  `Pytest`/`StaticAnalysis`/`RuntimeCheck`/`UserScript` validators),
  `SecretPort`/`SecretServiceAdapter`, `WorkspacePort`/
  `LocalWorkspaceAdapter`.
- The `application/reasoning` 100%-branch-coverage gate (ADR-0041).

### Known gaps at this tag

Candidate execution is not sandboxed (an explicitly accepted gap,
broader than test-file protection, deferred to M5 by design).
Cloud-provider and local-model adapters were code-complete but not yet
live-verified against a real provider.

## [0.2.0] - 2026-08-15

M1 (voice interaction), code-complete.

### Added

- Wake word -> VAD -> STT -> speaker-id (audit-only, never
  authorization) -> intent resolution -> `AuthorizationOrchestrator`
  (unchanged from M0) -> capability executes -> TTS speaks the
  result, wired end to end via `jarvis listen`.
- New ports/adapters: `WakeWordPort`/`OpenWakeWordAdapter`,
  `VadPort`/`SileroVadAdapter`, `SttPort`/`FasterWhisperAdapter`,
  `TtsPort`/`PiperTtsAdapter`, `SpeakerIdPort`/
  `UnverifiedSpeakerIdAdapter`, `PhysicalConfirmationPort`/
  `Gtk4PhysicalConfirmationAdapter`.
- Threat-model Finding 2 (from M0) closed for voice-triggered
  invocation: `MANUAL_ONLY`-eligible actions reached through
  `jarvis listen` require a genuine physical keypress/click, verified
  to reject a simulated/injected one.

### Known gaps at this tag

Full, live, end-to-end voice-loop verification (a real spoken
utterance completing the whole pipeline) remained an open item.

## [0.1.1] - 2026-08-13

A real privacy fix, tagged separately from M0's own completion.

### Fixed

- **Breaking, one-way change**: the audit log now persists only
  sha256 digests of argument values, never raw values -- closing a
  real privacy violation (Gap 1 in the original M0 threat model,
  contradicting ADR-0027). Pre-`v0.1.1` audit chain files cannot be
  loaded, since raw values were never persisted for digest
  recomputation.

## [0.1.0] - 2026-08-11

M0: the foundational capability-based agent kernel core.

### Added

- Ports & adapters layering; a four-tier policy engine
  (`ALLOW`/`CONFIRM`/`MANUAL_ONLY`/`DENY`); provenance/taint tracking
  (`Tainted[T]`); a hash-chained, tamper-evident, persisted audit log;
  a capability registry.
- Two real capabilities: MPRIS music control (`play`/`pause`/`next`/
  `previous`) and scope-checked local file reading (`read`), alongside
  `ping`, the no-op that proved the stack end-to-end first.
- A working `jarvis` CLI entrypoint.

### Known gaps at this tag

Documented honestly in `docs/threat-model/v0.md`, including Gap 1
(raw argument values in the audit log, contradicting ADR-0027 --
fixed one-way in `v0.1.1`).
