# ADR-0057: Email-send and attended calendar events reuse `EGRESS_SENSITIVE`/`EGRESS_SECRET`, not a new `Effect`

## Status

Proposed

**Not yet reviewed by the user in conversation** — drafted from this
pass's own reasoning while away from the machine, the same
"remotely-reasoned working assumption" provenance
`m5-browser-coding.md`'s own ADRs (0055, 0056) had before their own
later, explicit acceptance. Do not mark Accepted without the user's
own direct review of the reasoning below specifically.

## Date

2026-09-01

## Source

M6a real design (`docs/architecture/m6a-communications.md`), itself
built on four scoping answers the user gave directly in conversation
(2026-09-01, `docs/architecture/m6-scoping-notes.md`'s own "Resolved"
section) — none of which decided this ADR's own specific question.

## Context

M6a needs a real `Effect`/`Tier` classification for two real actions
that, unlike everything else this milestone reads, send content to a
party outside the user's own controlled systems: `EmailPort.send_message`
and `CalendarPort.create_event` when the draft carries real attendees.

Two existing effects already float exactly the tiers this needs:
`Effect.EGRESS_SENSITIVE` (`Tier.CONFIRM`) and `Effect.EGRESS_SECRET`
(`Tier.DENY`, unconditional, ADR-0038) — built for cloud-provider
reasoning calls (`application/reasoning/classification.py`'s own
`egress_effect_for`), but not restricted in their own domain-level
definition to that one caller. The real question this ADR answers:
does M6a reuse these two effects directly, or does it need its own
new effect(s), the way `Effect.MEMORY_WRITE` (ADR-0049) and
`Effect.CODE_WRITE`/`Effect.PROTECTED_PATH_WRITE` (ADR-0056) each did
for their own, different write-shaped actions?

**The precedent that makes this a real question, not an obvious
reuse**: ADR-0049 explicitly *rejected* reusing `Effect.EGRESS_SECRET`
for `Classification.SECRET` memory writes, reasoning that "a memory
write never leaves the machine at all — reusing that name here would
make the effect taxonomy actively misleading." Taken uncritically,
that precedent could read as "never reuse an EGRESS effect for
anything that isn't literally the M2 reasoning-provider call" — this
ADR checks that reading against the real facts of email-send/attended-
calendar-events specifically, rather than assuming it.

## Decision

**Reuse `Effect.EGRESS_SENSITIVE`/`Effect.EGRESS_SECRET` directly. Do
not add a new `Effect`.**

ADR-0049's own reasoning for rejecting reuse does not apply here, for
the opposite reason it applied there: a memory write is not an egress
at all (nothing leaves the machine), so `EGRESS_SECRET`'s own name and
meaning would have been wrong regardless of tier. Sending a real email,
or creating a real calendar event with real attendees, **is** exactly
what `EGRESS_SENSITIVE`/`EGRESS_SECRET` already mean: real content,
leaving the machine, reaching a real party who was not already going
to receive it. The tier floors these two effects already carry
(`CONFIRM` for ordinary content, unconditional `DENY` for
`Classification.SECRET`) are exactly the floors this ADR would
otherwise have to invent from scratch for a parallel, new pair of
effects — with no real difference in meaning to justify the
duplication.

A real, per-invocation classification function,
`application/communications/classification.py::egress_effect_for`,
mirrors `application/reasoning/classification.py`'s own function of
the identical name and shape — a deliberately separate function, not
a cross-package import of the M2-scoped one (matching
`application/coding/classification.py`'s own precedent of mirroring
`application/memory/classification.py`'s shape rather than importing
across milestone-scoped packages) — applied to:

- `EmailPort.send_message`'s outgoing body content.
- `CalendarPort.create_event`'s draft summary, only when
  `draft.attendees` is non-empty. An attendee-less event is a real,
  different case (see `m6a-communications.md`'s own reasoning,
  grounded in `git.push`'s already-Accepted `Effect.WRITE_LOCAL`
  precedent for "writes to infrastructure the user already owns") and
  is not classified through this function at all.

## Consequences

**Makes easier**: no new `Effect` member, no new entry in
`_EFFECT_TIER_FLOOR`, no new property test proving a novel effect's
own unconditional-DENY behavior from scratch — `tests/property/test_capability.py`'s
own existing `test_egress_secret_always_denies_unconditionally` already
covers `Effect.EGRESS_SECRET` for every real caller, this one
included, with no new test needed at the `domain/capability.py` level.
Only the classification *function* itself needs its own test (a real,
new one, mirroring `application/reasoning`'s and `application/memory`'s
own required classification-function tests) — see
`m6a-communications.md`'s own acceptance criteria 1–3.

**Makes harder / real, deliberately accepted limitation**: reusing one
shared pair of effects means a future policy change cannot, without a
new ADR reopening this one, treat "content sent to a cloud AI
provider" and "content emailed to a real person" as independently
tunable risks — both currently floor identically. Named here
explicitly, not discovered later: if that distinction ever becomes
real, necessary policy (e.g., a future decision that email should
require `MANUAL_ONLY` while cloud-provider egress stays `CONFIRM`),
it would need its own new effect at that point, the same way this
ADR's own reasoning would apply in reverse.

**Real, deliberately deferred question, not resolved here**: the
classification above is content-based, not recipient-based — see
`m6a-communications.md`'s own "real, deliberately deferred question"
note. A future refinement distinguishing "known, trusted recipient"
from "novel recipient" is real, separate design work this ADR does not
invent speculatively.

**Depends on nothing new being built yet**: this ADR, like ADR-0055/
ADR-0056 before their own implementation passes, describes a real
decision no code yet implements — `EmailPort`/`CalendarPort` and
`application/communications/` do not exist in this codebase as of this
ADR's own drafting. Implementation is real, separate, future work
(`m6a-communications.md`'s own work-package sketch, WP-76 onward), not
bundled into this ADR's own scope.
