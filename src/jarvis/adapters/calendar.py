"""Adapters implementing jarvis.ports.calendar.CalendarPort.

:class:`CalDavCalendarAdapter` is WP-78's own real implementation of
the port's read half (`list_events`) via the `caldav` library (real
RFC4791 client, evaluated in `m6-scoping-notes.md`'s own Part 2
research). Its real API was inspected directly against the installed
3.2.1 package before writing this adapter, not assumed from memory or
documentation alone -- confirmed via `mypy --strict`'s own
`reveal_type` against real code:

- `caldav`'s own top-level package uses PEP 562 lazy `__getattr__` for
  its heavy re-exports (`caldav.DAVClient` etc.) -- real, but this
  defeats mypy's static resolution (`caldav.DAVClient` resolves to
  `object`, not a class). Imported from its real submodule instead
  (`caldav.davclient.DAVClient`), which resolves cleanly.
- `DAVClient.principal()` (the method the library's own docs show in
  most examples) is itself untyped (`def principal(self, *largs,
  **kwargs):`, no annotations) -- `mypy --strict` correctly refuses an
  untyped call. `DAVClient.get_principal()` is the real, typed
  equivalent the library's own docstring already names as the
  "for new code" replacement -- used here instead.
- `Principal.calendars()`/`Calendar.date_search()` are both really
  declared to return `X | Coroutine[Any, Any, X]` (the same real
  method serves both `DAVClient` and `AsyncDAVClient`). Since this
  adapter only ever constructs a real, synchronous `DAVClient`, the
  coroutine branch is real but unreachable in practice -- narrowed
  with a real `isinstance(calendars, list)` check, not silently
  assumed or blindly cast.
- `CalendarObjectResource.icalendar_component` (from the separate
  `icalendar` library) resolves to `Any` under `mypy --strict` --
  `icalendar` itself ships no stricter static types to check against.
  Real behavior of its own `ATTENDEE` property was confirmed by direct
  construction, not assumed: no attendee returns `None`; exactly one
  returns a bare `vCalAddress`; more than one returns a real `list` of
  them -- `_parse_attendees` handles all three.

**Updated 2026-09-03 (WP-79 onward, following ADR-0057's Acceptance)**:
`create_event` is now a real implementation, via `Calendar.add_event`
-- confirmed as the real, current, non-deprecated write method on the
installed 3.2.1 `Calendar` class (`save_event` is a real, deprecated
alias for it, per the library's own docstring; `add_event`, not
`save_with_invites`, is used here since this design has no `organizer`
concept to add -- `add_event` writes the identical ATTENDEE-bearing
VEVENT a real CalDAV server's own RFC 6638 scheduling logic acts on
regardless of which of the two real methods was used to write it).
Real attendee addresses are given the `mailto:` scheme prefix
(`_with_mailto`) before being handed to `icalendar`'s own `vCalAddress`
encoding -- confirmed directly (`icalendar.vCalAddress("x@example.com").to_ical()`
does not add the prefix itself), mirroring `_strip_mailto`'s read-side
handling exactly, in reverse.

`caldav`'s own real client is blocking/synchronous; every real method
here wraps its own blocking call in `asyncio.to_thread`, the identical
pattern `adapters/email.py` uses for `imaplib`/`smtplib`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from jarvis.domain.calendar import CalendarEvent

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from jarvis.domain.calendar import CalendarEventDraft
    from jarvis.ports.secret import SecretPort


class _CalendarObjectLike(Protocol):
    """The narrow subset of caldav.CalendarObjectResource's own real interface this adapter uses."""

    @property
    def icalendar_component(self) -> Any: ...

    @property
    def id(self) -> str | None: ...


class _Calendar(Protocol):
    """The narrow subset of caldav.Calendar's own real interface this adapter uses."""

    def date_search(self, start: datetime, end: datetime) -> Sequence[_CalendarObjectLike]: ...
    def add_event(
        self,
        dtstart: datetime,
        dtend: datetime,
        summary: str,
        attendee: list[str] | None = None,
    ) -> _CalendarObjectLike | Coroutine[Any, Any, _CalendarObjectLike]: ...


def _strip_mailto(value: str) -> str:
    prefix = "mailto:"
    return value[len(prefix) :] if value.lower().startswith(prefix) else value


def _with_mailto(value: str) -> str:
    prefix = "mailto:"
    return value if value.lower().startswith(prefix) else f"{prefix}{value}"


def _parse_attendees(component: Any) -> tuple[str, ...]:
    """Handle all three real shapes icalendar's own ATTENDEE property can take.

    Confirmed directly against the installed icalendar library, not
    assumed: no ATTENDEE property is `None`; exactly one is a bare
    `vCalAddress`; more than one is a real `list` of them.
    """
    raw = component.get("attendee")
    if raw is None:
        return ()
    if isinstance(raw, list):
        return tuple(_strip_mailto(str(item)) for item in raw)
    return (_strip_mailto(str(raw)),)


def _parse_event(calendar_object: _CalendarObjectLike) -> CalendarEvent:
    component = calendar_object.icalendar_component
    start = component.get("dtstart")
    end = component.get("dtend")
    uid = component.get("uid")
    summary = component.get("summary")
    return CalendarEvent(
        uid=str(uid) if uid is not None else "",
        summary=str(summary) if summary is not None else "",
        start=start.dt.isoformat() if start is not None else "",
        end=end.dt.isoformat() if end is not None else "",
        attendees=_parse_attendees(component),
    )


