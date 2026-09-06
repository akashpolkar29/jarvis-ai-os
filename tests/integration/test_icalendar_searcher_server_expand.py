"""Real, empirical proof that `server_expand=True` avoids `icalendar_searcher`'s AGPL logic.

Closes the real, empirical half of the 7-real-decisions prompt's own
Decision 4 (2026-09-05): `docs/architecture/secrets-license-sbom-audit-phase9.md`
found `icalendar-searcher` (AGPL-3.0-or-later) genuinely exercised by
every real recurring-event calendar search, via `caldav`'s own
client-side recurrence expansion. `docs/architecture/license-alternatives-research.md`
found a real, no-new-dependency candidate mitigation
(`caldav.Calendar.search(..., server_expand=True)`) but left it
unverified against a real server.

This test verifies it for real, against the real, local, credential-
free Radicale test server already used elsewhere in this project's
integration suite (mirrors ``test_email_calendar_against_local_servers.py``'s
own connection constants/skip pattern exactly, kept in a separate file
since this is a distinct, focused license-compliance investigation,
not a general read/write feature test).

**Methodology, matching the exact empirical finding recorded in
``adapters/calendar.py``'s own ``_list_events_sync`` comment**: a
real, live-instrumented ``unittest.mock.patch.object`` wrapping
``icalendar_searcher.Searcher.check_component`` (the real method that
performs substantive recurrence-filtering/expansion logic, confirmed
by reading ``caldav/search.py``'s own ``_filter_search_results``
directly) counts real invocations while a real
``CalDavCalendarAdapter.list_events()`` call runs against a real
recurring event seeded directly on the real server. A positive
control (today's real, unmodified pre-Decision-4 call shape,
``calendar.date_search(...)``, which the adapter no longer uses) is
included specifically to prove the instrumentation itself would have
caught a real invocation, not merely that none happened to occur.
"""

from __future__ import annotations

import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from icalendar_searcher.searcher import Searcher  # type: ignore[import-untyped]

from jarvis.adapters.calendar import CalDavCalendarAdapter

if TYPE_CHECKING:
    from jarvis.ports.secret import SecretPort

_RADICALE_URL = "http://127.0.0.1:5232/"
_RADICALE_USERNAME = "testuser"
_RADICALE_PASSWORD = "anything-radicale-auth-type-is-none"
_REAL_OCCURRENCE_COUNT = 5


def _real_radicale_is_reachable() -> bool:
    try:
        urllib.request.urlopen(_RADICALE_URL, timeout=1)
    except (TimeoutError, urllib.error.URLError, OSError):
        return False
    return True


_radicale_skip = pytest.mark.skipif(
    not _real_radicale_is_reachable(),
    reason=(
        "Requires a real, local Radicale CalDAV test server on 127.0.0.1:5232 -- "
        "not running here. Start it with: docker run -d --name jarvis-test-radicale "
        "-p 5232:5232 -v $(pwd)/tests/fixtures/radicale-config:/config:ro "
        "tomsquest/docker-radicale:latest -- or let CI's own service container start "
        "it (.github/workflows/ci.yml). No real calendar account is required or used."
    ),
)


class _StaticSecretPort:
    def __init__(self, password: str) -> None:
        self._password = password

    def get_secret(self, reference: str) -> str:
        del reference
        return self._password

    def set_secret(self, reference: str, value: str) -> None:
        raise NotImplementedError


def _real_caldav_calendar() -> object:
    """Return a real, connected `caldav.Calendar` -- the same object `CalDavCalendarAdapter` uses."""  # noqa: E501
    from caldav.davclient import DAVClient  # noqa: PLC0415 -- test-local, real, heavy import

    client = DAVClient(url=_RADICALE_URL, username=_RADICALE_USERNAME, password=_RADICALE_PASSWORD)
    principal = client.get_principal()
    calendars = principal.calendars()
    assert isinstance(calendars, list), "test-only DAVClient is always synchronous"
    if not calendars:
        principal.make_calendar(name="Test Calendar")
        calendars = principal.calendars()
        assert isinstance(calendars, list), "test-only DAVClient is always synchronous"
    return calendars[0]


