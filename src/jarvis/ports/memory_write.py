"""The memory write port: persisting a real, provenance-tagged value to memory.

:class:`MemoryWritePort` is one of ADR-0048's two new M4 ports --
writing to memory and reading from it are kept structurally separate,
since they have different authorization stories (ADR-0049 for write,
ADR-0050 for read).

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.memory`` for the
concrete adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.provenance import Tainted


class MemoryRecordNotFoundError(Exception):
    """Raised when ``pin()`` is given an identifier no real record matches.

    Defined on the port, not the adapter, matching
    :class:`~jarvis.ports.secret.SecretNotFoundError`'s own reasoning --
    a caller should not need to know which concrete adapter is behind
    the port to catch this. Deliberately not a silent no-op: a
    caller acting on a stale or mistyped identifier and believing a
    pin succeeded when nothing was pinned is exactly the class of bug
    this project has already been burned by once (an AppArmor denial
    silently swallowed as success, ``adapters/media_player.py``'s own
    docstring records the fix) -- not repeated here for a second,
    different mechanism.
    """


@runtime_checkable
class MemoryWritePort(Protocol):
    """A real, persistent store a provenance-tagged value can be written to."""

    def write(self, value: Tainted[object]) -> str:
        """Persist ``value`` to memory, provenance intact.

        No authorization happens inside this method -- matching every
        other port in this repo (``SecretPort``, ``MediaPlayerPort``,
        ``DesktopWindowPort``), this is a pure mechanism. A
        SECRET-classified value is never denied *by this call*: the
        composition root resolves ``memory_effect_for`` (ADR-0049) and
        checks ``AuthorizationOrchestrator``'s real ``Decision``
        *before* ever calling ``write()`` at all -- a denied write
        simply never reaches this method, the same "port method only
        runs after a granted Decision" shape every
        ``kernel/*.py`` composition function already follows.

        Real, necessary correction found during implementation, not
        present in ADR-0048's original code sketch: this method
        returns the new record's real, stable identifier rather than
        ``None`` -- without it, ``pin()`` below would have no way to
        reference the record it was just asked to write, making the
        accepted design uncallable in practice. A small, mechanical
        fix, not a change to this ADR's own reasoning.

        Returns:
            The new ``MemoryRecord``'s real, stable identifier.
        """
        ...

    def pin(self, identifier: str) -> None:
        """Mark the record at ``identifier`` as pinned -- never expires (ADR-0051).

        Sets the record's ``expires_at`` to ``None`` rather than
        extending it by a fixed window, matching ADR-0051's own
        "anything you want kept longer" framing. A no-op if the record
        is already pinned.

        Raises:
            MemoryRecordNotFoundError: If ``identifier`` does not
                match a real, currently-stored record.
        """
        ...
