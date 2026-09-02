"""Contract test: jarvis.ports.calendar.CalendarPort's own shape.

A minimal fake proves the Protocol itself is well-formed and
satisfiable independent of any specific adapter (WP-76). CalDavCalendarAdapter
(WP-78) is the real adapter, checked separately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.ports.calendar import CalendarPort

if TYPE_CHECKING:
    from jarvis.domain.calendar import CalendarEvent, CalendarEventDraft


class _FakeCalendarAdapter:
    """A minimal, real fake proving CalendarPort is satisfiable."""

    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        del start, end
        return ()

    async def create_event(self, draft: CalendarEventDraft) -> str:
        raise NotImplementedError(str(draft))


def test_a_conforming_fake_satisfies_calendar_port() -> None:
    """A real, minimal implementation is structurally a CalendarPort."""
    adapter = _FakeCalendarAdapter()

    assert isinstance(adapter, CalendarPort)


def test_an_object_missing_create_event_does_not_satisfy_calendar_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotACalendarStore:
        """Deliberately lacks create_event()."""

        async def list_events(self, start: str, end: str) -> tuple[object, ...]:
            del start, end
            return ()

    assert isinstance(NotACalendarStore(), CalendarPort) is False
