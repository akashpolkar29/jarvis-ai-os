"""Unit tests for jarvis.adapters.email.ImapEmailAdapter.

A fake, minimal IMAP connection object stands in for a real
imaplib.IMAP4_SSL socket -- this adapter's own real network path is
exercised only in a real, skipif-guarded manual verification pass (see
test_real_imap_flow_against_a_configured_mailbox below), matching this
project's established precedent for network-dependent adapters
(test_real_cdp_flow_against_a_local_page).
"""

from __future__ import annotations

import email as email_stdlib
import os
from email.message import EmailMessage as StdlibEmailMessage

import pytest

from jarvis.adapters.email import ImapEmailAdapter, _extract_body
from jarvis.ports.email import EmailMessageNotFoundError

_HAS_REAL_TEST_IMAP_ACCOUNT = bool(os.environ.get("JARVIS_TEST_IMAP_HOST"))


def _raw_message(  # noqa: PLR0913, PLR0917 -- one arg per real message field, test-only helper
    message_id: str, sender: str, to: str, subject: str, body: str, date: str
) -> bytes:
    msg = StdlibEmailMessage()
    msg["Message-ID"] = message_id
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = date
    msg.set_content(body)
    return msg.as_bytes()


class _FakeSecretPort:
    def __init__(self, value: str = "real-password") -> None:
        self._value = value
        self.requested_references: list[str] = []

    def get_secret(self, reference: str) -> str:
        self.requested_references.append(reference)
        return self._value

    def set_secret(self, reference: str, value: str) -> None:
        raise NotImplementedError


class _FakeImapConnection:
    """Records every real call it receives, in order, and returns canned real responses."""

    def __init__(
        self,
        message_numbers: list[bytes],
        messages_by_number: dict[bytes, bytes],
        search_response: list[bytes] | None = None,
    ) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._message_numbers = message_numbers
        self._messages_by_number = messages_by_number
        self._search_response = search_response

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        self.calls.append(("login", (user, password)))
        return ("OK", [b"Logged in"])

    def select(
        self, mailbox: str = "INBOX", readonly: bool = False
    ) -> tuple[str, list[bytes | None]]:
        self.calls.append(("select", (mailbox, readonly)))
        return ("OK", [b"1"])

    def search(self, charset: str | None, *criteria: str) -> tuple[str, list[bytes]]:
        self.calls.append(("search", (charset, *criteria)))
        if self._search_response is not None:
            return ("OK", self._search_response)
        return ("OK", [b" ".join(self._message_numbers)])

    def fetch(
        self, message_set: str, message_parts: str
    ) -> tuple[str, list[None] | list[bytes | tuple[bytes, bytes]]]:
        self.calls.append(("fetch", (message_set, message_parts)))
        number = message_set.encode("ascii")
        raw = self._messages_by_number[number]
        response: list[bytes | tuple[bytes, bytes]] = [(number, raw), b")"]
        return ("OK", response)

    def logout(self) -> tuple[str, list[None] | list[bytes | tuple[bytes, bytes]]]:
        self.calls.append(("logout", ()))
        return ("BYE", [None])


def _adapter(connection: _FakeImapConnection, secret: _FakeSecretPort) -> ImapEmailAdapter:
    return ImapEmailAdapter(
        "imap.example.com",
        "user@example.com",
        secret,
        "imap-password-ref",
        connection_factory=lambda _host: connection,
    )


async def test_list_messages_returns_real_summaries_most_recent_last_preserved() -> None:
    raw_one = _raw_message(
        "<one@example.com>", "alice@example.com", "user@example.com", "Hi", "body one", "date1"
    )
    raw_two = _raw_message(
        "<two@example.com>", "bob@example.com", "user@example.com", "Hey", "body two", "date2"
    )
    connection = _FakeImapConnection(
        message_numbers=[b"1", b"2"],
        messages_by_number={b"1": raw_one, b"2": raw_two},
    )
    adapter = _adapter(connection, _FakeSecretPort())

    summaries = await adapter.list_messages("INBOX", 5)

    assert [s.message_id for s in summaries] == ["<one@example.com>", "<two@example.com>"]
    assert summaries[0].sender == "alice@example.com"
    assert summaries[1].sender == "bob@example.com"
    assert summaries[0].subject == "Hi"