def _seed_real_recurring_event(calendar: object) -> tuple[str, datetime, datetime]:
    """Seed a real, 5-occurrence weekly recurring VEVENT directly, bypassing the adapter.

    `CalendarEventDraft` (`domain/calendar.py`) has no recurrence
    field -- this seeds the raw ICS directly via `caldav`'s own
    `save_event`, the same real mechanism a real calendar client would
    use to create a recurring event, matching this test file's own
    "seed separately from the adapter under test" precedent
    (`test_email_calendar_against_local_servers.py`'s raw-smtplib seed).
    """
    uid = str(uuid.uuid4())  # noqa: TID251 -- real test-data uniqueness
    now = datetime.now(UTC).replace(microsecond=0)  # noqa: TID251 -- real, test-local timestamp
    dtstart = now + timedelta(days=1)
    dtend = dtstart + timedelta(hours=1)
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//jarvis-test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"DTEND:{dtend.strftime('%Y%m%dT%H%M%SZ')}\r\n"
        "SUMMARY:Real recurring test event (server_expand verification)\r\n"
        f"RRULE:FREQ=WEEKLY;COUNT={_REAL_OCCURRENCE_COUNT}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    calendar.save_event(ics)  # type: ignore[attr-defined]
    return uid, dtstart, dtend


def _real_calendar_adapter() -> CalDavCalendarAdapter:
    secret: SecretPort = _StaticSecretPort(_RADICALE_PASSWORD)
    return CalDavCalendarAdapter(
        url=_RADICALE_URL,
        username=_RADICALE_USERNAME,
        secret=secret,
        password_reference="unused-static-test-password",
    )


@_radicale_skip
async def test_real_list_events_with_server_expand_never_invokes_check_component() -> None:
    """The real, current adapter (server_expand=True) never calls Searcher.check_component."""
    calendar = _real_caldav_calendar()
    uid, dtstart, _dtend = _seed_real_recurring_event(calendar)

    adapter = _real_calendar_adapter()
    search_start = (dtstart - timedelta(days=1)).isoformat()
    search_end = (dtstart + timedelta(weeks=6)).isoformat()

    with mock.patch.object(
        Searcher, "check_component", wraps=Searcher.check_component, autospec=True
    ) as spy:
        events = await adapter.list_events(search_start, search_end)

    assert spy.call_count == 0, (
        "Searcher.check_component (icalendar_searcher's own real, substantive "
        "filtering/expansion logic) was invoked -- the server_expand=True "
        "mitigation is no longer avoiding it; do not silently accept this "
        "regression, see docs/architecture/license-alternatives-research.md."
    )
    # A real, positive functional check alongside the negative license check:
    # server-side expansion must still return all 5 real occurrences of
    # THIS test's own seeded event correctly -- filtered by uid, since a
    # real calendar (and this shared, local test server across repeated
    # runs) may hold other, unrelated events in the same search window.
    matching = [e for e in events if e.uid == uid]
    assert len(matching) == _REAL_OCCURRENCE_COUNT


@_radicale_skip
async def test_positive_control_date_search_does_invoke_check_component() -> None:
    """Proves the instrumentation itself is real: the OLD, no-longer-used call shape DOES invoke it.

    Without this positive control, a `call_count == 0` result in the
    test above would be ambiguous -- it could mean either "genuinely
    avoided" or "the mock never had a chance to observe a real call
    for some unrelated reason" (wrong target, wrong mock scope, wrong
    server support). This proves the same server, same real recurring
    event, same mock target, genuinely does record calls under the
    old, deprecated `date_search()`-equivalent call shape.
    """
    calendar = _real_caldav_calendar()
    uid, dtstart, _dtend = _seed_real_recurring_event(calendar)

    search_start = dtstart - timedelta(days=1)
    search_end = dtstart + timedelta(weeks=6)

    with mock.patch.object(
        Searcher, "check_component", wraps=Searcher.check_component, autospec=True
    ) as spy:
        results = calendar.search(  # type: ignore[attr-defined]
            start=search_start, end=search_end, event=True, expand=True
        )

    assert spy.call_count > 0, (
        "Positive control failed: the old, client-side-expansion call shape "
        "was expected to invoke Searcher.check_component at least once against "
        "a real recurring event, but it did not -- the instrumentation itself "
        "may be broken, invalidating the negative result above."
    )
    # Filtered by uid for the identical reason the test above is: this
    # shared, local test server may hold other, unrelated events.
    matching = [r for r in results if str(r.icalendar_component.get("uid")) == uid]
    assert len(matching) == _REAL_OCCURRENCE_COUNT
