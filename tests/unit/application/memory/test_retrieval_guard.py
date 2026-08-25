"""Unit tests for jarvis.application.memory.retrieval_guard.exclude_secret_records."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jarvis.application.memory.retrieval_guard import exclude_secret_records
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.ports.retrieval import MemoryIntegrityViolationError

_WRITTEN_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _record(identifier: str, classification: Classification) -> MemoryRecord:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return MemoryRecord(
        identifier=identifier,
        value=Tainted("x", provenance),
        written_at=_WRITTEN_AT,
        expires_at=None,
    )


def test_returns_all_records_unchanged_when_none_are_secret() -> None:
    records = (
        _record("mem:1", Classification.PUBLIC),
        _record("mem:2", Classification.SENSITIVE),
    )

    result = exclude_secret_records(records)

    assert result == records


def test_raises_when_a_secret_record_is_present() -> None:
    records = (
        _record("mem:1", Classification.PUBLIC),
        _record("mem:2", Classification.SECRET),
    )

    with pytest.raises(MemoryIntegrityViolationError):
        exclude_secret_records(records)


def test_raises_even_when_every_record_is_secret() -> None:
    records = (_record("mem:1", Classification.SECRET),)

    with pytest.raises(MemoryIntegrityViolationError):
        exclude_secret_records(records)


def test_returns_empty_tuple_for_empty_input() -> None:
    assert exclude_secret_records(()) == ()


def test_preserves_order_of_non_secret_records() -> None:
    records = (
        _record("mem:1", Classification.PUBLIC),
        _record("mem:2", Classification.PERSONAL),
        _record("mem:3", Classification.SENSITIVE),
    )

    result = exclude_secret_records(records)

    assert [record.identifier for record in result] == ["mem:1", "mem:2", "mem:3"]