def _parse_aware_iso8601(value: str, field_name: str) -> datetime:
    """Parse `value` as ISO-8601, rejecting a naive (timezone-less) result.

    Real bug found and fixed (10-phase combined pass, Phase 10,
    timezone-correctness task): `datetime.fromisoformat()` silently
    accepts a string with no UTC offset (e.g. "2026-01-01T15:00:00"),
    producing a naive `datetime` -- confirmed directly, not assumed.
    Handed to `caldav`/`icalendar` as-is, this becomes a "floating
    time" VEVENT with no `TZID`/`Z` designator at all, whose displayed
    time genuinely differs depending on whichever calendar client's
    own local timezone setting later renders it -- the opposite of
    what a real scheduling feature exists to guarantee (an
    unambiguous point in time). Neither `kernel/communications.py` nor
    `domain/calendar.py` validated this before this fix; every
    existing test happened to always supply an explicit offset,
    so this was never actually exercised.

    Args:
        value: The real, caller-supplied ISO-8601 string.
        field_name: Which field this is, for a clear error message.

    Raises:
        ValueError: If `value` is not valid ISO-8601, or parses to a
            naive `datetime` (no timezone offset).
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        msg = (
            f"{field_name} must include an explicit timezone offset "
            f"(e.g. '+00:00' or 'Z'), got {value!r} -- a naive datetime "
            "would create an ambiguous 'floating time' calendar event."
        )
        raise ValueError(msg)
    return parsed


class CalendarNotFoundError(Exception):
    """Raised when a real CalDAV principal has no real calendars to read from.

    Defined on the adapter, not the port: this is a real,
    account-configuration condition specific to the CalDAV protocol's
    own principal/calendar-collection model, not a general
    `CalendarPort` concept every future implementation would share.
    """


class CalendarEventCreationError(Exception):
    """Raised when a real CalDAV server does not return a real UID for a newly created event.

    Defined on the adapter, not the port, for the identical reason
    `CalendarNotFoundError` is: `caldav`'s own real `.id` property is
    genuinely typed `str | None` -- this is a real, checkable
    protocol-level anomaly (a compliant server always echoes back a
    UID), not a "this can't happen" case papered over defensively.
    """


def _real_calendar_factory(
    url: str, username: str, secret: SecretPort, password_reference: str
) -> _Calendar:
    # Deliberately lazy: a real, heavy third-party import, matching this
    # project's own "lazy-import a real-hardware/real-network client"
    # precedent (adapters/tts.py's own piper import).
    from caldav.davclient import DAVClient  # noqa: PLC0415

    password = secret.get_secret(password_reference)
    client = DAVClient(url=url, username=username, password=password)
    principal = client.get_principal()
    calendars = principal.calendars()
    if not isinstance(calendars, list) or not calendars:
        msg = f"No real calendars found for principal at {url!r}."
        raise CalendarNotFoundError(msg)
    return calendars[0]


class CalDavCalendarAdapter:
    """A real, CalDAV-backed `CalendarPort` -- reads and writes both real."""

    def __init__(
        self,
        url: str,
        username: str,
        secret: SecretPort,
        password_reference: str,
        calendar_factory: Callable[[], _Calendar] | None = None,
    ) -> None:
        """Store how to connect and how to resolve the real credential -- no I/O at construction.

        Args:
            url: The real CalDAV server URL.
            username: The real account username.
            secret: Resolves ``password_reference`` to a real password
                at the point of use (ADR-0017, ADR-0042) -- never
                stored as a field, never read at construction time.
            password_reference: The keyring reference for this
                account's password.
            calendar_factory: Returns a real, connected calendar
                object (the first one found for the real principal).
                Defaults to a real `caldav.davclient.DAVClient`-backed
                connection. Overridable for tests -- no real network
                connection is made until a real method is called.
        """
        self._calendar_factory = calendar_factory or (
            lambda: _real_calendar_factory(url, username, secret, password_reference)
        )

    def _list_events_sync(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        calendar = self._calendar_factory()
        real_events = calendar.date_search(
            _parse_aware_iso8601(start, "start"), _parse_aware_iso8601(end, "end")
        )
        return tuple(_parse_event(event) for event in real_events)

    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        """See `CalendarPort.list_events`. Runs the real, blocking CalDAV call off the event loop."""  # noqa: E501
        return await asyncio.to_thread(self._list_events_sync, start, end)

    def _create_event_sync(self, draft: CalendarEventDraft) -> str:
        calendar = self._calendar_factory()
        attendees = [_with_mailto(attendee) for attendee in draft.attendees] or None
        created = calendar.add_event(
            dtstart=_parse_aware_iso8601(draft.start, "start"),
            dtend=_parse_aware_iso8601(draft.end, "end"),
            summary=draft.summary,
            attendee=attendees,
        )
        if isinstance(created, Coroutine):
            # Real but unreachable in practice: this adapter only ever constructs a
            # synchronous DAVClient (see _real_calendar_factory) -- mirrors
            # _list_events_sync's own isinstance(calendars, list) narrowing.
            msg = "add_event() returned a coroutine -- this adapter requires a synchronous client."
            raise CalendarEventCreationError(msg)
        if created.id is None:
            msg = f"Real CalDAV server returned no UID for the newly created event {draft!r}."
            raise CalendarEventCreationError(msg)
        return created.id

    async def create_event(self, draft: CalendarEventDraft) -> str:
        """See `CalendarPort.create_event`. Runs the real, blocking CalDAV call off the event loop.

        Real, per-invocation classification/authorization
        (`calendar_effect_for`, ADR-0057) happens entirely at the
        composition-root layer (`kernel/communications.py`), before
        this is ever called -- matching `list_events`'s own identical
        "pure mechanism, no authorization here" contract.

        Raises:
            CalendarEventCreationError: If the real CalDAV server does
                not echo back a real UID for the newly created event.
        """
        return await asyncio.to_thread(self._create_event_sync, draft)
