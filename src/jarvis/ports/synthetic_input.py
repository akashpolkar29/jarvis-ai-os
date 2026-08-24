"""The synthetic input port: real keyboard events via the RemoteDesktop portal.

:class:`SyntheticInputPort` is ADR-0047's accepted decision -- the
first mechanism in this codebase that can inject real keyboard events
reaching whatever the compositor currently has focused, system-wide,
not scoped to a specific accessible node the way
:meth:`~jarvis.ports.desktop_window.DesktopWindowPort.type_text`'s
``insert_text`` call is. See that ADR for the full design reasoning,
most importantly why this port deliberately knows nothing about
:class:`~jarvis.domain.desktop.WindowHandle`: a portal session is not
parameterized by a target window at all -- it fires at whatever has
compositor focus, full stop. Callers needing a specific target must
verify focus themselves, immediately before calling :meth:`SyntheticInputPort.send_keysym`
(``DesktopWindowPort.is_focused``, per the same ADR) -- this port
provides no such verification itself, and cannot: it has no concept of
a target window to verify against.

Scoped strictly to Terminal's typing step (ADR-0047's explicit scope
limit) -- reusing this for any other capability requires a separate,
explicit, future decision, not implied by this port's existence.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.synthetic_input`` for the
concrete RemoteDesktop-portal-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.desktop import SyntheticInputSession


class SyntheticInputUnavailableError(Exception):
    """Raised when a synthetic input session or keystroke cannot proceed safely.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: an
    adapter/orchestration-level, real-world operational condition (the
    portal is unreachable, the human denied the permission dialog, or
    -- raised by the calling orchestration, not this port itself --
    focus could not be verified before a keystroke), matching
    :class:`~jarvis.ports.secret.SecretNotFoundError`'s own reasoning
    for being defined on the port rather than the adapter. Deliberately
    a single error type covering both "the session could never be
    opened" and "focus was lost mid-command": from a caller's
    perspective both mean "this invocation cannot safely continue,"
    and ADR-0047's fail-closed requirement treats them identically --
    abort every remaining keystroke, never partially recover.
    """


@runtime_checkable
class SyntheticInputPort(Protocol):
    """A RemoteDesktop portal session that can inject real keyboard events."""

    def start_session(self, restore_token: str | None) -> SyntheticInputSession:
        """Open (or replay) a RemoteDesktop session.

        Args:
            restore_token: A previously-issued, persisted token to
                replay (skipping the interactive permission dialog), or
                ``None`` to request a fresh grant. If ``restore_token``
                is given but the portal rejects it as invalid or
                revoked, falls back to exactly one fresh interactive
                grant attempt -- never silently retried beyond that
                (ADR-0047's restore_token lifecycle).

        Returns:
            A real, open session. Its ``new_restore_token`` must be
            persisted by the caller (via ``SecretPort.set_secret``)
            whenever it is not ``None`` -- the portal may rotate the
            token on any call that issues one.

        Raises:
            SyntheticInputUnavailableError: If a human denies the
                resulting interactive dialog (whether this is the
                first-ever grant or the one fallback attempt after an
                invalid token), or no portal is reachable at all.
        """
        ...

    def send_keysym(self, session: SyntheticInputSession, keysym: int, *, press: bool) -> None:
        """Fire one NotifyKeyboardKeysym press or release event.

        Delivered to whatever the compositor currently has keyboard
        focus at the moment this call is processed -- this method has
        no concept of a target window and cannot be given one. Callers
        needing a specific target must verify focus themselves,
        immediately before calling this (ADR-0047's per-character
        focus-verification loop); this port performs no such
        verification and provides no way to.

        Args:
            session: A session already returned by :meth:`start_session`.
            keysym: The X11 keysym to send (keyboard-layout-independent,
                per ADR-0047's own reasoning for using keysyms over raw
                keycodes).
            press: ``True`` for a key-down event, ``False`` for
                key-up. Typing one character means one ``press=True``
                call immediately followed by one ``press=False`` call
                with the same ``keysym``.
        """
        ...
