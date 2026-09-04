"""The email port: the seam between a real mailbox and this codebase.

:class:`EmailPort` covers both real protocol directions -- reading
(IMAP) and sending (SMTP) -- one port expressing the conceptual
capability ("email"), the same way `BrowserAutomationPort` already
bundles several distinct real CDP JSON-RPC domains behind one port
(`docs/architecture/m6a-communications.md`).

**Both halves are real, working implementations as of 2026-09-03**:
`list_messages`/`read_message` (WP-76/WP-77) and `send_message`
(WP-79 onward, following ADR-0057's Acceptance -- 2026-09-03, directly
by the user, in conversation, after direct review of the ADR's own
full text). Real, per-invocation `Effect`/`Tier` classification for
`send_message` (`application/communications/classification.py::egress_effect_for`)
happens at the composition-root layer (`kernel/communications.py`),
before any real adapter method is ever called -- this Protocol itself
declares no authorization, matching every other port in this repo.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.email`` for the concrete
IMAP/SMTP-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.email import EmailMessage, EmailSummary


class EmailMessageNotFoundError(Exception):
    """Raised when no real message matches the identifier a caller asked for.

    Defined on the port rather than the adapter so that any future,
    non-IMAP implementation of this port raises the same,
    technology-independent type, matching
    :class:`~jarvis.ports.memory_write.MemoryRecordNotFoundError`'s
    reasoning.
    """


class EmailConnectionError(Exception):
    """Raised when a real mailbox connection fails or is lost mid-session.

    Found by real resilience testing (property-matrix/fuzzing/
    concurrency-adjacent pass, adapter-resilience Track 1, 2026-09-04):
    unlike every other real network-facing adapter in this codebase
    (``urllib``/``requests``-backed ones, whose connectivity failures
    are all real ``OSError`` subclasses, already caught cleanly by
    ``cli/main.py``'s and ``kernel/voice_loop.py``'s own broad except
    tuples), Python's stdlib ``imaplib`` raises its own
    ``IMAP4.error``/``IMAP4.abort`` hierarchy for connection and
    protocol-level failures -- a bare ``Exception`` subclass, not an
    ``OSError`` one. A real, confirmed-by-test connection genuinely
    established and then lost mid-session (the real server stopped)
    raised a raw, uncaught-shaped ``imaplib.IMAP4.abort`` before this
    fix, which would have bypassed every existing broad except tuple
    in this codebase the moment a real caller (CLI or voice grammar)
    is ever wired up for ``communications.list_email``/``read_email``
    (neither is wired to a real entry point yet, but the gap was real
    regardless of whether it had a live caller today). Defined on the
    port, not the adapter, for the same technology-independence
    reasoning as :class:`EmailMessageNotFoundError`.
    """


@runtime_checkable
class EmailPort(Protocol):
    """A real mailbox this codebase can list, read, and send through."""

    async def list_messages(self, folder: str, limit: int) -> tuple[EmailSummary, ...]:
        """Return up to ``limit`` real message summaries from ``folder``, most recent first.

        No authorization happens inside this method -- matching every
        other port in this repo, this is a pure mechanism. Real
        `Tier.ALLOW` authorization happens at the composition-root
        layer (`kernel/communications.py`), before this is ever
        called.
        """
        ...

    async def read_message(self, message_id: str) -> EmailMessage:
        """Return the real, full content of the message identified by ``message_id``.

        Raises:
            EmailMessageNotFoundError: If ``message_id`` matches no
                real message.
        """
        ...

    async def send_message(self, to: tuple[str, ...], subject: str, body: str) -> None:
        """Send a real email to ``to`` with ``subject``/``body``.

        No authorization happens inside this method -- matching every
        other port in this repo, this is a pure mechanism. Real
        `Effect`/`Tier` classification and authorization
        (`egress_effect_for`, ADR-0057) happens at the composition-root
        layer (`kernel/communications.py`), before this is ever called;
        this method never runs unless that call's own `Decision.granted`
        is `True`.
        """
        ...
