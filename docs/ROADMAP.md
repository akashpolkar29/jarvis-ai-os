# JARVIS Roadmap

## End goal

A complete, privacy-first, plugin-based personal AI agent kernel running
locally, handling voice interaction, multi-model reasoning, desktop
control, memory/retrieval, browser/coding assistance, and integrations
(email/calendar via IMAP/CalDAV, research, job assistance) — all under
the Clean Architecture, capability-based plugin, multi-tier policy
engine, and hash-chained audit invariants established in M0. Docker
and ROS2 were both real, named parts of this line's original vision;
both were dropped during M6's own real scoping pass (2026-09-01) —
Docker because M3 already fully satisfies it, ROS2 because no real
product reason for it was ever found — see
`docs/architecture/m6-scoping-notes.md`'s own "Resolved" section.

## Standing principle: always legible

Every action JARVIS takes, across every milestone, should be legible
to Akash in real time — both spoken (reusing M1's existing TTS output)
and visible on-screen (via M5's Console UI, once it exists). This is a
decided product expectation, not a specific UI or output design. What
actually gets spoken vs. shown, and what the on-screen view looks
like, remains deliberately undecided — per this project's own
recovered original design intent that Console UI views are frozen at
the interface level but deliberately not designed further ahead of
real use (see `m2-reasoning-layer.md` section 8: *"You will know what
you want after six months of using the HUD."*). Nothing about this
principle authorizes designing M5's Console UI or M6's integrations
ahead of their own planning passes — it only states that when they are
designed, silent/invisible operation is not an acceptable outcome.

## System at a glance

```
You (voice or text)
   |
   v
Voice interface (M1)  +  Reasoning (M2)
   |    wake word, STT     escalation ladder
   v
Kernel (M0) -- Policy engine (4 tiers: allow -> deny) + Audit log (tamper-evident)
   |    every request passes through here, always
   v
[ Desktop (M3) | Memory (M4) | Browser/code (M5) | Integrations (M6) ]
   |
   v
Response (spoken or shown)
```

The kernel core — M0 through M2: voice, reasoning, policy, audit — is
already real and does not change as new capabilities are added. The
capability domains — M3 through M6 — are what grows outward from that
core, one milestone at a time, without ever touching it.

## Milestone summary

Status pulled from real repo state (git tags, the task tracker, actual
files on disk) as of this document's creation, and kept in sync with
CLAUDE.md's "Current Status" line, which reflects the same state.

| Milestone | Objective | Entry gate | Exit gate | Complexity | Status |
|---|---|---|---|---|---|
| **M0** | Capability-based agent kernel core: ports & adapters layering, four-tier policy engine (ALLOW/CONFIRM/MANUAL_ONLY/DENY), provenance/taint tracking (`Tainted[T]`), hash-chained tamper-evident audit log, two real capabilities (MPRIS music control, scoped file read), CLI entrypoint. | None — foundational. | All 7 gates pass; threat-model v0 documented honestly, including its own gaps. | Not estimated in any surviving planning material. | **Complete.** Tagged `v0.1.0`, then `v0.1.1` (closed an audit-log privacy gap — raw argument values were briefly persisted, contradicting ADR-0027; fixed to digest-only, a breaking one-way change to the chain format). 32 ADRs (`0001`–`0032`). |
| **M1** | Voice interaction: wake-word detection, VAD, STT, speaker-id (audit/UX signal only, never authorization), a genuine physical-keypress GTK4 confirmation dialog closing threat-model Finding 2, TTS — wired end to end via `jarvis listen`, calling the *unmodified* M0 `AuthorizationOrchestrator`. | M0 tagged `v0.1.1`, complete. | All 7 gates pass; Finding 2 closed for voice-triggered invocation; `jarvis listen` runs the full pipeline. | Not estimated in any surviving planning material. | **Code-complete**, tagged `v0.2.0`, all 7 gates pass on `main`'s tip today (CI green on `ubuntu-latest`, both Python 3.12/3.13). **Correction, Track 6 health pass, 2026-09-02**: the exact tagged commit's own real CI run was red at tag time (both matrix jobs failed at `Install dependencies`, a missing PyGObject system-dependency step introduced by WP-24 and not fixed until three days later, `8c1c6cef`) -- see `docs/threat-model/v0.md`'s own new "Milestone 1 additions" note for the full finding; not a functional/gate failure, and `main` has been green on every push since the fix. 5 further ADRs (`0033`–`0037`). **Live, end-to-end pipeline verification is still an open item** (tracker `#19`): wake-word triggering and the confirmation dialog are each separately verified on real hardware; a bug isolated to the capture code's own audio path (not the OS/PipeWire layer, confirmed working independently) still blocks a real utterance completing the full loop. Not rounding this up to "done." |
| **M2** | Multi-model reasoning layer: a `ReasoningPort` abstraction over multiple trusted providers, no vendor names in `domain`/`application`/`ports` (ADR-0021), an escalation ladder trying deterministic fixes and self-repair before consulting a second provider (ADR-0022), an arbiter that selects one candidate unmodified rather than merging (ADR-0023), a reviewing model that must produce a failing test rather than a verdict (ADR-0024), and zero weight for a provider's own test scoring its own candidate (ADR-0025). | M1. | All 7 gates pass, including the new `application/reasoning` 100%-branch-coverage gate (ADR-0041). | Not specified. | **Code-complete**, tagged `v0.3.0`. 6 further ADRs (`0038`–`0043`). `docs/threat-model/v0.md` carries a "Milestone 2 additions" section, including a real, explicitly-accepted gap (candidate execution is not sandboxed) and a live-verification tracker mirroring M1's `#19` (local fully verified; cloud providers partially/not verified — real account/API constraints, not code bugs). |
| **M3** | Desktop control: portal + libei, X11 fallback, AT-SPI2. Out-of-process plugin host + `bwrap` sandboxing. Eight apps: Brave, VS Code, Spotify, Terminal, Docker, Git, the Claude desktop app, the ChatGPT desktop app. | M0, M1. | `DesktopControlPortContract` green on both Wayland and X11; moving plugins out-of-process requires zero plugin changes. | XL, 25–35 ideal-days. | **Code-complete** (WP-43 through WP-56), all gates pass — see `docs/architecture/m3-desktop-control.md`, ADR-0044–ADR-0047, and `docs/threat-model/v0.md`'s "Milestone 3 additions"/"Live desktop-control verification"/"Overnight live-reality audit" sections for what was actually built and verified. Real deviations from this row's own original objective, stated plainly rather than rounded up: the mechanism actually used for reading/finding/focusing windows is AT-SPI2 only, not portal+libei (libei's GI binding was found absent during WP-43's spike) — AT-SPI2 is display-server-agnostic, so it was never run against a real X11 session specifically, only this milestone's real Wayland development machine; Terminal's synthetic-typing step does use the RemoteDesktop portal (ADR-0047, WP-56), the one place `libei`'s original objective partly survives, code-complete but its real portal call has deliberately never fired (needs the user physically present); no out-of-process plugin host was built in this pass, so this row's "moving plugins out-of-process requires zero plugin changes" criterion remains untested, not passed. **No longer a blanket unverified gap, updated across several later sessions**: Docker (`list_containers`) and Git (push/branch/commit/force-push) have been exercised for real against a real daemon and a real, network-reachable remote; Brave, VS Code, Spotify (MPRIS), and Terminal's real display have all been exercised for real against live desktop windows — one pass also found and fixed a real bug (`focus()`/`is_focused()`/`is_visible_and_showing()` checked the wrong AT-SPI2 node). Genuinely still open: Terminal's real synthetic keystroke has never fired; the Claude desktop app launches but exposes no AT-SPI2 tree; the ChatGPT desktop app was never installed (no official Linux client exists); `docker run`/`build_image` (DESTRUCTIVE) remain deliberately unexercised. |
| **M4** | Memory, hybrid retrieval, retrieval eval set. | M2, M3. | Retrieval measured against a fixed eval set; brute-force-vs-ANN decision made by benchmark, not preference. | XL, 25–35 ideal-days (not re-estimated after scoping -- see below). | **Code-complete, tagged v0.4.0** (WP-57 through WP-64, plus the WP-65 M4-gap-closure pass), all gates pass — see `docs/architecture/m4-memory-retrieval.md`, ADR-0048–ADR-0054, `docs/architecture/m4-benchmark-results.md`, and `docs/threat-model/v0.md`'s "Milestone 4 additions"/"M4-gap-closure pass" for what was actually built. Built in one unattended overnight pass; ADR-0048–ADR-0053 were accepted directly by the user before the pass began, but **ADR-0054 (ClockPort/IdPort) was accepted unilaterally, mid-implementation, by the pass itself, not by the user** — flagged for the user's own retroactive review, not presented as equivalent to the other six. Real, benchmark-backed decision: brute-force numpy cosine similarity over `sqlite-vec` (real numbers in `m4-benchmark-results.md`); `fastembed`/`BAAI/bge-small-en-v1.5` (ONNX, CPU-only) chosen over a `torch`-based embedding model specifically to avoid an unattended-overnight CUDA/download risk — a real quality trade-off, not a default. **WP-65 (2026-08-31) closed four of the originally-named gaps**: a real GC sweep (`MemoryWritePort.sweep_expired()`, triggered on every granted write); a real "forget X" capability (`authorize_and_forget()`/`MemoryWritePort.forget()`, `Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`, same combination as `git.force_push`); `memory.pin`'s first real caller (`authorize_and_pin()`); and real `jarvis memory write/retrieve/forget/pin` CLI subcommands (correcting an earlier, mistaken "mirrors `docker.*`/`git.*`'s no-CLI precedent" claim — see the threat model's own note). All four kernel-level only, no new voice grammar, per that pass's own fixed scope. Real, explicitly-named gaps still open: ADR-0050's provenance carry-forward rule now has a real consumer (`application/memory/carry_forward.py`, closed 2026-09-02 -- see the threat model's own note) so that gap is closed; the `str`-only memory value limitation was narrowed 2026-09-02 (overnight Track 5 pass -- JSON-serializable non-str values now real, supported memories, no new classification/effect decision needed -- see the threat model's own note); voice-triggered *recall* was closed 2026-09-02 (a real "recall <query>" command -- see the threat model's own note); the full real write/retrieve pipeline was verified live exactly once, manually, never repeated by CI by design. |
| **M5** | Browser via CDP. Coding capabilities via LSP + git. Console UI. Vision via ScreenCast/PipeWire (moved from M4's original objective, decided alongside M4's own scoping pass -- see `m4-memory-retrieval.md`'s "Relationship to M5" section). | M3, M4. | Coding agent passes the M2 escalation ladder end-to-end on a real repo; test files provably write-protected. | XL, 30–40 ideal-days. | **Code-complete, tagged v0.5.0** (WP-67 through WP-75), all gates pass — see `docs/architecture/m5-browser-coding.md`, ADR-0055–ADR-0056, and `docs/threat-model/v0.md`'s "Milestone 5 additions" for what was actually built and verified. Exit gate met for real: `run_coding_task`'s own end-to-end test proves the wrapper retries across two full `Dispatcher.run()` climbs on a real repo with a real failing test and reaches `Verdict.PASSED`; a real, all-or-nothing test proves a patch touching one ordinary and one protected path is rejected wholesale, neither file written. Browser automation (CDP) is real and live-verified (a real headless Brave instance, a real screenshot, a real DOM query, all proven on the development machine); the minimal Console UI mechanism is real, wired into one real action (`browser.open_page`). **Real, explicitly-named gaps, none rounded up to "done"**: LSP-based code intelligence (half of this row's own original objective) was never answered or built, real unresolved scope; `coding.run_task` has no default `dispatcher_factory` and therefore no real caller anywhere in this codebase yet; voice grammar for `coding.run_task` was closed 2026-09-02 (overnight Track 4 pass, still gated by the same outer `Effect.EXECUTE`/`Tier.CONFIRM` and by the still-open no-default-`dispatcher_factory` gap -- see the threat model's own note); `Dispatcher`'s own pre-existing multi-candidate-accumulation gap is contained by a disposable workspace, not resolved at the `Dispatcher` level. **ADR-0055/ADR-0056 are Accepted, but by this session's own judgment acting on the user's own relayed instruction, not the user's own independent reading of the final ADR text** — see the threat model's own note. **Tagged `v0.5.0` 2026-09-01**, out of strict milestone-sequential order, same as M4 (M3 remains untagged). |
| **M6a** | Communications/productivity: email via IMAP (read)/SMTP (send), calendar via CalDAV (vendor-neutral throughout, ADR-0021), research (resolved: no new port, reuses M5's existing `BrowserAutomationPort` unmodified). | M5. | Per-plugin conformance to the M0 capability/policy/audit model. | Not specified. | **Code-complete, both read and write halves (WP-76 through WP-80 for reads, WP-79 onward for writes, all 2026-09-03), all gates pass.** `docs/architecture/m6a-communications.md` (2026-09-01) is the real design; ADR-0057 (email-send/attended-calendar-event classification) is **Accepted (2026-09-03, directly by the user, in conversation, after direct review of the ADR's own full text)**. `EmailPort.send_message`/`CalendarPort.create_event` are now real implementations: `smtplib`-backed sending (`ImapEmailAdapter`) and `caldav`'s `Calendar.add_event`-backed creation (`CalDavCalendarAdapter`), both gated by real, dynamic-effect authorizers (`EmailSendAuthorizer`/`CalendarEventAuthorizer`, `application/communications/writer.py`) built on a real classification function (`application/communications/classification.py::egress_effect_for`/`calendar_effect_for`) — a `Classification.SECRET` body/attendee-bearing summary is denied unconditionally, proven by real property tests (including the "all-or-nothing, no partial send across multiple recipients" property ADR-0057's own amendment required), even with `physical_confirmation_available=True`. The structural meta-test that once proved no send/create code path existed (`tests/meta/test_communications_no_send_or_create.py`) has been retired -- its invariant is now intentionally superseded, not left stale. **`communications.list_email`/`communications.read_email`/`communications.list_calendar_events`** remain real, invocable, `Effect.EGRESS_LOCAL`/`Tier.ALLOW` capabilities — `ports/email.py`/`ports/calendar.py`, `kernel/communications.py` (now also home to `authorize_and_send_email`/`authorize_and_create_calendar_event`, dynamic-effect, not statically registered, mirroring `memory.write`'s own precedent). Real, adversary-influenced content is tainted per-item at the point it enters this codebase, mirroring `browser.screenshot`'s own precedent; outgoing content sent by `authorize_and_send_email`/`authorize_and_create_calendar_event` is wrapped `Tainted(value, Provenance.user())`, matching `authorize_and_remember`'s own identical trust-boundary caveat. `email_port`/`calendar_port` have no default (mirror `job_assistance.draft`'s own `providers` precedent) — real per-deployment IMAP/CalDAV configuration is not this module's decision. **`jarvis send-email` (2026-09-03) is the first real caller** — a flat, top-level CLI subcommand (`cli/main.py`), constructing a real `ImapEmailAdapter` from new, required `--imap-host`/`--smtp-host`/`--username`/`--password-reference` flags (no default, per-deployment config, mirroring `listen`'s own `Gtk4PhysicalConfirmationAdapter` construction), wrapped in `asyncio.run` since `authorize_and_send_email` is `async`. **Real, explicitly-named gaps**: `authorize_and_create_calendar_event` still has no real caller; the real, live skipif-guarded test against a real mailbox/calendar remains unmet (no real test-account credentials configured anywhere in this environment); the real `caldav`-vs-alternative library evaluation and console-line wiring for any M6a capability remain open. |
| **M6b** | Job assistance: research and drafting only, no auto-apply — **resolved 2026-09-02, directly by the user**: "no auto-apply" is a structural boundary, not a policy-tier gate (see `docs/adr/0058-m6b-no-auto-apply-is-a-structural-boundary-not-a-policy-tier-gate.md`, **Accepted**). | M5. | Per-plugin conformance to the M0 capability/policy/audit model — plus `m6b-job-assistance.md`'s own six real acceptance criteria. | Not specified. | **Code-complete** (WP-82 through WP-85), all gates pass — see `docs/architecture/m6b-job-assistance.md`, ADR-0058, and `docs/threat-model/v0.md`'s "Milestone 6b additions" for what was actually built and verified. The structural meta-test (`tests/meta/test_job_assistance_no_submission.py`) landed first, proven against an empty package, before any real capability code existed — mirroring this project's own "safety-critical piece first" discipline. `job_assistance.draft` reuses M2's existing `UnverifiableTaskHandler` (not `Dispatcher` — checked and rejected, no pass/fail validator exists for prose), one new, minimal `DraftStoragePort`/`LocalDraftStorageAdapter` (with a real, defensive path-traversal-sanitization finding made during implementation, not named in the design doc itself), and no outer `coding.run_task`-style gate (checked and rejected as unnecessary — no per-write inner loop exists here). Research needed no new code at all — checked against M6a's own item-6 resolution, not assumed to match. **A real, conservative implementation default, confirmed by the user directly, in conversation, 2026-09-02, as the real, permanent policy**: `SECRET`-classified drafting input reuses `Effect.MEMORY_WRITE`'s own unconditional-`DENY` floor, no override — this also makes `job_assistance.draft` a dynamic-effect capability, a real deviation from the design doc's original static-capability sketch, forced by implementing the classification function for real. **Real, explicitly-named gaps, none rounded up to "done"**: no real caller (CLI or voice) invokes `authorize_and_draft_document` yet — `providers` has no default, the same real blocker `coding.run_task` has with `dispatcher_factory`; the meta-test's own real, named limits (it cannot inspect provider-generated content for adversarial intent, its identifier ban-list is a fixed set not an exhaustive network-reachability proof, and its scan boundary is M6b's own package path only); console-line wiring closed 2026-09-02 (a granted draft shows a real on-screen line via ConsolePort, mirroring browser.open_page's identical mechanism); which real job-listing source(s) a future research flow would use remains open. **Not tagged** — tagging remains a separate, later action. |

## Rolling-wave planning

Each milestone gets full architecture-level detail only once its
predecessor is complete — not before. This is a deliberate choice, not
a gap: pre-writing implementation-level detail for a distant milestone
has already, concretely, gone stale before it was ever built.

The evidence is in this repo's own history: `docs/architecture/m1-voice-architecture.md`
was drafted before M1 implementation started, and by the time WP-27
(M1's closeout) reached it, several parts no longer matched what had
actually been built — `WakeEvent` needed a field the original pipeline
diagram never anticipated (ADR-0033), the "existing rule-based intent
resolver" the doc assumed M0 had built never actually existed and had
to be written from scratch, two ADR citations pointed at the wrong
numbers, and the whole document still called itself "Draft for
approval" months after being fully implemented and tagged. All of that
was corrected in place (commit `bde285d`) rather than left silently
wrong — but the fact that a *single* milestone's worth of pre-written
detail drifted that much in the time it took to build is exactly why
M5 and M6+ were each deliberately left as gate-only stubs until their
own turn came, not speculative designs written ahead of time — the
same reasoning that kept M3 and M4 stubs through the milestones before
each of them. M3's real design (`m3-desktop-control.md`, written
2026-08-21) was written only once M3 genuinely became the next
milestone, with M2 complete and tagged, not ahead of that point; M4's
real design (`m4-memory-retrieval.md`, written 2026-08-25) followed the
identical pattern once M3 was complete and tagged; M5's real design
(`m5-browser-coding.md`, written 2026-08-31) followed the same pattern
once M4 was complete and tagged, with one real, named difference from
the three before it — drafted from remotely-reasoned working
assumptions rather than confirmed by the user directly in conversation
(see that document's own header, and `docs/threat-model/v0.md`'s
"Milestone 5 additions" for what that meant for ADR-0055/ADR-0056's own
acceptance) — the rolling-wave principle in action a third time, with
that one process difference stated plainly rather than smoothed over.
**M6 followed the same pattern a fourth time, once M5 was tagged**:
real scoping (`m6-scoping-notes.md`, written 2026-09-01) surfaced six
genuine ambiguities in the ROADMAP's own terse M6 objective — the user
answered four directly in conversation (Docker dropped, already
satisfied by M3; ROS2 dropped, no real product reason ever named;
email/calendar scoped to vendor-neutral IMAP/CalDAV; the bundle split
into M6a/M6b rather than staying one milestone) and left two
genuinely open, one per surviving sub-milestone. **M6a's real design**
(`m6a-communications.md`, written the same day, once M6a itself
genuinely became next) resolved its own remaining open question
(research needs no new port) as part of drafting — the identical
"design surfaces the answer to a question scoping only posed"
pattern `m4-memory-retrieval.md`'s own vision/M5-boundary decision
already set. `m6-integrations.md` itself **remains a gate-only stub
for M6b specifically** — that sub-milestone's own central open
question (whether "no auto-apply" is structural or policy-tier) was
deliberately left untouched, matching this project's own charter-level
rule that a decision shaping whether this system can ever submit a
real job application belongs to the user directly, not remote
reasoning — M6b's own real design starts only once the user answers
it.

## Per-milestone documents

- **M0**: [`docs/architecture/m0-architecture.md`](architecture/m0-architecture.md) —
  as-built record, reconstructed 2026-08-18 from recovered fragments of
  the original design conversation and grounded primarily in the real
  repository (source code, the 32 M0-era ADRs, the real import-linter
  contracts). Not a pristine original — see the document's own status
  note.
- **M1**: [`docs/architecture/m1-voice-architecture.md`](architecture/m1-voice-architecture.md) —
  current, corrected against what was actually built as of commit `bde285d`.
- **M2**: [`docs/architecture/m2-reasoning-layer.md`](architecture/m2-reasoning-layer.md) —
  recovered 2026-08-18 from the original design conversation, reconciled
  against real M0 state during the WP-28 planning pass and implemented
  through WP-31–WP-42 (`v0.3.0`). The recovered fragments themselves are
  not rewritten; deviations found along the way are recorded in real
  ADRs (`0038`–`0043`) and in `docs/threat-model/v0.md`'s "Milestone 2
  additions" instead — see the M2 row above.
- **System design**: [`docs/architecture/system-design.md`](architecture/system-design.md) —
  reconciliation of the original system-design decisions (plugin ABI,
  event bus, IPC transport, persistence, secrets, D-Bus library choice,
  the confirmation dialog) against real repo state, reconstructed
  2026-08-18.
- **M3**: [`docs/architecture/m3-desktop-control.md`](architecture/m3-desktop-control.md) —
  real design, written 2026-08-21 against real post-M2 repo state, not
  a reconciliation of recovered material (none was ever found for M3) —
  see the M3 row above and the document's own status note.
- **M4**: [`docs/architecture/m4-memory-retrieval.md`](architecture/m4-memory-retrieval.md) —
  real design, written 2026-08-25 against real post-M3 repo state and
  the user's own answers to `m4-scoping-notes.md`'s five open
  questions, not a reconciliation of recovered material (none exists
  for M4, same as M3) — see the M4 row above and
  `docs/threat-model/v0.md`'s "Milestone 4 additions".
- **M5**: [`docs/architecture/m5-browser-coding.md`](architecture/m5-browser-coding.md) —
  real design, written 2026-08-31 against real post-M4 repo state, not
  a reconciliation of recovered material (none exists for M5, same as
  M3/M4) — but, unlike M3/M4, drafted from remotely-reasoned working
  assumptions rather than the user's own direct answers in conversation
  (see the document's own header) — see the M5 row above and
  `docs/threat-model/v0.md`'s "Milestone 5 additions".
- **M6a**: [`docs/architecture/m6a-communications.md`](architecture/m6a-communications.md) —
  real design, written 2026-09-01 against real post-M5 repo state and
  the user's own direct answers to `m6-scoping-notes.md`'s first four
  questions, resolving that document's own item 6 (research) in the
  process — its classification reasoning was originally worked through
  remotely, like M5's own design doc, but was reviewed and confirmed by
  the user directly on 2026-09-03 (see the document's own header). One
  new ADR, `0057`, **Accepted 2026-09-03**, directly by the user, in
  conversation, after direct review of the ADR's own full text.
- **M6b**: [`docs/architecture/m6b-job-assistance.md`](architecture/m6b-job-assistance.md) —
  code-complete (WP-82 through WP-85); real scoping is done
  ([`docs/architecture/m6-scoping-notes.md`](architecture/m6-scoping-notes.md)),
  but M6b's own central open question (item 5: whether "no auto-apply"
  is a structural boundary or a policy-tier gate) was deliberately left
  untouched by M6a's own real design pass — real design work for M6b
  has not started.
