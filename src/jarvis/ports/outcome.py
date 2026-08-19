"""The outcome sink port: the seam between structured engineering telemetry and real storage.

:class:`OutcomeSinkPort` is deliberately generic (one method, a plain
mapping) -- the M2-specific shape of what gets recorded
(:class:`~jarvis.application.reasoning.outcome_logger.Outcome`: which
rung, how long, pass/fail) is owned entirely by
:class:`~jarvis.application.reasoning.outcome_logger.OutcomeLogger`,
not by this port. Per ADR-0039, this port's real implementations must
never become a second, unaudited record of an authorization-relevant
event -- see that ADR and ``outcome_logger.py``'s own docstring for
the full reasoning.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.outcome`` for the
concrete JSON-lines-file adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping


@runtime_checkable
class OutcomeSinkPort(Protocol):
    """A real place to durably record one structured, non-authoritative telemetry entry."""

    def record(self, entry: Mapping[str, object]) -> None:
        """Durably record ``entry``.

        Args:
            entry: A plain, JSON-serializable mapping. What it
                contains is entirely the caller's business -- this
                port neither validates nor interprets it.
        """
        ...
