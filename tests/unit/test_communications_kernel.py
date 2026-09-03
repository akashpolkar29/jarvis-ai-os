"""Unit tests for jarvis.kernel.communications's authorize_and_* composition-root functions.

A stub EmailPort/CalendarPort (with call tracking) is injected in
place of the real ImapEmailAdapter/CalDavCalendarAdapter -- these
tests must be hermetic and never reach a real network. Satisfies
m6a-communications.md's own acceptance criteria 4 and 5 (for the
real, implemented read half only -- 1/2/3/6/7 all concern
send_message/create_event, which no real adapter implements, blocked
on ADR-0057).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.calendar import CalendarEvent
from jarvis.domain.email import EmailMessage, EmailSummary
from jarvis.domain.provenance import Classification, Trust
from jarvis.kernel.communications import (
    authorize_and_list_calendar_events,
    authorize_and_list_email,
    authorize_and_read_email,
)

if TYPE_CHECKING:
    from pathlib import Path


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
        raise NotImplementedError


class _StubCalendarPort:
    """Records every real call it receives, returns canned real results."""

    def __init__(self, events: tuple[CalendarEvent, ...] = ()) -> None:
        self.list_calls: list[tuple[str, str]] = []
        self._events = events

    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]:
        self.list_calls.append((start, end))
        return self._events

    async def create_event(self, draft: object) -> str:
        raise NotImplementedError


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
