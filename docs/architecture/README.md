# Architecture

This directory holds the project's architecture documents.

`m0-architecture.md`, `system-design.md`, and `m2-reasoning-layer.md`
were genuinely designed and approved in an original architecture-phase
conversation, but were never actually persisted into this repository —
confirmed absent by a full-tree search on 2026-08-18. As of that date,
all three have been **reconstructed from recovered fragments of that
original conversation and reconciled against the real repository**:
real ADRs (`docs/adr/0001`–`0037`), real source code, and real
import-linter configuration. They are not pristine originals. Each
states plainly, section by section, what was recovered, what matches
real repo state, what was decided but never built, and what has no
corresponding real ADR at all — nothing is smoothed over or silently
assumed correct.

- **`m0-architecture.md`** — as-built record of M0 (complete, tagged
  `v0.1.1`), grounded primarily in the real repository, using recovered
  design-conversation context only where it doesn't contradict what
  was actually built.
- **`system-design.md`** — full reconciliation of the original
  system-design decisions (plugin ABI, event bus, IPC transport,
  persistence, secrets, D-Bus library choice, the confirmation dialog)
  against real repo state, with an explicit old-decision → real-ADR
  (or "no corresponding real ADR") table.
- **`m2-reasoning-layer.md`** — recovered M2 design (summary judgement,
  validation-over-agreement, the cost-model worked example, scope
  deliverables, acceptance criteria). Explicitly **not yet
  re-validated** against what M0 actually became — that reconciliation
  pass is separate, upcoming work, not done as part of recovering this
  document.
- **`m1-voice-architecture.md`** — current, corrected against what was
  actually built as of commit `bde285d`. Unlike M0/M2/system-design,
  this one was drafted close to its own implementation and kept in
  sync, not recovered after the fact.
- **`m3-desktop-control.md`, `m4-memory-retrieval.md`,
  `m5-browser-coding.md`, `m6-integrations.md`** — intentional
  gate-only placeholders (objective, entry/exit gate, complexity, known
  risks only). Per this project's rolling-wave planning principle (see
  `docs/ROADMAP.md`), full architecture-level detail for these is
  written only once each milestone actually starts — not before. Do
  not add ports, adapters, work-package breakdowns, or ADRs to these
  until that milestone begins.

See `docs/ROADMAP.md` for the full milestone table and the rolling-wave
planning rationale.
