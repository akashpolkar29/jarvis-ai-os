"""M6a email-send/calendar-event-create authorization: the real ADR-0057/ADR-0059 choke point.

:func:`~jarvis.application.communications.classification.egress_effect_for`
maps an outgoing email body's (or an attendee-bearing calendar event's
summary's) real :class:`~jarvis.domain.provenance.Classification` to
the :class:`~jarvis.domain.capability.Effect` a send/create
``CapabilityInvocation`` must declare -- ``Effect.EGRESS_SECRET``
(floors ``Tier.DENY``, unconditional) for ``Classification.SECRET``
only, ``Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`` (floors
``Tier.MANUAL_ONLY``, ADR-0059 -- never remote-satisfiable, the
project's own charter requirement for "sending emails" specifically,
mirroring ``git.force_push``'s/``memory.forget``'s own identical
effect combination) for everything else.
:func:`~jarvis.application.communications.classification.calendar_effect_for`
adds one real branch on top: an attendee-less event floors at
``Effect.WRITE_LOCAL``/``Tier.CONFIRM`` regardless of classification
(``git.push``'s own precedent) -- unaffected by ADR-0059, which only
amends the attendee-bearing case.

:class:`~jarvis.application.communications.writer.EmailSendAuthorizer`
and :class:`~jarvis.application.communications.writer.CalendarEventAuthorizer`
authorize one real send/create invocation through the existing
``AuthorizationOrchestrator``/``AuditChain`` choke point, mirroring
``jarvis.application.memory.writer.MemoryWriteAuthorizer`` exactly.
"""

from __future__ import annotations

from .classification import calendar_effect_for, egress_effect_for
from .writer import (
    CALENDAR_CREATE_EVENT_CAPABILITY_ID,
    EMAIL_SEND_CAPABILITY_ID,
    CalendarEventAuthorizer,
    EmailSendAuthorizer,
)

__all__ = [
    "CALENDAR_CREATE_EVENT_CAPABILITY_ID",
    "EMAIL_SEND_CAPABILITY_ID",
    "CalendarEventAuthorizer",
    "EmailSendAuthorizer",
    "calendar_effect_for",
    "egress_effect_for",
]
