# JARVIS Roadmap

## End goal

A complete, privacy-first, plugin-based personal AI agent kernel running
locally, handling voice interaction, multi-model reasoning, desktop
control, memory/retrieval, browser/coding assistance, and integrations
(email, calendar, research, Docker, ROS2) — all under the Clean
Architecture, capability-based plugin, multi-tier policy engine, and
hash-chained audit invariants established in M0.

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
| **M1** | Voice interaction: wake-word detection, VAD, STT, speaker-id (audit/UX signal only, never authorization), a genuine physical-keypress GTK4 confirmation dialog closing threat-model Finding 2, TTS — wired end to end via `jarvis listen`, calling the *unmodified* M0 `AuthorizationOrchestrator`. | M0 tagged `v0.1.1`, complete. | All 7 gates pass; Finding 2 closed for voice-triggered invocation; `jarvis listen` runs the full pipeline. | Not estimated in any surviving planning material. | **Code-complete**, tagged `v0.2.0`, all 7 gates pass (CI green on `ubuntu-latest`, both Python 3.12/3.13). 5 further ADRs (`0033`–`0037`). **Live, end-to-end pipeline verification is still an open item** (tracker `#19`): wake-word triggering and the confirmation dialog are each separately verified on real hardware; a bug isolated to the capture code's own audio path (not the OS/PipeWire layer, confirmed working independently) still blocks a real utterance completing the full loop. Not rounding this up to "done." |
| **M2** | Multi-model reasoning layer: a `ReasoningPort` abstraction over multiple trusted providers, no vendor names in `domain`/`application`/`ports` (ADR-0021), an escalation ladder trying deterministic fixes and self-repair before consulting a second provider (ADR-0022), an arbiter that selects one candidate unmodified rather than merging (ADR-0023), a reviewing model that must produce a failing test rather than a verdict (ADR-0024), and zero weight for a provider's own test scoring its own candidate (ADR-0025). | M1. | All 7 gates pass, including the new `application/reasoning` 100%-branch-coverage gate (ADR-0041). | Not specified. | **Code-complete**, tagged `v0.3.0`. 6 further ADRs (`0038`–`0043`). `docs/threat-model/v0.md` carries a "Milestone 2 additions" section, including a real, explicitly-accepted gap (candidate execution is not sandboxed) and a live-verification tracker mirroring M1's `#19` (local fully verified; cloud providers partially/not verified — real account/API constraints, not code bugs). |
| **M3** | Desktop control: portal + libei, X11 fallback, AT-SPI2. Out-of-process plugin host + `bwrap` sandboxing. Eight apps: Brave, VS Code, Spotify, Terminal, Docker, Git, the Claude desktop app, the ChatGPT desktop app. | M0, M1. | `DesktopControlPortContract` green on both Wayland and X11; moving plugins out-of-process requires zero plugin changes. | XL, 25–35 ideal-days. | **Code-complete** (WP-43 through WP-56), all gates pass — see `docs/architecture/m3-desktop-control.md`, ADR-0044–ADR-0047, and `docs/threat-model/v0.md`'s "Milestone 3 additions"/"Live desktop-control verification"/"Overnight live-reality audit" sections for what was actually built and verified. Real deviations from this row's own original objective, stated plainly rather than rounded up: the mechanism actually used for reading/finding/focusing windows is AT-SPI2 only, not portal+libei (libei's GI binding was found absent during WP-43's spike) — AT-SPI2 is display-server-agnostic, so it was never run against a real X11 session specifically, only this milestone's real Wayland development machine; Terminal's synthetic-typing step does use the RemoteDesktop portal (ADR-0047, WP-56), the one place `libei`'s original objective partly survives, code-complete but its real portal call has deliberately never fired (needs the user physically present); no out-of-process plugin host was built in this pass, so this row's "moving plugins out-of-process requires zero plugin changes" criterion remains untested, not passed. **No longer a blanket unverified gap, updated across several later sessions**: Docker (`list_containers`) and Git (push/branch/commit/force-push) have been exercised for real against a real daemon and a real, network-reachable remote; Brave, VS Code, Spotify (MPRIS), and Terminal's real display have all been exercised for real against live desktop windows — one pass also found and fixed a real bug (`focus()`/`is_focused()`/`is_visible_and_showing()` checked the wrong AT-SPI2 node). Genuinely still open: Terminal's real synthetic keystroke has never fired; the Claude desktop app launches but exposes no AT-SPI2 tree; the ChatGPT desktop app was never installed (no official Linux client exists); `docker run`/`build_image` (DESTRUCTIVE) remain deliberately unexercised. |
| **M4** | Memory, hybrid retrieval, retrieval eval set. | M2, M3. | Retrieval measured against a fixed eval set; brute-force-vs-ANN decision made by benchmark, not preference. | XL, 25–35 ideal-days (not re-estimated after scoping -- see below). | **Code-complete, tagged v0.4.0** (WP-57 through WP-64, plus the WP-65 M4-gap-closure pass), all gates pass — see `docs/architecture/m4-memory-retrieval.md`, ADR-0048–ADR-0054, `docs/architecture/m4-benchmark-results.md`, and `docs/threat-model/v0.md`'s "Milestone 4 additions"/"M4-gap-closure pass" for what was actually built. Built in one unattended overnight pass; ADR-0048–ADR-0053 were accepted directly by the user before the pass began, but **ADR-0054 (ClockPort/IdPort) was accepted unilaterally, mid-implementation, by the pass itself, not by the user** — flagged for the user's own retroactive review, not presented as equivalent to the other six. Real, benchmark-backed decision: brute-force numpy cosine similarity over `sqlite-vec` (real numbers in `m4-benchmark-results.md`); `fastembed`/`BAAI/bge-small-en-v1.5` (ONNX, CPU-only) chosen over a `torch`-based embedding model specifically to avoid an unattended-overnight CUDA/download risk — a real quality trade-off, not a default. **WP-65 (2026-08-31) closed four of the originally-named gaps**: a real GC sweep (`MemoryWritePort.sweep_expired()`, triggered on every granted write); a real "forget X" capability (`authorize_and_forget()`/`MemoryWritePort.forget()`, `Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`, same combination as `git.force_push`); `memory.pin`'s first real caller (`authorize_and_pin()`); and real `jarvis memory write/retrieve/forget/pin` CLI subcommands (correcting an earlier, mistaken "mirrors `docker.*`/`git.*`'s no-CLI precedent" claim — see the threat model's own note). All four kernel-level only, no new voice grammar, per that pass's own fixed scope. Real, explicitly-named gaps still open: ADR-0050's provenance carry-forward rule has no real consumer yet to exercise it; only `str`-valued memories are supported; voice-triggered *recall* was not built (only "remember `<text>`", per ADR-0053's own explicit commitment); the full real write/retrieve pipeline was verified live exactly once, manually, never repeated by CI by design. |
| **M5** | Browser via CDP. Coding capabilities via LSP + git. Console UI. Vision via ScreenCast/PipeWire (moved from M4's original objective, decided alongside M4's own scoping pass -- see `m4-memory-retrieval.md`'s "Relationship to M5" section). | M3, M4. | Coding agent passes the M2 escalation ladder end-to-end on a real repo; test files provably write-protected. | XL, 30–40 ideal-days. | **Code-complete, tagged v0.5.0** (WP-67 through WP-75), all gates pass — see `docs/architecture/m5-browser-coding.md`, ADR-0055–ADR-0056, and `docs/threat-model/v0.md`'s "Milestone 5 additions" for what was actually built and verified. Exit gate met for real: `run_coding_task`'s own end-to-end test proves the wrapper retries across two full `Dispatcher.run()` climbs on a real repo with a real failing test and reaches `Verdict.PASSED`; a real, all-or-nothing test proves a patch touching one ordinary and one protected path is rejected wholesale, neither file written. Browser automation (CDP) is real and live-verified (a real headless Brave instance, a real screenshot, a real DOM query, all proven on the development machine); the minimal Console UI mechanism is real, wired into one real action (`browser.open_page`). **Real, explicitly-named gaps, none rounded up to "done"**: LSP-based code intelligence (half of this row's own original objective) was never answered or built, real unresolved scope; `coding.run_task` has no default `dispatcher_factory` and therefore no real caller anywhere in this codebase yet; no voice grammar exists for `coding.run_task`; `Dispatcher`'s own pre-existing multi-candidate-accumulation gap is contained by a disposable workspace, not resolved at the `Dispatcher` level. **ADR-0055/ADR-0056 are Accepted, but by this session's own judgment acting on the user's own relayed instruction, not the user's own independent reading of the final ADR text** — see the threat model's own note. **Tagged `v0.5.0` 2026-09-01**, out of strict milestone-sequential order, same as M4 (M3 remains untagged). |
| **M6+** | Email, calendar, research, job assistance (research + drafting only, no auto-apply), Docker, ROS2. | M5. | Per-plugin conformance to the M0 capability/policy/audit model. | Not specified. | Not started. See `docs/architecture/m6-integrations.md` (placeholder). |

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
**M6+ remains a gate-only stub** — no design work has started for it,
matching the same principle exactly.

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
- **M6+**: [`docs/architecture/m6-integrations.md`](architecture/m6-integrations.md) — placeholder.
