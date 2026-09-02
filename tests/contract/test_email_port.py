"""Contract test: jarvis.ports.email.EmailPort's own shape.

A minimal fake proves the Protocol itself is well-formed and
satisfiable independent of any specific adapter (WP-76, mirroring
test_memory_write_port.py's own "port exists and is tested
structurally before any real technology is chosen" ordering).
ImapEmailAdapter (WP-77) is the real adapter, checked separately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.ports.email import EmailPort

if TYPE_CHECKING:
    from jarvis.domain.email import EmailMessage, EmailSummary


class _FakeEmailAdapter:
    """A minimal, real fake proving EmailPort is satisfiable."""

    async def list_messages(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        del folder, limit
        return ()

    async def read_message(self, message_id: str) -> EmailMessage:
        raise NotImplementedError(message_id)

    async def send_message(self, to: tuple[str, ...], subject: str, body: str) -> None:
        del to, subject, body


def test_a_conforming_fake_satisfies_email_port() -> None:
    """A real, minimal implementation is structurally an EmailPort."""
    adapter = _FakeEmailAdapter()

    assert isinstance(adapter, EmailPort)


def test_an_object_missing_read_message_does_not_satisfy_email_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAnEmailStore:
        """Deliberately lacks read_message()/send_message()."""

        async def list_messages(self, folder: str, limit: int) -> tuple[object, ...]:
            del folder, limit
            return ()

    assert isinstance(NotAnEmailStore(), EmailPort) is False