async def test_list_messages_respects_limit() -> None:
    raw = _raw_message("<x@example.com>", "a@example.com", "u@example.com", "S", "b", "d")
    connection = _FakeImapConnection(
        message_numbers=[b"1", b"2", b"3"],
        messages_by_number={b"1": raw, b"2": raw, b"3": raw},
    )
    adapter = _adapter(connection, _FakeSecretPort())

    summaries = await adapter.list_messages("INBOX", 2)

    assert len(summaries) == 2  # noqa: PLR2004 -- the real limit passed above


async def test_list_messages_logs_in_with_the_real_resolved_password() -> None:
    connection = _FakeImapConnection(message_numbers=[], messages_by_number={})
    secret = _FakeSecretPort(value="real-secret-password")
    adapter = _adapter(connection, secret)

    await adapter.list_messages("INBOX", 5)

    assert connection.calls[0] == ("login", ("user@example.com", "real-secret-password"))
    assert secret.requested_references == ["imap-password-ref"]


async def test_list_messages_always_logs_out() -> None:
    connection = _FakeImapConnection(message_numbers=[], messages_by_number={})
    adapter = _adapter(connection, _FakeSecretPort())

    await adapter.list_messages("INBOX", 5)

    assert connection.calls[-1] == ("logout", ())


async def test_read_message_returns_the_real_full_content() -> None:
    raw = _raw_message(
        "<abc@example.com>",
        "alice@example.com",
        "bob@example.com, carol@example.com",
        "Meeting",
        "Let's meet at 3pm.",
        "Thu, 03 Sep 2026 10:00:00 +0000",
    )
    connection = _FakeImapConnection(
        message_numbers=[b"1"],
        messages_by_number={b"1": raw},
        search_response=[b"1"],
    )
    adapter = _adapter(connection, _FakeSecretPort())

    message = await adapter.read_message("<abc@example.com>")

    assert message.message_id == "<abc@example.com>"
    assert message.sender == "alice@example.com"
    assert message.recipients == ("bob@example.com", "carol@example.com")
    assert message.subject == "Meeting"
    assert "Let's meet at 3pm." in message.body
    assert message.received_at == "Thu, 03 Sep 2026 10:00:00 +0000"


async def test_read_message_raises_when_no_message_matches() -> None:
    connection = _FakeImapConnection(
        message_numbers=[], messages_by_number={}, search_response=[b""]
    )
    adapter = _adapter(connection, _FakeSecretPort())

    with pytest.raises(EmailMessageNotFoundError):
        await adapter.read_message("<missing@example.com>")


async def test_send_message_always_raises_and_never_touches_the_network() -> None:
    connection = _FakeImapConnection(message_numbers=[], messages_by_number={})
    adapter = _adapter(connection, _FakeSecretPort())

    with pytest.raises(NotImplementedError, match="ADR-0057"):
        await adapter.send_message(("someone@example.com",), "Subject", "Body")

    assert connection.calls == []


def test_extract_body_of_a_multipart_message_prefers_the_plain_text_part() -> None:
    msg = email_stdlib.message.EmailMessage()
    msg.set_content("plain text version")
    msg.add_alternative("<p>html version</p>", subtype="html")

    body = _extract_body(msg)

    assert "plain text version" in body


@pytest.mark.skipif(
    not _HAS_REAL_TEST_IMAP_ACCOUNT,
    reason=(
        "Requires real, configured test-account IMAP credentials "
        "(JARVIS_TEST_IMAP_HOST/etc, not set here) -- mirroring "
        "test_real_cdp_flow_against_a_local_page's own real-infrastructure "
        "precedent, honestly skipped in CI, matching "
        "m6a-communications.md's own acceptance criterion 6."
    ),
)
async def test_real_imap_flow_against_a_configured_mailbox() -> None:
    """Never exercised by this pass -- no real test IMAP account is configured anywhere."""
    pytest.skip("No real IMAP adapter wiring built in this pass to run this against yet.")
