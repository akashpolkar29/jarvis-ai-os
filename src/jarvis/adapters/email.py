"""Adapters implementing jarvis.ports.email.EmailPort.

:class:`ImapEmailAdapter` is WP-77's own real implementation of the
port's read half (`list_messages`/`read_message`) via `imaplib`
(standard library, per `m6a-communications.md`'s own stdlib-only
decision). `send_message` raises `NotImplementedError` unconditionally
-- see `ports/email.py`'s own module docstring for why (blocked on
ADR-0057, `Proposed`, not `Accepted`). No SMTP call, no `smtplib`
import, exists anywhere in this module.

`imaplib.IMAP4_SSL` is a blocking, synchronous client with no async
twin in the standard library; every real method here wraps its own
blocking call in `asyncio.to_thread` so `EmailPort`'s own async
interface is honored without blocking the event loop -- a new pattern
in this codebase (no existing adapter has needed to wrap blocking I/O
behind an async port before this one).

Message parsing uses the standard library's own `email` package
(`email.message_from_bytes`), not hand-rolled header/MIME parsing --
the same "use the real, correct stdlib tool" discipline this project
already applies elsewhere (`configparser`/`tomllib` for
`application/coding/classification.py`'s own real config-file
detection).
"""

from __future__ import annotations

import asyncio
import email as email_stdlib
import imaplib
from email.header import decode_header
from email.utils import parseaddr
from typing import TYPE_CHECKING, Protocol

from jarvis.domain.email import EmailMessage, EmailSummary
from jarvis.ports.email import EmailMessageNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable
    from email.message import Message

    from jarvis.ports.secret import SecretPort


class _ImapConnection(Protocol):
    """The narrow subset of imaplib.IMAP4_SSL's own real interface this adapter uses.

    Real return types confirmed via `mypy --strict`'s own
    `reveal_type` against typeshed's stdlib stubs, not assumed --
    `fetch`'s own real message-part payload type
    (`list[None] | list[bytes | tuple[bytes, bytes]]`) is genuinely
    that heterogeneous; narrowed at each real call site instead of
    typed away here.
    """

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]: ...
    def select(
        self, mailbox: str = ..., readonly: bool = ...
    ) -> tuple[str, list[bytes | None]]: ...
    def search(self, charset: str | None, *criteria: str) -> tuple[str, list[bytes]]: ...
    def fetch(
        self, message_set: str, message_parts: str
    ) -> tuple[str, list[None] | list[bytes | tuple[bytes, bytes]]]: ...
    def logout(self) -> tuple[str, list[None] | list[bytes | tuple[bytes, bytes]]]: ...


def _decode_mime_header(raw: str | None) -> str:
    """Decode a real, possibly RFC 2047-encoded header value into plain text."""
    if not raw:
        return ""
    decoded_parts = []
    for text, charset in decode_header(raw):
        if isinstance(text, bytes):
            decoded_parts.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(text)
    return "".join(decoded_parts)


def _extract_body(message: Message) -> str:
    """Return a real message's own plain-text body, walking a multipart structure if present."""
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = part.get("Content-Disposition")
            if content_type == "text/plain" and not disposition:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = message.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = message.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return str(message.get_payload())


def _parse_recipients(message: Message) -> tuple[str, ...]:
    raw_to = _decode_mime_header(message.get("To", ""))
    if not raw_to:
        return ()
    return tuple(addr for _name, addr in (parseaddr(part) for part in raw_to.split(",")) if addr)


