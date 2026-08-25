"""Memory retention mechanics: 90-day default TTL, real ClockPort-derived timestamps (ADR-0051).

:func:`compute_write_timestamps` is the one place a new
:class:`~jarvis.domain.memory.MemoryRecord`'s ``written_at``/
``expires_at`` pair is derived -- both from a single
:class:`~jarvis.ports.clock.ClockPort` read, never
``datetime.now()`` directly, matching this project's own
tooling-enforced invariant. A single ``clock.now()`` call anchors both
fields, rather than two separate reads that could observe different
instants.

:func:`exclude_expired_records` is the adapter-independent half of
ADR-0051's retrieval-side guarantee -- "an expired, not-yet-swept
record must never be returned" -- built and tested now, against real
``MemoryRecord`` values, the same "does not depend on a real vector
store existing yet" ordering WP-59's ``exclude_secret_records``
already established. WP-61's real adapter calls both this and
``exclude_secret_records`` on its raw query results before returning
them.

A pinned record (``expires_at is None``) is never expired --
``MemoryRecord.is_expired()`` (ADR-0048) already encodes this; this
module adds no separate pinned-record special case of its own.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from jarvis.domain.memory import MemoryRecord
    from jarvis.ports.clock import ClockPort

DEFAULT_RETENTION = timedelta(days=90)
"""ADR-0051's own real default -- named here once, not a magic literal at each call site.

Whether 90 days is the right real default is explicitly named in
ADR-0051 as empirical, not fixed permanently -- this is the one place
that value would change.
"""


def compute_write_timestamps(clock: ClockPort) -> tuple[datetime, datetime]:
    """Return ``(written_at, expires_at)`` for a new record, both derived from one clock read.

    Args:
        clock: The real source of wall-clock time -- never
            ``datetime.now()`` called directly here or anywhere else
            in this milestone's code.

    Returns:
        ``written_at`` is ``clock.now()``; ``expires_at`` is
        ``written_at + DEFAULT_RETENTION``. A caller wanting a pinned
        record from the start simply discards this ``expires_at`` and
        passes ``None`` to ``MemoryRecord`` instead -- this function
        always computes the default-TTL case.
    """
    written_at = clock.now()
    return written_at, written_at + DEFAULT_RETENTION


def exclude_expired_records(
    records: Iterable[MemoryRecord], at: datetime
) -> tuple[MemoryRecord, ...]:
    """Return ``records`` with any record expired as of ``at`` excluded.

    Args:
        records: The real, unfiltered records a query matched.
        at: The real current time to check expiry against -- caller-
            supplied (from a real ``ClockPort``), matching
            ``MemoryRecord.is_expired()``'s own "stays a pure function"
            convention.

    Returns:
        ``records``, in the same order, with any record whose
        ``is_expired(at)`` is ``True`` removed. A pinned record
        (``expires_at is None``) is never excluded by this function.
    """
    return tuple(record for record in records if not record.is_expired(at))
