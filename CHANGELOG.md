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

Real work merged to `main` since `v0.6.0` was tagged, not yet cut into
a new release tag. Two large, sequential passes: a 10-phase combined
pass, and a 5-mixed-real-tasks pass. Full detail in `CLAUDE.md`'s
"Current Status" and the individual docs under `docs/architecture/`
each phase/task produced.

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
