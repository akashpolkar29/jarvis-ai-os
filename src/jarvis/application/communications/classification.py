"""Classification -> Effect mapping for M6a's send-email/create-calendar-event capabilities.

Kept separate from ``writer.py`` deliberately, mirroring
``jarvis.application.memory.classification``'s own split exactly: this
is the one pure decision a real authorizer orchestrates around. A real,
separate module from
``jarvis.application.reasoning.classification``/``jarvis.application.memory.classification``,
not a cross-package import of either -- matching
``jarvis.application.coding.classification``'s own established
precedent of mirroring shape rather than importing across
milestone-scoped packages.

**ADR-0057's own real Decision (Accepted 2026-09-03, directly by the
user, in conversation, after direct review of the ADR's own full
text)**: email-send and attended-calendar-event creation reuse
``Effect.EGRESS_SECRET`` directly for ``Classification.SECRET`` content
-- no new effect for that half, unconditional ``Tier.DENY``, unaffected
by the amendment below.

**ADR-0059's own real Decision (Accepted 2026-09-03, directly by the
user, in conversation) amends the non-``SECRET`` half**: ADR-0057's
original reasoning reused ``Effect.EGRESS_SENSITIVE`` (``Tier.CONFIRM``,
remote-satisfiable) for that case, by analogy to
``EGRESS_SENSITIVE``/``EGRESS_SECRET``'s own existing precedent -- never
independently checked against the project's own founding charter,
which names "sending emails" explicitly among actions requiring
"manual confirmation through the desktop interface," never voice/remote
alone (see ADR-0059's own Context for the full finding).
``Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`` (``Tier.MANUAL_ONLY``,
never remote-satisfiable -- ``domain/policy.py``'s own ``evaluate()``
deliberately never reads ``remote_confirmation_available`` for this
tier) is the real fix: the identical combination ``git.force_push``/
``memory.forget`` already use, chosen deliberately over inventing a new
``Effect`` member, matching those two capabilities' own real,
already-Accepted precedent for "no built-in undo" finality -- a real
email, once sent, cannot be recalled, the same as a force-pushed
history rewrite or a permanently deleted memory record.
"""

from __future__ import annotations

from jarvis.domain.capability import Effect
from jarvis.domain.provenance import Classification


def egress_effect_for(classification: Classification) -> Effect:
    """Return the Effect a real email-send CapabilityInvocation must declare for ``classification``.

    Also used, directly, by :func:`calendar_effect_for` for the
    attendee-bearing case -- one real classification function serves
    both ``send_message`` and ``create_event``-with-attendees, per
    ADR-0057's own Decision, not two parallel copies.

    Args:
        classification: The real classification of the outgoing
            content (an email body, or an attendee-bearing calendar
            event's summary).

    Returns:
        ``Effect.EGRESS_SECRET`` for ``Classification.SECRET``
        (unconditional ``Tier.DENY`` -- an email, or an invite, can
        never carry a value classified SECRET, full stop, the same
        zero-tolerance this project already applies to cloud-provider
        egress and memory writes). ``Effect.DESTRUCTIVE | Effect.IRREVERSIBLE``
        for everything else (``Tier.MANUAL_ONLY``, ADR-0059 -- a real
        send/invite can never be authorized by remote confirmation
        alone, mirroring ``git.force_push``'s/``memory.forget``'s own
        identical effect combination and "no built-in undo" reasoning).
    """
    if classification is Classification.SECRET:
        return Effect.EGRESS_SECRET
    return Effect.DESTRUCTIVE | Effect.IRREVERSIBLE


def calendar_effect_for(classification: Classification, *, has_attendees: bool) -> Effect:
    """Return the Effect a real create-calendar-event CapabilityInvocation must declare.

    Args:
        classification: The real classification of the draft event's
            own summary -- only consulted when ``has_attendees`` is
            ``True``; an attendee-less event's content classification
            does not change its floor (see below).
        has_attendees: Whether the draft carries one or more real
            attendees.

    Returns:
        ``Effect.WRITE_LOCAL`` (``Tier.CONFIRM``, the ordinary local-write
        floor) when ``has_attendees`` is ``False`` -- a real, deliberate
        choice, not ``EGRESS_SENSITIVE``, despite the event physically
        being written to a remote CalDAV server: grounded directly in
        ``git.push``'s own already-Accepted precedent ("an ordinary
        fast-forward push to a branch the user already owns" is
        ``WRITE_LOCAL``, not an egress effect) -- a CalDAV write to the
        user's own calendar account is the identical shape, real network
        egress to infrastructure the user themselves already controls,
        not a new external party gaining anything.

        Otherwise, delegates to :func:`egress_effect_for` -- most real
        CalDAV servers send invite emails to attendees automatically on
        real event creation, the exact same "reaches a new external
        party" shape ``send_message`` has, classified the identical way
        (``Effect.DESTRUCTIVE | Effect.IRREVERSIBLE``/``Tier.MANUAL_ONLY``
        for non-``SECRET`` content, per ADR-0059).
    """
    if not has_attendees:
        return Effect.WRITE_LOCAL
    return egress_effect_for(classification)
