"""The calendar port: the seam between a real CalDAV calendar and this codebase.

**Both halves are real, working implementations as of 2026-09-03**:
``list_events`` (WP-76/WP-78) and ``create_event`` (WP-79 onward,
following ADR-0057's Acceptance -- 2026-09-03, directly by the user, in
conversation, after direct review of the ADR's own full text). Real,
per-invocation ``Effect``/``Tier`` classification for ``create_event``
(``application/communications/classification.py::calendar_effect_for``)
happens at the composition-root layer (``kernel/communications.py``),
before any real adapter method is ever called -- an attendee-less
event floors at ``Effect.WRITE_LOCAL``/``Tier.CONFIRM`` regardless of
its own summary's classification (``git.push``'s own precedent); an
attendee-bearing event routes through the identical
``egress_effect_for`` function ``EmailPort.send_message`` uses. This
Protocol itself declares no authorization, matching every other port
in this repo.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.calendar`` for the
concrete CalDAV-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.calendar import CalendarEvent, CalendarEventDraft


@runtime_checkable
class CalendarPort(Protocol):
    """A real CalDAV calendar this codebase can list events from, and create events in."""

    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        """Return every real event starting within ``[start, end]`` (both ISO-8601).

        No authorization happens inside this method -- matching every
        other port in this repo, this is a pure mechanism. Real
        `Tier.ALLOW` authorization happens at the composition-root
        layer (`kernel/communications.py`), before this is ever
        called.
        """
        ...

    async def create_event(self, draft: CalendarEventDraft) -> str:
        """Create a real calendar event from ``draft``. Returns the new event's real uid.

        No authorization happens inside this method -- matching every
        other port in this repo, this is a pure mechanism. Real
        `Effect`/`Tier` classification and authorization
        (`calendar_effect_for`, ADR-0057) happens at the
        composition-root layer (`kernel/communications.py`), before
        this is ever called; this method never runs unless that call's
        own `Decision.granted` is `True`.
        """
        ...
