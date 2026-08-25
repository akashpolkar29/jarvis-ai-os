"""The retrieval port: searching real, previously-memorized content.

:class:`RetrievalPort` is the other of ADR-0048's two new M4 ports.
Deliberately performs no tier-based gating itself -- per ADR-0050, a
recalled value's own classification is re-evaluated by the *caller*,
at the point it's used in a new capability invocation, not filtered
here. The one exception, per ADR-0050's own amendment: a
``Classification.SECRET`` record is never returned, unconditionally --
see :class:`MemoryIntegrityViolationError`'s own docstring for why
that one case is different in kind, not degree.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.memory`` for the
concrete adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.memory import MemoryRecord


class MemoryIntegrityViolationError(Exception):
    """Raised when a ``Classification.SECRET`` record is found during retrieval.

    Per ADR-0049, a SECRET-classified value should structurally never
    reach the real store at all -- if one is found here regardless (a
    bug, a pre-ADR-0049 legacy write, a classification computed
    incorrectly at write time), that is not a routine authorization
    decision this port silently handles; it is evidence ADR-0049's own
    write-time guarantee was bypassed somewhere. Raised *after* the
    real adapter has already excluded the record from its returned
    results (ADR-0050's own amendment) -- the caller's query still
    completes safely with no SECRET content ever reaching it, but the
    anomaly itself is never silently swallowed either.
    """


@runtime_checkable
class RetrievalPort(Protocol):
    """A real, searchable store of previously-memorized content."""

    def retrieve(self, query: str, *, limit: int) -> tuple[MemoryRecord, ...]:
        """Return up to ``limit`` ``MemoryRecord``s ranked by relevance to ``query``.

        Each returned record carries its own real, unmodified
        ``Provenance`` -- this port does not gate anything based on
        classification; the caller re-evaluates each record's tier
        before using it (ADR-0050). Excludes records past their
        ``expires_at`` and not pinned (ADR-0051) -- an expired,
        unpinned record is indistinguishable from one that was never
        written, from this port's own caller's perspective.

        Args:
            query: The real search text.
            limit: The maximum number of records to return.

        Raises:
            MemoryIntegrityViolationError: If a ``Classification.SECRET``
                record was found and excluded during this query.
        """
        ...
