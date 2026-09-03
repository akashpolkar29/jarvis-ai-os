# ADR-0057: Email-send and attended calendar events reuse `EGRESS_SENSITIVE`/`EGRESS_SECRET`, not a new `Effect`

## Status

Accepted

**Accepted 2026-09-03, directly by the user, in conversation, after
direct review of this document's own full text** — the complete
Decision, Consequences, and Amendment sections below were surfaced to
the user verbatim and accepted as-is, satisfying this project's own
"a relayed decision is not the same as reviewing the document" bar
(the same bar ADR-0058 already satisfied, and the bar ADR-0055/
ADR-0056 still have not). Drafted from this pass's own reasoning while
away from the machine, the same "remotely-reasoned working assumption"
provenance `m5-browser-coding.md`'s own ADRs (0055, 0056) had before
their own acceptance — that provenance is now closed out by this
direct review, not merely noted as an open gap.

**Amended 2026-09-01 (real gap-hunt pass, before any implementation
started, prior to this Acceptance):** four real gaps found by applying
the same adversarial scrutiny ADR-0056's own amendment pass applied to
itself — a missing trust-boundary caveat, an under-specified
multi-recipient send signature, an implicit rather than explicit
classify-then-authorize ordering, and an unnamed future bypass risk
for calendar attendees. None change this ADR's own core Decision
(reuse `Effect.EGRESS_SENSITIVE`/`Effect.EGRESS_SECRET`, no new
effect) — see "Amendment 2026-09-01" under Consequences below for what
each one adds. The user's own acceptance above covers this amended
text, not the pre-amendment original.

**What Acceptance does and does not unblock, stated precisely**: this
ADR's own classification question is now settled — `email_port`/
`calendar_port`'s future `send_message`/`create_event` authorizers may
be built using `Effect.EGRESS_SENSITIVE`/`Effect.EGRESS_SECRET` per
the Decision below. **Implementation itself remains separate, future
work** (`m6a-communications.md`'s own WP-79 onward) — `EmailPort.send_message`/
`CalendarPort.create_event` still unconditionally raise
`NotImplementedError` in every real adapter as of this Acceptance;
this document records a decision, it does not write code.

## Date

2026-09-01 (amended 2026-09-01)

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

## Amendment 2026-09-01 (real gap-hunt pass, before implementation)

Applied the same real skepticism ADR-0056's own amendment pass applied
to itself, before any of WP-76 onward starts, not after. Four real
findings, none changing this ADR's own core Decision:

**1. A real trust-boundary caveat was missing, not just unstated.**
This ADR's own `Effect.EGRESS_SECRET`/`DENY` protection is entirely
dependent on the outgoing content's `Classification` already being
correct by the time `egress_effect_for` sees it — this function
*classifies*, it does not *detect*. Nothing in this mechanism scans an
email body's actual text for something that looks like a leaked API
key; if the `Tainted` value representing the body is constructed with
`Classification.PUBLIC` by whatever real caller builds it (a future
voice/CLI entry point, or an M5 coding-agent-adjacent flow drafting an
email on the user's behalf), a real secret embedded in otherwise
ordinary-looking prose passes straight through at `CONFIRM`, not
`DENY` — this ADR's own unconditional-DENY guarantee is only as strong
as whoever computes that provenance upstream. **This is not a new,
undiscovered risk specific to email — it is the same trust boundary
`kernel/memory.py`'s own `authorize_and_remember` docstring already
names explicitly for memory writes** ("A future caller constructing
this value from a less-trusted or more sensitive source is responsible
for giving it the correct provenance before calling this function --
this function does not, and cannot, second-guess a provenance it did
not compute"). The real gap was this ADR's own silence on it, not a
new architectural hole — fixed by restating the identical caveat here,
explicitly, rather than leaving a reader to assume it. Whichever work
package first builds a real caller of `send_message`/`create_event`
(WP-79 onward) must construct the outgoing content's `Tainted` value
with real, considered classification, the same responsibility every
other dynamic-effect capability in this codebase already carries.

**2. `EmailPort.send_message`'s own `to: str` signature does not
support real multiple recipients, and this ADR never stated what
"all-or-nothing" means for it.** A real email capability needs to
address more than one recipient in the ordinary case (a real cc/to
list), which `to: str` cannot express at all. `m6a-communications.md`
is amended to widen this to `to: tuple[str, ...]`. This does not weaken
this ADR's own classification guarantee — it strengthens the
statement of it: classification here is computed once, over the whole
message's own content, for the entire call, not per-recipient. There
is no code path, by construction, where a `Classification.SECRET` body
sends to some addresses in `to` and not others — the capability
invocation is atomic (one real `send_message` call, one real
`Decision`, one real outcome), so "all-or-nothing" was already
structurally guaranteed by the existing single-invocation shape; it
was simply never stated as an explicit property of this ADR's own
Decision until this amendment.

**3. The classify-then-authorize-then-act ordering was implicit
("mirrors the existing pattern"), not stated as an explicit
requirement of this ADR's own Decision.** Every real dynamic-effect
authorizer this codebase already has
(`MemoryWriteAuthorizer.authorize_write`, `CodeWriteAuthorizer.authorize_write`)
follows the same real shape: classify the content, build the
`CapabilityInvocation` with the resulting `Effect`, call
`AuthorizationOrchestrator.authorize()`, and only if `Decision.granted`
is `True` does the real side effect (`adapter.write`,
`WorkspacePort.apply_patch`) ever run. `m6a-communications.md`'s own
package-layout section said the future `EmailSendAuthorizer`/
`CalendarEventAuthorizer` would mirror this "exactly," which is
correct, but this ADR's own Decision section never said so explicitly
enough to be unambiguous on its own. Stated explicitly now, as a real,
binding requirement of this ADR's own Decision, not merely implied by
analogy: **`egress_effect_for` must be called, and its result used to
build the real `CapabilityInvocation` that `AuthorizationOrchestrator.authorize()`
evaluates, strictly before `EmailPort.send_message`/`CalendarPort.create_event`
is ever invoked against the real adapter — and only if that call's own
`Decision.granted` is `True`.** Whichever work package implements
`kernel/communications.py` (WP-80) must satisfy this literally, the
same way `CodeWriteAuthorizer`'s own real code already does, not just
structurally resemble it.

**4. A real, named future bypass risk: any future `update_event`/
`add_attendees` method must apply the identical attendee
classification this ADR requires for `create_event`, not treat
"adding attendees to an already-existing event" as ordinary
`Effect.WRITE_LOCAL` just because it isn't creation.** This design's
own current `CalendarPort` has no such method — `create_event` is the
only write — so no real bypass exists in what is designed today. But
the risk is real and worth naming now, before it can be built past
unnoticed: a future implementer adding `update_event(uid, draft)` or
`add_attendees(uid, attendees)` without reading this ADR closely could
reasonably assume "updating an existing event" is a lesser action than
"creating one," and classify it `WRITE_LOCAL` by default — silently
reopening the exact "reaches a new external party" gap this ADR exists
to close. Any future work extending `CalendarPort` with an
attendee-affecting write must route through
`application/communications/classification.py::egress_effect_for` the
identical way `create_event` does, or this ADR is being violated in
spirit even while its own literal text is unchanged.
