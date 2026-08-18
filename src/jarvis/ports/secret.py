"""The secret port: the seam between a reference and a secret's real value.

:class:`SecretPort` is "the keyring adapter" ADR-0017 already presupposes
("Any code that needs a secret's actual value must go through the keyring
adapter at the point of use") but that, until ADR-0042, did not actually
exist anywhere in this codebase -- see that ADR for the full gap and why
it surfaced during WP-32, not earlier.

Only ``get_secret`` exists, matching :class:`~jarvis.ports.file_system.FileSystemPort`'s
"only what the real caller needs" minimalism: nothing in this repo needs
to write a new secret yet (a human provisions one out of band, e.g. via a
normal secrets tool), so no write path is built speculatively here.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.secret`` for the concrete
system-keyring-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class SecretNotFoundError(Exception):
    """Raised when no secret matches the reference a caller asked for.

    Not a :class:`~jarvis.domain.errors.JarvisError` subclass: this is
    an adapter-level, real-world operational condition (the keyring has
    nothing under this reference, or it does but a locked collection
    keeps it out of reach -- see ``jarvis.adapters.secret``'s docstring
    for why the two are not distinguished), not a domain-level
    security/policy concern. Defined on the port rather than the
    adapter so that any future, non-keyring implementation of this port
    raises the same, technology-independent type -- a caller should not
    need to know which concrete adapter is behind the port to catch
    this, matching :class:`~jarvis.ports.media_player.NoMediaPlayerRunningError`'s
    reasoning.
    """


@runtime_checkable
class SecretPort(Protocol):
    """A real system keyring a capability can resolve secret references against."""

    def get_secret(self, reference: str) -> str:
        """Return the real value of the secret referenced by ``reference``.

        Args:
            reference: An opaque, caller-chosen handle identifying which
                provisioned secret to resolve -- never the secret's
                value itself. Where a secret is stored under this
                reference, and how it got there, is out of this port's
                scope (ADR-0042).

        Raises:
            SecretNotFoundError: If no secret matches ``reference``.
        """
        ...
