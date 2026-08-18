# JARVIS — M4: Memory & Retrieval

Placeholder — objective and gates only, per this project's rolling-wave
planning. Full architecture-level design is written when this
milestone actually starts, not before (see docs/ROADMAP.md).

## Objective

Memory, hybrid retrieval, retrieval eval set. Vision via
ScreenCast/PipeWire.

## Entry gate

M2, M3.

## Exit gate

Retrieval measured against a fixed eval set; brute-force-vs-ANN
decision made by benchmark, not preference.

## Complexity

XL, 25–35 ideal-days.

## Known risks

Retrieval quality is empirical and may need several iterations.

## Deliberately deferred, not an oversight

No ports, adapters, package layout, work-package breakdown, or ADRs
exist for this milestone yet. This is not caution for its own sake:
the original architecture-phase conversation reached the same
rolling-wave conclusion independently, before any of M0 was built —
see `m2-reasoning-layer.md` section 8. Any old-scheme ADR numbers
referenced in earlier planning conversations predate this repo's real
ADR numbering and are not carried forward here — TBD, decided when
this milestone starts.

This repo has now twice demonstrated the concrete cost of designing
ahead of real implementation: `m1-voice-architecture.md` needed
post-implementation correction (commit `bde285d`) once real code
diverged from what had been pre-written; and the just-recovered
`system-design.md` found that the original M0-era confirmation-dialog
design specified a separate process, which was never actually built
that way (see `system-design.md` section 9).

What does carry forward regardless of this milestone's undecided
specifics: every future milestone inherits the same kernel invariants
already enforced today — capability-based extension, not agents; every
action gated by the four-tier policy engine; every invocation
audit-logged; the ports-and-adapters dependency rule; no vendor names
leaking into `domain`/`application`/`ports`. Which specific ports or
capabilities this milestone will need is not decided here.

M4's eventual design must also satisfy the standing "always legible"
principle in `docs/ROADMAP.md`: every memory or retrieval action
should be legible to Akash in real time, spoken and shown. That means
reusing M1's TTS and M5's Console UI once they're available to build
against — not inventing new voice or display mechanisms specific to
M4. This is a constraint M4's future design must satisfy, not a
decision about what M4's specific ports, adapters, or UI will look
like — those remain genuinely undecided.
