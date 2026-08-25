"""The retrieval-side SECRET filter: ADR-0050's amendment, applied before any real adapter exists.

:func:`exclude_secret_records` is the one real, adapter-independent
piece of ADR-0050's amendment: an unconditional exclusion of any
``Classification.SECRET`` record from a query's returned results,
redundant with ADR-0049's write-time DENY on purpose (defense in
depth for this project's most sensitive classification).

Kept here, in ``application/memory/``, rather than inside a real
adapter under ``adapters/`` -- the filtering logic itself has nothing
to do with which storage technology WP-61 eventually chooses, so it is
built and fully tested now, against real ``MemoryRecord`` values,
exactly matching ``m4-memory-retrieval.md``'s own note that WP-59
"does not depend on a real vector store existing yet." WP-61's real
adapter calls this function on its own raw query results before
returning them, rather than reimplementing the same exclusion inline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.domain.provenance import Classification
from jarvis.ports.retrieval import MemoryIntegrityViolationError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from jarvis.domain.memory import MemoryRecord


def exclude_secret_records(records: Iterable[MemoryRecord]) -> tuple[MemoryRecord, ...]:
    """Return ``records`` with any ``Classification.SECRET`` record excluded.

    Per ADR-0050's own amendment: filtering happens first, building
    the clean result a caller could safely observe even if the
    subsequent raise is later caught and logged elsewhere -- SECRET
    content itself never appears in the returned tuple, only the fact
    that one was found and excluded is signaled, via the raise below,
    not silently dropped.

    Args:
        records: The real, unfiltered records a query matched.

    Returns:
        ``records``, in the same order, with any SECRET-classified
        record removed. Never actually returned to a caller if any
        such record was found -- see Raises below.

    Raises:
        MemoryIntegrityViolationError: If any record in ``records`` is
            ``Classification.SECRET``-classified. Per ADR-0049, this
            should never happen -- a SECRET value should never have
            reached storage at all. Encountering one here is evidence
            that guarantee was bypassed somewhere upstream, not a
            routine authorization outcome.
    """
    materialized = tuple(records)
    filtered = tuple(
        record
        for record in materialized
        if record.value.provenance.classification is not Classification.SECRET
    )
    if len(filtered) != len(materialized):
        msg = (
            "A Classification.SECRET record was found during retrieval and excluded -- "
            "this should be structurally impossible per ADR-0049's write-time DENY; "
            "its presence here indicates that guarantee was bypassed upstream."
        )
        raise MemoryIntegrityViolationError(msg)
    return filtered
