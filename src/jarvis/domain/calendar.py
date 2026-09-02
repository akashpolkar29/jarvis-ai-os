"""Domain types for M6a's calendar surface (CalendarPort).

Plain, stdlib-only dataclasses, same reasoning as ``domain/email.py``.
``start``/``end`` are plain ``str`` (ISO-8601, server-authoritative),
not domain ``datetime`` objects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalendarEvent:
    """One real, existing calendar event."""

    uid: str
    summary: str
    start: str
    end: str
    attendees: tuple[str, ...]


@dataclass(frozen=True)
class CalendarEventDraft:
    """A not-yet-created event's own real content.

    Declared for `CalendarPort.create_event`'s own type signature only
    -- no real caller constructs one in this codebase yet.
    `create_event` is deliberately unimplemented (raises
    `NotImplementedError`); see `ports/calendar.py`'s own docstring for
    why (blocked on ADR-0057, Proposed, not Accepted).
    """

    summary: str
    start: str
    end: str
    attendees: tuple[str, ...]
