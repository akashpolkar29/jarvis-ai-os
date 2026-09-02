"""Unit tests for jarvis.domain.calendar's plain dataclasses."""

from __future__ import annotations

from jarvis.domain.calendar import CalendarEvent, CalendarEventDraft


def test_calendar_event_holds_its_own_real_fields() -> None:
    event = CalendarEvent(
        uid="event-123",
        summary="Team sync",
        start="2026-09-03T10:00:00+00:00",
        end="2026-09-03T11:00:00+00:00",
        attendees=("alice@example.com", "bob@example.com"),
    )

    assert event.uid == "event-123"
    assert event.summary == "Team sync"
    assert event.start == "2026-09-03T10:00:00+00:00"
    assert event.end == "2026-09-03T11:00:00+00:00"
    assert event.attendees == ("alice@example.com", "bob@example.com")


def test_calendar_event_draft_holds_its_own_real_fields() -> None:
    draft = CalendarEventDraft(
        summary="Team sync",
        start="2026-09-03T10:00:00+00:00",
        end="2026-09-03T11:00:00+00:00",
        attendees=(),
    )

    assert draft.summary == "Team sync"
    assert draft.start == "2026-09-03T10:00:00+00:00"
    assert draft.end == "2026-09-03T11:00:00+00:00"
    assert draft.attendees == ()
