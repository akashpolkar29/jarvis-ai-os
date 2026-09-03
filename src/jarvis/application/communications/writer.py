"""The email-send/calendar-event-create authorizers: route one real write invocation.

:class:`EmailSendAuthorizer` and :class:`CalendarEventAuthorizer` are
where ADR-0057 becomes load-bearing for real -- mirroring
``jarvis.application.memory.writer.MemoryWriteAuthorizer`` exactly. A
fresh ``CapabilityDescriptor`` is built per call, with
:func:`~jarvis.application.communications.classification.egress_effect_for`/
:func:`~jarvis.application.communications.classification.calendar_effect_for`
resolving *this specific invocation's* real effect -- not a fixed
effect registered once, the same reason ``MemoryWriteAuthorizer``/
``jarvis.application.reasoning.router.ModelRouter`` are never
registered in ``build_default_registry()`` either: the correct effect
genuinely varies per call, based on real, per-invocation content, not
something fixable at registration time.

**ADR-0057's own explicit ordering requirement (Amendment 2026-09-01,
finding 3), satisfied structurally, not just by convention**: each
``authorize_*`` method below classifies, builds the real
``CapabilityInvocation``, and calls
``AuthorizationOrchestrator.authorize()`` -- returning only a
``Decision``. Neither method ever touches ``EmailPort``/``CalendarPort``
itself; the real send/create call is strictly the caller's own
responsibility, only if ``decision.granted``, the identical shape
``MemoryWriteAuthorizer.authorize_write`` already established.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.application.communications.classification import (
    calendar_effect_for,
    egress_effect_for,
)
from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, CapabilityInvocation

if TYPE_CHECKING:
    from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
    from jarvis.domain.policy import Decision, PolicyContext
    from jarvis.domain.provenance import Tainted

EMAIL_SEND_CAPABILITY_ID = CapabilityId("communications.send_email")
CALENDAR_CREATE_EVENT_CAPABILITY_ID = CapabilityId("communications.create_calendar_event")


class EmailSendAuthorizer:
    """Authorizes one real email-send invocation through the real AuthorizationOrchestrator."""

    def __init__(self, orchestrator: AuthorizationOrchestrator) -> None:
        """Store the orchestrator every email-send authorization is routed through.

        Args:
            orchestrator: Owned by the caller, matching every other
                real consumer of ``AuthorizationOrchestrator`` in this
                repo -- this class never constructs its own.
        """
        self._orchestrator = orchestrator

    def authorize_send(
        self, to: tuple[str, ...], subject: str, body: Tainted[str], context: PolicyContext
    ) -> Decision:
        """Authorize sending a real email to ``to``.

        Args:
            to: The real recipient addresses -- carried on the
                invocation's own arguments for audit purposes, but not
                itself classified: ADR-0057's own Amendment 2026-09-01
                (finding 2) states this explicitly -- classification is
                computed once, over the whole message, for the entire
                call. There is no code path where a ``Classification.SECRET``
                body sends to some addresses in ``to`` and not others.
            subject: The real subject line -- carried on the
                invocation's own arguments, not itself classified
                (mirrors ``to``; the body is the real content this
                design classifies, per ``m6a-communications.md``).
            body: The real message body, with its own real provenance
                -- ``body.provenance.classification`` is what decides
                which ``Effect`` this call declares
                (``egress_effect_for``). **The real trust-boundary
                caveat ADR-0057's own Amendment 2026-09-01 (finding 1)
                states explicitly, mirrored here word for word**: this
                method *classifies* ``body``'s already-assigned
                ``Classification``; it does not *detect* anything.
                Whichever caller constructs this value is responsible
                for real, considered classification before calling
                this method -- this method does not, and cannot,
                second-guess a provenance it did not compute.
            context: Facts about the environment this decision is made
                in (confirmation channel availability).

        Returns:
            The real ``Decision`` -- ``granted`` is ``True`` only if
            this specific send is authorized right now. Already
            durably appended to the injected ``AuditChain`` by the
            time this returns. The real call to
            ``EmailPort.send_message`` itself is the caller's own
            responsibility, only if ``granted`` -- this method never
            touches the port.
        """
        effect = egress_effect_for(body.provenance.classification)
        descriptor = CapabilityDescriptor(
            id=EMAIL_SEND_CAPABILITY_ID,
            effects=effect,
            description="Send a real email to one or more external recipients.",
        )
        invocation = CapabilityInvocation(
            descriptor, body.map(lambda content: {"to": to, "subject": subject, "body": content})
        )
        return self._orchestrator.authorize(invocation, context)


class CalendarEventAuthorizer:
    """Authorizes one real calendar-event-create invocation through the real AuthorizationOrchestrator."""  # noqa: E501

    def __init__(self, orchestrator: AuthorizationOrchestrator) -> None:
        """Store the orchestrator every calendar-event-create authorization is routed through.

        Args:
            orchestrator: Owned by the caller, matching every other
                real consumer of ``AuthorizationOrchestrator`` in this
                repo -- this class never constructs its own.
        """
        self._orchestrator = orchestrator

    def authorize_create(
        self, summary: Tainted[str], *, has_attendees: bool, context: PolicyContext
    ) -> Decision:
        """Authorize creating a real calendar event.

        Args:
            summary: The draft event's own real summary, with its own
                real provenance -- ``summary.provenance.classification``
                decides the real ``Effect`` this call declares
                (``calendar_effect_for``) only when ``has_attendees`` is
                ``True``. The identical trust-boundary caveat
                :meth:`EmailSendAuthorizer.authorize_send` states
                applies here too: this method classifies, it does not
                detect.
            has_attendees: Whether the draft carries one or more real
                attendees -- an attendee-less event floors at
                ``Effect.WRITE_LOCAL``/``Tier.CONFIRM`` regardless of
                ``summary``'s own classification (``git.push``'s own
                precedent, see ``calendar_effect_for``'s own docstring).
            context: Facts about the environment this decision is made
                in (confirmation channel availability).

        Returns:
            The real ``Decision`` -- see
            :meth:`EmailSendAuthorizer.authorize_send`'s own identical
            return-value contract. The real call to
            ``CalendarPort.create_event`` itself is the caller's own
            responsibility, only if ``granted``.
        """
        effect = calendar_effect_for(summary.provenance.classification, has_attendees=has_attendees)
        descriptor = CapabilityDescriptor(
            id=CALENDAR_CREATE_EVENT_CAPABILITY_ID,
            effects=effect,
            description="Create a real calendar event, optionally with real attendees.",
        )
        invocation = CapabilityInvocation(
            descriptor,
            summary.map(lambda content: {"summary": content, "has_attendees": has_attendees}),
        )
        return self._orchestrator.authorize(invocation, context)
