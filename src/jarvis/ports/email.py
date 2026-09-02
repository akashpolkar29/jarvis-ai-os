"""The email port: the seam between a real mailbox and this codebase.

:class:`EmailPort` covers both real protocol directions -- reading
(IMAP) and sending (SMTP) -- one port expressing the conceptual
capability ("email"), the same way `BrowserAutomationPort` already
bundles several distinct real CDP JSON-RPC domains behind one port
(`docs/architecture/m6a-communications.md`).

**Real, deliberate scope limit for this pass, not the port's own
permanent shape**: only the read half (`list_messages`/`read_message`)
has a real, working implementation anywhere in this codebase today.
`send_message` exists on this Protocol because `EmailPort` is
conceptually one port for "email," but every real adapter's own
`send_message` method raises `NotImplementedError` -- sending requires
a real `Effect`/`Tier` classification decision
(`application/communications/classification.py::egress_effect_for`,
ADR-0057) that has not been reviewed by the user directly and remains
`Proposed`, not `Accepted`. No real SMTP call exists anywhere in this
codebase as a result -- not gated, not DENY-classified, simply never
implemented, the same "the mechanism does not exist" discipline
ADR-0058 uses for M6b's own submission boundary, applied here for the
identical real reason (an unreviewed classification decision, not a
structural product decision).

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.email`` for the concrete
IMAP-backed adapter that satisfies this port's read half.
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


@runtime_checkable
class EmailPort(Protocol):
    """A real mailbox this codebase can list, read, and (once ADR-0057 is Accepted) send through."""

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
        """Not implemented by any real adapter in this codebase -- see this module's own docstring.

        Every real adapter's own implementation raises
        ``NotImplementedError`` unconditionally, before any real SMTP
        connection is ever attempted. This Protocol method exists so
        `EmailPort` can express the conceptual, eventual full shape of
        "email" in one place -- it is not a promise that a real send
        path exists today.

        Raises:
            NotImplementedError: Always, until ADR-0057 is reviewed
                and Accepted and a real work package implements this
                for real.
        """
        ...
