# ADR-0059: Does ADR-0057's `Tier.CONFIRM` for email-send/attended-calendar-event satisfy the charter's own "manual confirmation through the desktop interface" requirement?

## Status

Proposed. This ADR does not choose an option — it names a real,
evidenced gap and lays out three concrete resolutions for the user to
choose directly, the same way ADR-0058's own most consequential
question ("is 'no auto-apply' structural or a policy-tier gate?") was
routed to the user rather than resolved remotely. **Do not accept
without the user's own direct choice among the options below** (or a
different option they name instead).

## Date

2026-09-03

## Source

Direct user request: "does ADR-0057's Tier.CONFIRM for email/calendar
actually satisfy the project's own charter?" — prompted by
`job_assistance.draft`'s own WP-84 test suite proving `Tier.CONFIRM`
is remote-satisfiable, and the project's original charter (the system's
own founding description, not currently quoted verbatim anywhere in
this repo's committed docs) explicitly naming "sending emails" among
actions that "must never be executed through voice commands alone"
and must "always require explicit manual confirmation through the
desktop interface."

## Context

**Part 1 — is `Tier.CONFIRM` remote-satisfiable for these two
capabilities specifically? Yes, confirmed directly in code, not
assumed.** `domain/policy.py::evaluate()`:

```python
elif tier == Tier.CONFIRM:
    granted = context.physical_confirmation_available or context.remote_confirmation_available
    if not granted:
        reasons |= DecisionReason.NO_REMOTE_CONFIRMATION
elif tier == Tier.ALLOW:
    granted = True
```

Contrast `Tier.MANUAL_ONLY`, three lines above, which deliberately
never reads `remote_confirmation_available` at all, even when `True`
— per the code's own comment, "voice/remote confirmation is a
convenience filter, never an authorization boundary." `Effect.EGRESS_SENSITIVE`
(what `authorize_and_send_email`/`authorize_and_create_calendar_event`
declare for every non-`SECRET` invocation, per `application/communications/classification.py`)
floors at `Tier.CONFIRM`, not `Tier.MANUAL_ONLY` — confirmed against
`domain/capability.py`'s own `_EFFECT_TIER_FLOOR` dict. This is not
theoretical: `tests/property/test_communications_writer.py`'s own
`test_non_secret_email_bodies_are_never_denied_by_send_alone` and
`test_non_secret_attendee_bearing_summary_floors_at_confirm` both
assert `expected_granted = physical_confirmation_available or remote_confirmation_available`
directly against the real `EmailSendAuthorizer`/`CalendarEventAuthorizer`
— written and passing before this ADR was drafted, proving the
behavior this ADR is now questioning was already deliberately built
and tested this way.

**This is live today, not hypothetical.** `jarvis send-email ...
--remote-confirmation-available` (with no `--physical-confirmation-available`)
already authorizes a real SMTP send, via the real CLI wiring merged
2026-09-03 (WP-79 onward). `ManualConfirmationAdapter`
(`adapters/confirmation.py`) makes the gap sharper still: both
booleans are self-declared CLI flags with zero real presence/hardware
verification behind them today — "Real presence/hardware detection is
future work," per that adapter's own docstring. "Remote confirmation"
currently means nothing more than a caller typing one CLI flag.

**Part 2 — did ADR-0057 or `m6a-communications.md` ever check this
reuse against the charter's own explicit language for email
specifically?** No. Direct search of both documents for
`physical`/`MANUAL`/`desktop`/`charter` finds exactly one relevant
passage, in ADR-0057's own Consequences section, and it treats the
question as speculative future policy rather than a present
requirement:

> "reusing one shared pair of effects means a future policy change
> cannot, without a new ADR reopening this one, treat 'content sent to
> a cloud AI provider' and 'content emailed to a real person' as
> independently tunable risks... if that distinction ever becomes
> real, necessary policy (e.g., a future decision that email should
> require `MANUAL_ONLY` while cloud-provider egress stays `CONFIRM`),
> it would need its own new effect at that point."

ADR-0057 named this exact possibility and deferred it as an "if" —
without ever checking it against the charter's own already-existing,
already-decided treatment of "sending emails" as a named example
requiring manual, desktop confirmation. The reasoning it did do (email
genuinely leaves the machine, reaching a real external party, the same
condition `EGRESS_SENSITIVE`/`EGRESS_SECRET` exist to express) is
sound for the `SECRET`/`DENY` half — an email can never carry a
`SECRET` value, matching cloud-provider egress's own zero-tolerance —
but that analogy was never independently re-checked for the
`CONFIRM`-tier, remote-satisfiability question specifically.

**`Effect.EGRESS_SENSITIVE` was calibrated for a different, narrower
risk than "a real email reaching a real person."** ADR-0038's own
Context: "M2's `ReasoningPort` adapters... the first capabilities in
this repo whose whole purpose is sending data to a cloud provider" —
a cloud AI model seeing text, not a real, external human receiving a
real, unrecallable email or calendar invite. ADR-0057 reused
`EGRESS_SENSITIVE`'s existing `CONFIRM` floor by analogy to that
narrower original purpose, not by independently re-deriving what floor
email-send itself deserves.

