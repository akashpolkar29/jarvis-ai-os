"""The identifier port: the one real source of fresh, unique identifiers this project allows.

:class:`IdPort` is the port ADR-0054 closes, alongside :class:`~jarvis.ports.clock.ClockPort`
-- this project's own tooling-enforced invariant ("no direct
randomness-based identifier generation anywhere in `src/` -- inject
`IdPort` instead") presupposed this port since before it, but nothing
had ever actually built it until M4's own `MemoryRecord` (ADR-0048)
needed a real, fresh identifier for the first time.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.identifier`` for the
concrete adapter that satisfies this port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IdPort(Protocol):
    """A real source of fresh, unique identifiers."""

    def new_id(self) -> str:
        """Return a real, fresh, unique identifier."""
        ...
