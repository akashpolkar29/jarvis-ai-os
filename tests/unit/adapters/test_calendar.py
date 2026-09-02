"""Unit tests for jarvis.adapters.calendar.CalDavCalendarAdapter.

A fake, minimal Calendar object (backed by real `icalendar.Event`
components, since `icalendar` is a real, installed dependency) stands
in for a real `caldav.Calendar` -- this adapter's own real network
path is never exercised in this pass, matching
`m6a-communications.md`'s own "no real test-account CalDAV credentials
configured" precedent (identical to `adapters/email.py`'s own real-IMAP
gap).
"""

from __future__ import annotations

from datetime import UTC, datetime

import icalendar
import pytest

from jarvis.adapters.calendar import CalDavCalendarAdapter
from jarvis.domain.calendar import CalendarEventDraft


class _FakeSecretPort:
    def get_secret(self, reference: str) -> str:
        del reference
        return "real-password"

    def set_secret(self, reference: str, value: str) -> None:
        raise NotImplementedError


def _real_event_component(
    uid: str,
    summary: str,
    start: datetime,
    end: datetime,
    attendees: list[str],
) -> icalendar.Event:
    """Build a real icalendar.Event component -- no fake stand-in needed, the real library is installed."""  # noqa: E501
    event = icalendar.Event()
    event.add("uid", uid)
    event.add("summary", summary)
    event.add("dtstart", start)
    event.add("dtend", end)
    for attendee in attendees:
        event.add("attendee", f"mailto:{attendee}")
    return event


class _FakeCalendarObject:
    """A minimal stand-in for caldav.CalendarObjectResource -- just the one property used."""

    def __init__(self, component: icalendar.Event) -> None:
        self.icalendar_component = component


class _FakeCalendar:
    """Records every real date_search() call, returns canned real events."""

    def __init__(self, events: list[_FakeCalendarObject]) -> None:
        self.calls: list[tuple[datetime, datetime]] = []
        self._events = events

    def date_search(self, start: datetime, end: datetime) -> list[_FakeCalendarObject]:
        self.calls.append((start, end))
        return self._events


def _adapter(calendar: _FakeCalendar) -> CalDavCalendarAdapter:
    return CalDavCalendarAdapter(
        "https://caldav.example.com",
        "user@example.com",
        _FakeSecretPort(),
        "caldav-password-ref",
        calendar_factory=lambda: calendar,
    )


async def test_list_events_returns_real_events_with_no_attendees() -> None:
    start = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 3, 11, 0, tzinfo=UTC)
    component = _real_event_component("event-1", "Solo focus block", start, end, [])
    calendar = _FakeCalendar([_FakeCalendarObject(component)])
    adapter = _adapter(calendar)

    events = await adapter.list_events("2026-09-01T00:00:00+00:00", "2026-09-30T00:00:00+00:00")

    assert len(events) == 1
    assert events[0].uid == "event-1"
    assert events[0].summary == "Solo focus block"
    assert events[0].attendees == ()


async def test_list_events_returns_a_single_real_attendee() -> None:
    start = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 3, 11, 0, tzinfo=UTC)
    component = _real_event_component("event-2", "1:1", start, end, ["alice@example.com"])
    calendar = _FakeCalendar([_FakeCalendarObject(component)])
    adapter = _adapter(calendar)

    events = await adapter.list_events("2026-09-01T00:00:00+00:00", "2026-09-30T00:00:00+00:00")

    assert events[0].attendees == ("alice@example.com",)


async def test_list_events_returns_multiple_real_attendees() -> None:
    start = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
    end = datetime(2026, 9, 3, 11, 0, tzinfo=UTC)
    component = _real_event_component(
        "event-3", "Team sync", start, end, ["alice@example.com", "bob@example.com"]
    )
    calendar = _FakeCalendar([_FakeCalendarObject(component)])
    adapter = _adapter(calendar)

    events = await adapter.list_events("2026-09-01T00:00:00+00:00", "2026-09-30T00:00:00+00:00")

    assert events[0].attendees == ("alice@example.com", "bob@example.com")


async def test_list_events_passes_the_real_parsed_start_and_end_to_date_search() -> None:
    calendar = _FakeCalendar([])
    adapter = _adapter(calendar)

    await adapter.list_events("2026-09-01T00:00:00+00:00", "2026-09-30T00:00:00+00:00")

    assert calendar.calls == [
        (
            datetime.fromisoformat("2026-09-01T00:00:00+00:00"),
            datetime.fromisoformat("2026-09-30T00:00:00+00:00"),
        )
    ]


async def test_list_events_returns_empty_tuple_when_nothing_matches() -> None:
    calendar = _FakeCalendar([])
    adapter = _adapter(calendar)

    events = await adapter.list_events("2026-09-01T00:00:00+00:00", "2026-09-30T00:00:00+00:00")

    assert events == ()


async def test_create_event_always_raises_and_never_touches_the_network() -> None:
    calendar = _FakeCalendar([])
    adapter = _adapter(calendar)
    draft = CalendarEventDraft(
        summary="s",
        start="2026-09-03T10:00:00+00:00",
        end="2026-09-03T11:00:00+00:00",
        attendees=(),
    )

    with pytest.raises(NotImplementedError, match="ADR-0057"):
        await adapter.create_event(draft)

    assert calendar.calls == []
