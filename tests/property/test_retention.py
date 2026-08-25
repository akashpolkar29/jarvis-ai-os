"""Property-based test for jarvis.application.memory.retention.exclude_expired_records.

The required acceptance criterion named directly by ADR-0051
("acceptance criterion 3", ``m4-memory-retrieval.md``): "an expired,
not-yet-swept record must never be returned" from ``RetrievalPort``,
checked directly by a real test -- not just a hand-picked example, but
across arbitrary combinations of expiry offsets and pin state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.memory.retention import exclude_expired_records
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.provenance import Tainted

_AT = datetime(2026, 1, 1, tzinfo=UTC)

_OFFSETS = st.integers(min_value=-10_000, max_value=10_000).map(
    lambda seconds: timedelta(seconds=seconds)
)
_EXPIRY = st.one_of(st.none(), _OFFSETS.map(lambda offset: _AT + offset))
_RECORD_SETS = st.lists(_EXPIRY, min_size=0, max_size=8)


def _record(index: int, expires_at: datetime | None) -> MemoryRecord:
    return MemoryRecord(
        identifier=f"mem:{index}",
        value=Tainted.user("x"),
        written_at=_AT,
        expires_at=expires_at,
    )


@given(_RECORD_SETS)
def test_a_record_survives_the_filter_if_and_only_if_it_is_not_expired(
    expiry_values: list[datetime | None],
) -> None:
    """No record whose is_expired(_AT) is True is ever present in the filtered result."""
    records = tuple(_record(index, expires_at) for index, expires_at in enumerate(expiry_values))

    result = exclude_expired_records(records, _AT)

    for record in records:
        should_survive = not record.is_expired(_AT)
        assert (record in result) is should_survive


@given(_RECORD_SETS)
def test_pinned_records_always_survive_regardless_of_how_far_in_the_future_at_is(
    expiry_values: list[datetime | None],
) -> None:
    """A pinned record (expires_at=None) survives no matter how far forward at is checked."""
    records = tuple(_record(index, expires_at) for index, expires_at in enumerate(expiry_values))
    far_future = _AT + timedelta(days=36500)

    result = exclude_expired_records(records, far_future)

    pinned = [record for record in records if record.expires_at is None]
    assert all(record in result for record in pinned)
