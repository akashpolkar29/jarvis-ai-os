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

    def get_by_identifier(self, identifier: str) -> MemoryRecord | None:
        """Return the one real record at ``identifier``, or ``None`` if no such record exists.

        The real, direct, O(1)-by-key counterpart to :meth:`retrieve`'s
        similarity search (WP-107) -- for a caller that already knows
        exactly which record it wants (a ``Task``'s own id), a broad
        semantic query-then-filter is the wrong tool: it is only ever
        an approximation (a store large enough can rank the wanted
        record below the query's own ``limit``, a real, already-named
        limitation ``job_application.list``/``project.py`` both
        inherited). This method has no such limitation -- a lookup by
        the real, unique primary key either finds the record or it
        does not.

        Applies the same two real, required retrieval-time guarantees
        :meth:`retrieve` applies, for the identical reasons: a
        ``Classification.SECRET`` record is never returned (ADR-0050's
        own amendment), and an expired, unpinned record is treated as
        not found, not returned stale (ADR-0051).

        Args:
            identifier: The real identifier to look up.

        Returns:
            The matching ``MemoryRecord``, or ``None`` if no record
            exists at ``identifier``, or if it exists but is expired
            and unpinned.

        Raises:
            MemoryIntegrityViolationError: If the record at
                ``identifier`` is ``Classification.SECRET``.
        """
        ...
