"""Unit tests for jarvis.domain.email's plain dataclasses."""

from __future__ import annotations

from jarvis.domain.email import EmailMessage, EmailSummary


def test_email_summary_holds_its_own_real_fields() -> None:
    summary = EmailSummary(
        message_id="<abc@example.com>",
        sender="alice@example.com",
        subject="Hello",
        received_at="2026-09-03T10:00:00+00:00",
    )

    assert summary.message_id == "<abc@example.com>"
    assert summary.sender == "alice@example.com"
    assert summary.subject == "Hello"
    assert summary.received_at == "2026-09-03T10:00:00+00:00"


def test_email_message_holds_its_own_real_fields() -> None:
    message = EmailMessage(
        message_id="<abc@example.com>",
        sender="alice@example.com",
        recipients=("bob@example.com", "carol@example.com"),
        subject="Hello",
        body="Hi Bob and Carol,",
        received_at="2026-09-03T10:00:00+00:00",
    )

    assert message.message_id == "<abc@example.com>"
    assert message.sender == "alice@example.com"
    assert message.recipients == ("bob@example.com", "carol@example.com")
    assert message.subject == "Hello"
    assert message.body == "Hi Bob and Carol,"
    assert message.received_at == "2026-09-03T10:00:00+00:00"