**ADR-0019 ("Destructive/irreversible/credential actions always
require `MANUAL_ONLY`") is this codebase's own real, existing
codification of part of the same charter principle — but its own
Decision is scoped purely by `Effect` membership** (`DESTRUCTIVE`,
`IRREVERSIBLE`, `CREDENTIAL`), and `Effect.EGRESS_SENSITIVE` is not a
member of that set. Two of the charter's own four named examples map
cleanly onto this existing floor already ("deleting files" →
`DESTRUCTIVE`/`IRREVERSIBLE`; "changing passwords" → `CREDENTIAL`); a
third ("submitting applications") was independently, directly resolved
by the user as M6b's own *structural* boundary (ADR-0058) — stronger
than `MANUAL_ONLY`, not weaker. The fourth, "sending emails," is the
one the charter names explicitly by name, and it is the one this
codebase currently classifies at `Tier.CONFIRM`, remote-satisfiable.

## Decision

**Undecided — deliberately left to the user, not resolved remotely,
matching this project's own established precedent for decisions of
this shape** (ADR-0058's own "no auto-apply" boundary was the user's
own direct answer, not inferred). Three real options, laid out without
a preference baked in:

**(a) Give email-send and attendee-bearing calendar-event creation
their own `Tier.MANUAL_ONLY` floor.** Closer to `memory.forget`'s/
`git.force_push`'s own precedent for this codebase's most consequential
real actions. The clean version of this is a genuinely new `Effect`
specific to "content reaching a new external party this codebase does
not already trust" (email-send, attendee-bearing calendar-event
creation only — *not* every `EGRESS_SENSITIVE` caller), floored at
`Tier.MANUAL_ONLY`, leaving `EGRESS_SENSITIVE`'s own existing `CONFIRM`
floor untouched for its original, narrower cloud-provider-egress
purpose. Simply moving `_EFFECT_TIER_FLOOR[Effect.EGRESS_SENSITIVE]`
itself to `MANUAL_ONLY` would also move every M2 cloud-provider-egress
call to `MANUAL_ONLY` too — a much broader, almost certainly
unintended blast radius; ADR-0057's own Consequences section already
named the narrower fix ("it would need its own new effect"), not a
floor change to the existing one.

**(b) A more general mechanism**: introduce a `CONFIRM`-tier variant,
or a new tier between `CONFIRM` and `MANUAL_ONLY`, that requires
physical confirmation specifically for a marked subset of capabilities
without touching every `EGRESS_SENSITIVE` caller. A bigger, more
load-bearing change to `domain/capability.py`'s own four-tier model
(ADR-0006) than (a) — real, but with wider consequences, and would
need its own separate design pass; not sketched further here.

**(c) Confirm the current design is intentional and already
sufficient.** The charter's own "manual confirmation through the
desktop interface" language could be read as already satisfied by the
existing `CONFIRM` floor, on the theory that a real, future
`ConfirmationPort` implementation's own "remote confirmation" channel
(e.g. a tappable desktop notification) would itself run through "the
desktop interface," satisfying the charter's own language on its own
terms without a new tier. **This reading is plausible but not true
today**: no such real remote-confirmation mechanism exists anywhere in
this codebase yet — `ManualConfirmationAdapter`'s own docstring states
plainly, "Real presence/hardware detection is future work." Choosing
(c) means accepting that gap as it stands today, not that it is
already closed.

No option is chosen here. **Whichever is chosen, no voice grammar for
`send_email`/`create_calendar_event` should be added until this is
resolved** (per the user's own explicit instruction accompanying this
investigation) — voice invocation stacked on a possibly-remote-
confirmable send is exactly the failure mode the charter's own
sentence names.

## Consequences

Whatever is decided binds real, existing code that already ships and
is already CLI-invocable (`jarvis send-email`, `jarvis
create-calendar-event`, merged 2026-09-03) — this is not a
speculative, pre-implementation question the way ADR-0057's own
original draft was answering. If (a) or (b) is chosen,
`EmailSendAuthorizer`/`CalendarEventAuthorizer`
(`application/communications/writer.py`) and the classification
functions in `application/communications/classification.py` both need
real code changes, plus updated property tests replacing the current
"remote alone suffices" assertions in
`tests/property/test_communications_writer.py` with the opposite
claim for the affected paths — `test_non_secret_email_bodies_are_never_denied_by_send_alone`
and `test_non_secret_attendee_bearing_summary_floors_at_confirm` would
both need to change from proving remote-alone-suffices to proving the
opposite. If (c) is chosen, this ADR's own finding should be recorded
as a real, deliberate, reasoned acceptance — not silently dropped —
and a real remote-confirmation mechanism becomes a real, load-bearing
prerequisite that reading depends on, named explicitly rather than
assumed to already exist.

This ADR does not touch ADR-0019's own effect-based `MANUAL_ONLY`
criteria, ADR-0038's own `EGRESS_SECRET`/`DENY` reasoning (unaffected
— a `SECRET`-classified email/invite already denies unconditionally,
regardless of how this question resolves), or M6b's own structural
"no auto-apply" boundary (ADR-0058) — each already correctly
implements its own part of the charter. This ADR's scope is narrowly
the one real gap found: email-send/attendee-bearing-calendar-event-
creation's own `Tier.CONFIRM` floor, specifically.
