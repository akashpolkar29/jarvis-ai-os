"""The clock port: the one real source of wall-clock time this project allows.

:class:`ClockPort` is the port ADR-0054 closes -- this project's own
tooling-enforced invariant ("no direct wall-clock access anywhere in
`src/` -- inject `ClockPort` instead") presupposed this port since
before it, but nothing had ever actually built it until M4's own
retention mechanics (ADR-0051) needed real wall-clock time for the
first time.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.clock`` for the concrete
adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime


@runtime_checkable
class ClockPort(Protocol):
    """A real source of the current wall-clock time."""

    def now(self) -> datetime:
        """Return the real, current wall-clock time (UTC, timezone-aware)."""
        ...