class ImapEmailAdapter:
    """A real, read-only IMAP-backed `EmailPort`. `send_message` is deliberately unimplemented."""

    def __init__(
        self,
        host: str,
        username: str,
        secret: SecretPort,
        password_reference: str,
        connection_factory: Callable[[str], _ImapConnection] | None = None,
    ) -> None:
        """Store how to connect and how to resolve the real credential -- no I/O at construction.

        Args:
            host: The real IMAP server hostname.
            username: The real mailbox username.
            secret: Resolves ``password_reference`` to a real password
                at the point of use (ADR-0017, ADR-0042) -- never
                stored as a field, never read at construction time.
            password_reference: The keyring reference for this
                mailbox's password.
            connection_factory: Given a host, returns a real,
                unauthenticated connection object. Defaults to
                ``imaplib.IMAP4_SSL``. Overridable for tests -- no
                real network connection is made until a real method is
                called.
        """
        self._host = host
        self._username = username
        self._secret = secret
        self._password_reference = password_reference
        # A lambda, not the bare class, deliberately: mypy --strict does not
        # accept `type[IMAP4_SSL]` directly where `Callable[[str], _ImapConnection]`
        # is expected, even though the call signature is structurally
        # identical -- a real mypy quirk around class-object callables,
        # confirmed by direct testing, not a style preference.
        self._connection_factory: Callable[[str], _ImapConnection] = (
            connection_factory or (lambda host: imaplib.IMAP4_SSL(host))  # noqa: PLW0108
        )

    def _connect(self) -> _ImapConnection:
        connection = self._connection_factory(self._host)
        password = self._secret.get_secret(self._password_reference)
        connection.login(self._username, password)
        return connection

    def _list_messages_sync(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        connection = self._connect()
        try:
            connection.select(folder, readonly=True)
            _typ, data = connection.search(None, "ALL")
            message_numbers = data[0].split() if data and data[0] else []
            summaries = []
            for number in message_numbers[-limit:]:
                _typ, msg_data = connection.fetch(number.decode("ascii"), "(RFC822.HEADER)")
                first = msg_data[0]
                if not isinstance(first, tuple):
                    continue
                parsed = email_stdlib.message_from_bytes(first[1])
                summaries.append(
                    EmailSummary(
                        message_id=parsed.get("Message-ID", "").strip(),
                        sender=parseaddr(_decode_mime_header(parsed.get("From")))[1],
                        subject=_decode_mime_header(parsed.get("Subject")),
                        received_at=parsed.get("Date", ""),
                    )
                )
            return tuple(summaries)
        finally:
            connection.logout()

    async def list_messages(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        """See `EmailPort.list_messages`. Runs the real, blocking IMAP call off the event loop."""
        return await asyncio.to_thread(self._list_messages_sync, folder, limit)

    def _read_message_sync(self, message_id: str) -> EmailMessage:
        connection = self._connect()
        try:
            connection.select("INBOX", readonly=True)
            _typ, data = connection.search(None, f'(HEADER Message-ID "{message_id}")')
            message_numbers = data[0].split() if data and data[0] else []
            if not message_numbers:
                msg = f"No message found with Message-ID {message_id!r}."
                raise EmailMessageNotFoundError(msg)
            _typ, msg_data = connection.fetch(message_numbers[0].decode("ascii"), "(RFC822)")
            first = msg_data[0]
            if not isinstance(first, tuple):
                msg = f"No message found with Message-ID {message_id!r}."
                raise EmailMessageNotFoundError(msg)
            parsed = email_stdlib.message_from_bytes(first[1])
            return EmailMessage(
                message_id=parsed.get("Message-ID", "").strip(),
                sender=parseaddr(_decode_mime_header(parsed.get("From")))[1],
                recipients=_parse_recipients(parsed),
                subject=_decode_mime_header(parsed.get("Subject")),
                body=_extract_body(parsed),
                received_at=parsed.get("Date", ""),
            )
        finally:
            connection.logout()

    async def read_message(self, message_id: str) -> EmailMessage:
        """See `EmailPort.read_message`. Runs the real, blocking IMAP call off the event loop.

        Raises:
            EmailMessageNotFoundError: If ``message_id`` matches no
                real message in ``INBOX``.
        """
        return await asyncio.to_thread(self._read_message_sync, message_id)

    async def send_message(self, to: tuple[str, ...], subject: str, body: str) -> None:
        """Always raises -- see `EmailPort.send_message`'s own docstring for why."""
        del to, subject, body
        msg = (
            "EmailPort.send_message is not implemented in this codebase -- blocked on "
            "ADR-0057's own pending review (Proposed, not Accepted). No SMTP call is made."
        )
        raise NotImplementedError(msg)
