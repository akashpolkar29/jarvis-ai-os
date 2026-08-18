# JARVIS — M3: Desktop Control

Placeholder — objective and gates only, per this project's rolling-wave
planning. Full architecture-level design is written when this
milestone actually starts, not before (see docs/ROADMAP.md).

## Objective

Desktop control: portal + libei, X11 fallback, AT-SPI2. Out-of-process
plugin host + `bwrap` sandboxing.

## Entry gate

M0, M1.

## Exit gate

`DesktopControlPortContract` green on both Wayland and X11; moving
plugins out-of-process requires zero plugin changes.

## Complexity

XL, 25–35 ideal-days.

## Known risks

Highest-uncertainty milestone in the project — portal behavior varies
by compositor, the libei Python binding situation is young.

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
