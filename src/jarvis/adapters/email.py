"""Adapters implementing jarvis.ports.email.EmailPort.

:class:`ImapEmailAdapter` is WP-77's own real implementation of the
port's read half (`list_messages`/`read_message`) via `imaplib`
(standard library, per `m6a-communications.md`'s own stdlib-only
decision). **Updated 2026-09-03 (WP-79 onward, following ADR-0057's
Acceptance)**: `send_message` is now a real implementation too, via
`smtplib` (standard library, the same stdlib-only decision the design
doc already made). The class keeps its original name -- `ImapEmailAdapter`
-- rather than the design doc's own `ImapSmtpEmailAdapter` sketch, a
real, deliberate, minimal-footprint choice: renaming would touch every
existing real caller/test for no functional benefit; the docstring
below states plainly what the name no longer fully describes.

`imaplib.IMAP4_SSL`/`smtplib.SMTP_SSL` are both blocking, synchronous
clients with no async twin in the standard library; every real method
here wraps its own blocking call in `asyncio.to_thread` so `EmailPort`'s
own async interface is honored without blocking the event loop.

Message parsing uses the standard library's own `email` package
(`email.message_from_bytes`), not hand-rolled header/MIME parsing --
the same "use the real, correct stdlib tool" discipline this project
already applies elsewhere (`configparser`/`tomllib` for
`application/coding/classification.py`'s own real config-file
detection). The outgoing message `send_message` builds uses
`email.message.EmailMessage` (the modern stdlib API), aliased to
`MimeEmailMessage` in this module to avoid colliding with
`jarvis.domain.email.EmailMessage`, an unrelated real dataclass.
"""

from __future__ import annotations

import asyncio
import email as email_stdlib
import imaplib
import smtplib
from email.header import decode_header
from email.message import EmailMessage as MimeEmailMessage
from email.utils import parseaddr
from typing import TYPE_CHECKING, Protocol

from jarvis.domain.email import EmailMessage, EmailSummary
from jarvis.ports.email import EmailConnectionError, EmailMessageNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
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


class _SmtpConnection(Protocol):
    """The narrow subset of smtplib.SMTP_SSL's own real interface this adapter uses.

    Real return types confirmed via `mypy --strict`'s own `reveal_type`
    against typeshed's stdlib stubs, matching `_ImapConnection`'s own
    established discipline.
    """

    def login(self, user: str, password: str) -> tuple[int, bytes]: ...
    def send_message(
        self,
        msg: MimeEmailMessage,
        from_addr: str | None = ...,
        to_addrs: Sequence[str] | None = ...,
    ) -> dict[str, tuple[int, bytes]]: ...
    def quit(self) -> tuple[int, bytes]: ...


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
    """A real, IMAP-backed `EmailPort` read half, SMTP-backed `send_message` write half."""

    def __init__(  # noqa: PLR0913, PLR0917 -- one per real, distinct credential/connection concern
        self,
        host: str,
        username: str,
        secret: SecretPort,
        password_reference: str,
        smtp_host: str,
        connection_factory: Callable[[str], _ImapConnection] | None = None,
        smtp_connection_factory: Callable[[str], _SmtpConnection] | None = None,
    ) -> None:
        """Store how to connect and how to resolve the real credential -- no I/O at construction.

        Args:
            host: The real IMAP server hostname.
            username: The real mailbox username -- reused as the SMTP
                login username and the outgoing message's own ``From``
                address; most real providers use one account for both
                protocols.
            secret: Resolves ``password_reference`` to a real password
                at the point of use (ADR-0017, ADR-0042) -- never
                stored as a field, never read at construction time.
                Reused for both the IMAP and SMTP login.
            password_reference: The keyring reference for this
                mailbox's password.
            smtp_host: The real SMTP server hostname. Required, no
                default -- most real providers use a genuinely
                different hostname than the IMAP server (e.g.
                ``imap.example.com`` vs ``smtp.example.com``); assuming
                they match would be a real, silent misconfiguration
                risk for a real deployment, not a safe simplification.
            connection_factory: Given the IMAP host, returns a real,
                unauthenticated connection object. Defaults to
                ``imaplib.IMAP4_SSL``. Overridable for tests -- no
                real network connection is made until a real method is
                called.
            smtp_connection_factory: Given the SMTP host, returns a
                real, unauthenticated connection object. Defaults to
                ``smtplib.SMTP_SSL``. Overridable for tests -- no real
                network connection is made until a real method is
                called.
        """
        self._host = host
        self._username = username
        self._secret = secret
        self._password_reference = password_reference
        self._smtp_host = smtp_host
        # A lambda, not the bare class, deliberately: mypy --strict does not
        # accept `type[IMAP4_SSL]` directly where `Callable[[str], _ImapConnection]`
        # is expected, even though the call signature is structurally
        # identical -- a real mypy quirk around class-object callables,
        # confirmed by direct testing, not a style preference.
        self._connection_factory: Callable[[str], _ImapConnection] = (
            connection_factory or (lambda host: imaplib.IMAP4_SSL(host))  # noqa: PLW0108
        )
        self._smtp_connection_factory: Callable[[str], _SmtpConnection] = (
            smtp_connection_factory or (lambda host: smtplib.SMTP_SSL(host))  # noqa: PLW0108
        )

    def _connect(self) -> _ImapConnection:
        connection = self._connection_factory(self._host)
        password = self._secret.get_secret(self._password_reference)
        connection.login(self._username, password)
        return connection

    def _list_messages_sync(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        try:
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
        except imaplib.IMAP4.error as exc:
            msg = f"Real IMAP connection to {self._host!r} failed or was lost: {exc}"
            raise EmailConnectionError(msg) from exc

    async def list_messages(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        """See `EmailPort.list_messages`. Runs the real, blocking IMAP call off the event loop."""
        return await asyncio.to_thread(self._list_messages_sync, folder, limit)

    def _read_message_sync(self, message_id: str) -> EmailMessage:
        try:
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
        except imaplib.IMAP4.error as exc:
            msg = f"Real IMAP connection to {self._host!r} failed or was lost: {exc}"
            raise EmailConnectionError(msg) from exc

    async def read_message(self, message_id: str) -> EmailMessage:
        """See `EmailPort.read_message`. Runs the real, blocking IMAP call off the event loop.

        Raises:
            EmailMessageNotFoundError: If ``message_id`` matches no
                real message in ``INBOX``.
        """
        return await asyncio.to_thread(self._read_message_sync, message_id)

    def _send_message_sync(self, to: tuple[str, ...], subject: str, body: str) -> None:
        connection = self._smtp_connection_factory(self._smtp_host)
        password = self._secret.get_secret(self._password_reference)
        try:
            connection.login(self._username, password)
            message = MimeEmailMessage()
            message["From"] = self._username
            message["To"] = ", ".join(to)
            message["Subject"] = subject
            message.set_content(body)
            connection.send_message(message, self._username, list(to))
        finally:
            connection.quit()

    async def send_message(self, to: tuple[str, ...], subject: str, body: str) -> None:
        """See `EmailPort.send_message`. Runs the real, blocking SMTP call off the event loop.

        Real, per-invocation classification/authorization
        (`egress_effect_for`, ADR-0057) happens entirely at the
        composition-root layer (`kernel/communications.py`), before
        this is ever called -- matching `list_messages`'/`read_message`'s
        own identical "pure mechanism, no authorization here" contract.
        """
        await asyncio.to_thread(self._send_message_sync, to, subject, body)
