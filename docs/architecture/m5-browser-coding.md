# JARVIS — M5: Browser & Coding

Placeholder — objective and gates only, per this project's rolling-wave
planning. Full architecture-level design is written when this
milestone actually starts, not before (see docs/ROADMAP.md).

## Objective

Browser via CDP. Coding capabilities via LSP + git. Console UI.

## Entry gate

M3, M4.

## Exit gate

Coding agent passes the M2 escalation ladder end-to-end on a real
repo; test files provably write-protected.

## Complexity

XL, 30–40 ideal-days.

## Known risks

CDP automation against Brave will break on browser updates, needs an
ongoing maintenance budget, not just a build budget.

## Deliberately deferred, not an oversight

No ports, adapters, package layout, work-package breakdown, or ADRs
exist for this milestone yet. This is not caution for its own sake:
the original architecture-phase conversation reached the same
rolling-wave conclusion independently, before any of M0 was built.
Two recovered fragments apply directly to this milestone
(`m2-reasoning-layer.md` section 8), quoted verbatim:

> "Individual agent capability sets (M5+). Designing the Email Agent's
> capabilities before the plugin ABI has survived three real plugins
> would be designing against an untested interface."

> "Console UI views. Interface frozen; views deliberately not. You
> will know what you want after six months of using the HUD."

Any old-scheme ADR numbers referenced in earlier planning conversations
predate this repo's real ADR numbering and are not carried forward
here — TBD, decided when this milestone starts.

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

M5's eventual design must also satisfy the standing "always legible"
principle in `docs/ROADMAP.md`: every browser or coding action should
be legible to Akash in real time, spoken and shown. That means reusing
M1's TTS — and, for the on-screen half, M5 is not just another
consumer of this principle: the Console UI named in this milestone's
own objective is the mechanism the principle depends on, so this is
where it actually gets built, not inherited from elsewhere. This is a
constraint M5's future design must satisfy, not a decision about what
M5's specific ports, adapters, or Console UI will look like — those
remain genuinely undecided.
