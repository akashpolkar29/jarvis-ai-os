"""Unit tests for jarvis.kernel.communications's authorize_and_* composition-root functions.

A stub EmailPort/CalendarPort (with call tracking) is injected in
place of the real ImapEmailAdapter/CalDavCalendarAdapter -- these
tests must be hermetic and never reach a real network. Satisfies
m6a-communications.md's own acceptance criteria 4 and 5 (the read
half) plus 6 (granted send/create genuinely reaches the port; a
denied decision never does). Acceptance criteria 1/2/3/7 (the real
SECRET-classification DENY/all-or-nothing property) are proven at the
EmailSendAuthorizer/CalendarEventAuthorizer level instead
(tests/property/test_communications_writer.py) -- authorize_and_send_email/
authorize_and_create_calendar_event always wrap their own content as
Tainted(value, Provenance.user()) (always PUBLIC), matching
authorize_and_remember's own identical choice, so a kernel-level call
alone can never produce a SECRET classification to test against.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.calendar import CalendarEvent
from jarvis.domain.email import EmailMessage, EmailSummary
from jarvis.domain.provenance import Classification, Trust
from jarvis.kernel.communications import (
    authorize_and_create_calendar_event,
    authorize_and_list_calendar_events,
    authorize_and_list_email,
    authorize_and_read_email,
    authorize_and_send_email,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.calendar import CalendarEventDraft


def _summary(message_id: str) -> EmailSummary:
    return EmailSummary(message_id=message_id, sender="a@example.com", subject="s", received_at="d")


def _message(message_id: str) -> EmailMessage:
    return EmailMessage(
        message_id=message_id,
        sender="a@example.com",
        recipients=("b@example.com",),
        subject="s",
        body="b",
        received_at="d",
    )


def _event(uid: str) -> CalendarEvent:
    return CalendarEvent(
        uid=uid,
        summary="s",
        start="2026-09-03T10:00:00+00:00",
        end="2026-09-03T11:00:00+00:00",
        attendees=(),
    )


class _StubEmailPort:
    """Records every real call it receives, returns canned real results."""

    def __init__(
        self, summaries: tuple[EmailSummary, ...] = (), message: EmailMessage | None = None
    ) -> None:
        self.list_calls: list[tuple[str, int]] = []
        self.read_calls: list[str] = []
        self.send_calls: list[tuple[tuple[str, ...], str, str]] = []
        self._summaries = summaries
        self._message = message

    async def list_messages(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        self.list_calls.append((folder, limit))
        return self._summaries

    async def read_message(self, message_id: str) -> EmailMessage:
        self.read_calls.append(message_id)
        assert self._message is not None
        return self._message

    async def send_message(self, to: tuple[str, ...], subject: str, body: str) -> None:
        self.send_calls.append((to, subject, body))


class _StubCalendarPort:
    """Records every real call it receives, returns canned real results."""

    def __init__(
        self, events: tuple[CalendarEvent, ...] = (), created_uid: str = "new-uid"
    ) -> None:
        self.list_calls: list[tuple[str, str]] = []
        self.create_calls: list[CalendarEventDraft] = []
        self._events = events
        self._created_uid = created_uid

    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        self.list_calls.append((start, end))
        return self._events

    async def create_event(self, draft: CalendarEventDraft) -> str:
        self.create_calls.append(draft)
        return self._created_uid


async def test_granted_list_email_returns_real_tainted_summaries(tmp_path: Path) -> None:
    port = _StubEmailPort(summaries=(_summary("<one@example.com>"), _summary("<two@example.com>")))

    decision, summaries = await authorize_and_list_email(
        "INBOX",
        5,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        email_port=port,
    )

    assert decision.granted is True
    assert summaries is not None
    assert len(summaries) == 2  # noqa: PLR2004 -- the real count of summaries constructed above
    assert summaries[0].value.message_id == "<one@example.com>"
    assert summaries[0].provenance.trust is Trust.UNTRUSTED_EXTERNAL
    assert summaries[0].provenance.classification is Classification.SENSITIVE
    assert port.list_calls == [("INBOX", 5)]


async def test_list_email_is_granted_even_with_no_confirmation_available(tmp_path: Path) -> None:
    """EGRESS_LOCAL floors Tier.ALLOW -- mirrors memory.retrieve's own equivalent test: a
    denied confirmation still lists real messages, the port is still genuinely reached."""
    port = _StubEmailPort(summaries=(_summary("<one@example.com>"),))

    decision, summaries = await authorize_and_list_email(
        "INBOX",
        5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        email_port=port,
    )

    assert decision.granted is True
    assert summaries is not None
    assert port.list_calls == [("INBOX", 5)]


async def test_granted_read_email_returns_a_real_tainted_message(tmp_path: Path) -> None:
    port = _StubEmailPort(message=_message("<abc@example.com>"))

    decision, message = await authorize_and_read_email(
        "<abc@example.com>",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        email_port=port,
    )

    assert decision.granted is True
    assert message is not None
    assert message.value.message_id == "<abc@example.com>"
    assert message.provenance.trust is Trust.UNTRUSTED_EXTERNAL
    assert message.provenance.classification is Classification.SENSITIVE
    assert message.provenance.sources == frozenset({"<abc@example.com>"})
    assert port.read_calls == ["<abc@example.com>"]


async def test_read_email_is_granted_even_with_no_confirmation_available(tmp_path: Path) -> None:
    """EGRESS_LOCAL floors Tier.ALLOW: a denied confirmation still reads the real message."""
    port = _StubEmailPort(message=_message("<abc@example.com>"))

    decision, message = await authorize_and_read_email(
        "<abc@example.com>",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        email_port=port,
    )

    assert decision.granted is True
    assert message is not None
    assert port.read_calls == ["<abc@example.com>"]


async def test_granted_list_calendar_events_returns_real_tainted_events(tmp_path: Path) -> None:
    port = _StubCalendarPort(events=(_event("event-1"),))

    decision, events = await authorize_and_list_calendar_events(
        "2026-09-01T00:00:00+00:00",
        "2026-09-30T00:00:00+00:00",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        calendar_port=port,
    )

    assert decision.granted is True
    assert events is not None
    assert events[0].value.uid == "event-1"
    assert events[0].provenance.trust is Trust.UNTRUSTED_EXTERNAL
    assert events[0].provenance.classification is Classification.SENSITIVE
    assert port.list_calls == [("2026-09-01T00:00:00+00:00", "2026-09-30T00:00:00+00:00")]


async def test_list_calendar_events_is_granted_even_with_no_confirmation_available(
    tmp_path: Path,
) -> None:
    """EGRESS_LOCAL floors Tier.ALLOW: a denied confirmation still lists real events."""
    port = _StubCalendarPort(events=(_event("event-1"),))

    decision, events = await authorize_and_list_calendar_events(
        "2026-09-01T00:00:00+00:00",
        "2026-09-30T00:00:00+00:00",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        calendar_port=port,
    )

    assert decision.granted is True
    assert events is not None
    assert port.list_calls == [("2026-09-01T00:00:00+00:00", "2026-09-30T00:00:00+00:00")]


async def test_a_single_granted_list_email_appends_a_verifiable_audit_record(
    tmp_path: Path,
) -> None:
    chain_path = tmp_path / "audit_chain.json"
    port = _StubEmailPort()

    await authorize_and_list_email(
        "INBOX",
        5,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        email_port=port,
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 1
    assert chain.verify().valid is True
    assert chain[0].decision.granted is True


async def test_granted_send_email_reaches_the_real_port(tmp_path: Path) -> None:
    port = _StubEmailPort()

    decision = await authorize_and_send_email(
        ("alice@example.com",),
        "Subject",
        "Body text",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        email_port=port,
    )

    assert decision.granted is True
    assert port.send_calls == [(("alice@example.com",), "Subject", "Body text")]


async def test_denied_send_email_never_reaches_the_real_port(tmp_path: Path) -> None:
    """EGRESS_SENSITIVE floors CONFIRM -- no confirmation channel available means denied."""
    port = _StubEmailPort()

    decision = await authorize_and_send_email(
        ("alice@example.com",),
        "Subject",
        "Body text",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        email_port=port,
    )

    assert decision.granted is False
    assert port.send_calls == []


async def test_granted_create_calendar_event_with_no_attendees_reaches_the_real_port(
    tmp_path: Path,
) -> None:
    port = _StubCalendarPort(created_uid="attendee-less-uid")

    outcome = await authorize_and_create_calendar_event(
        "Solo focus block",
        "2026-09-03T10:00:00+00:00",
        "2026-09-03T11:00:00+00:00",
        (),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        calendar_port=port,
    )

    assert outcome.decision.granted is True
    assert outcome.uid == "attendee-less-uid"
    assert len(port.create_calls) == 1
    assert port.create_calls[0].summary == "Solo focus block"
    assert port.create_calls[0].attendees == ()


async def test_granted_create_calendar_event_with_attendees_reaches_the_real_port(
    tmp_path: Path,
) -> None:
    port = _StubCalendarPort(created_uid="attendee-uid")

    outcome = await authorize_and_create_calendar_event(
        "Team sync",
        "2026-09-03T10:00:00+00:00",
        "2026-09-03T11:00:00+00:00",
        ("alice@example.com",),
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        calendar_port=port,
    )

    assert outcome.decision.granted is True
    assert outcome.uid == "attendee-uid"
    assert port.create_calls[0].attendees == ("alice@example.com",)


async def test_denied_create_calendar_event_never_reaches_the_real_port(tmp_path: Path) -> None:
    """An attendee-less create floors WRITE_LOCAL/CONFIRM -- no confirmation means denied."""
    port = _StubCalendarPort()

    outcome = await authorize_and_create_calendar_event(
        "Solo focus block",
        "2026-09-03T10:00:00+00:00",
        "2026-09-03T11:00:00+00:00",
        (),
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        calendar_port=port,
    )

    assert outcome.decision.granted is False
    assert outcome.uid is None
    assert port.create_calls == []
