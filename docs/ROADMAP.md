# JARVIS Roadmap

## End goal

A complete, privacy-first, plugin-based personal AI agent kernel running
locally, handling voice interaction, multi-model reasoning, desktop
control, memory/retrieval, browser/coding assistance, and integrations
(email, calendar, research, Docker, ROS2) — all under the Clean
Architecture, capability-based plugin, multi-tier policy engine, and
hash-chained audit invariants established in M0.

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
| **M2** | Multi-model reasoning layer: a `ReasoningPort` abstraction over multiple trusted providers, no vendor names in `domain`/`application`/`ports` (ADR-0021), an escalation ladder trying deterministic fixes and self-repair before consulting a second provider (ADR-0022), an arbiter that selects one candidate unmodified rather than merging (ADR-0023), a reviewing model that must produce a failing test rather than a verdict (ADR-0024), and zero weight for a provider's own test scoring its own candidate (ADR-0025). | M1. | Not specified in surviving planning material — see `m2-reasoning-layer.md`. | Not specified. | **Not started.** The *principles* above are real and already decided (ADRs 0020–0025, written during M0). A detailed design document, `m2-reasoning-layer.md`, has now been recovered from the original architecture-phase conversation and reconstructed (2026-08-18) — but it is **not yet re-validated** against what M0 actually became; that reconciliation pass is separate, upcoming planning work, not something this recovery did. |
| **M3** | Desktop control: portal + libei, X11 fallback, AT-SPI2. Out-of-process plugin host + `bwrap` sandboxing. | M0, M1. | `DesktopControlPortContract` green on both Wayland and X11; moving plugins out-of-process requires zero plugin changes. | XL, 25–35 ideal-days. | Not started. See `docs/architecture/m3-desktop-control.md` (placeholder — objective/gates only). |
| **M4** | Memory, hybrid retrieval, retrieval eval set. Vision via ScreenCast/PipeWire. | M2, M3. | Retrieval measured against a fixed eval set; brute-force-vs-ANN decision made by benchmark, not preference. | XL, 25–35 ideal-days. | Not started. See `docs/architecture/m4-memory-retrieval.md` (placeholder). |
| **M5** | Browser via CDP. Coding capabilities via LSP + git. Console UI. | M3, M4. | Coding agent passes the M2 escalation ladder end-to-end on a real repo; test files provably write-protected. | XL, 30–40 ideal-days. | Not started. See `docs/architecture/m5-browser-coding.md` (placeholder). |
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
M3 through M6+ below are deliberately left as gate-only stubs, not
speculative designs: writing `m3-desktop-control.md`'s actual port
signatures, package layout, and work-package breakdown today would
mean writing something guaranteed to need the same kind of correction
before M3 ever starts, for a milestone that is not even next.

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
  recovered 2026-08-18 from the original design conversation. Explicitly
  **not yet re-validated** against what M0 actually became — see the
  M2 row above and the document's own status note.
- **System design**: [`docs/architecture/system-design.md`](architecture/system-design.md) —
  reconciliation of the original system-design decisions (plugin ABI,
  event bus, IPC transport, persistence, secrets, D-Bus library choice,
  the confirmation dialog) against real repo state, reconstructed
  2026-08-18.
- **M3**: [`docs/architecture/m3-desktop-control.md`](architecture/m3-desktop-control.md) — placeholder.
- **M4**: [`docs/architecture/m4-memory-retrieval.md`](architecture/m4-memory-retrieval.md) — placeholder.
- **M5**: [`docs/architecture/m5-browser-coding.md`](architecture/m5-browser-coding.md) — placeholder.
- **M6+**: [`docs/architecture/m6-integrations.md`](architecture/m6-integrations.md) — placeholder.
