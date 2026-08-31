"""Unit tests for jarvis.adapters.memory.SqliteMemoryAdapter.

Uses a fake, deterministic EmbeddingPort throughout -- this adapter's
own real FastEmbedAdapter is exercised only in a real, manual
verification pass (see docs/threat-model/v0.md's "Milestone 4
additions"), matching this project's established precedent for
network/hardware-dependent adapters.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import pytest

from jarvis.adapters.memory import SqliteMemoryAdapter, UnsupportedMemoryValueError
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.ports.memory_write import MemoryRecordNotFoundError
from jarvis.ports.retrieval import MemoryIntegrityViolationError

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeEmbeddingPort:
    """Maps known strings to hand-picked vectors so similarity ordering is fully controlled."""

    _VECTORS: ClassVar[dict[str, tuple[float, ...]]] = {
        "tabs": (1.0, 0.0),
        "rust": (0.0, 1.0),
        "tabs query": (0.9, 0.1),
        "rust query": (0.1, 0.9),
    }

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._VECTORS.get(text, (0.0, 0.0)) for text in texts)


class _FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set_now(self, now: datetime) -> None:
        self._now = now


class _SequentialIdPort:
    def __init__(self) -> None:
        self._counter = 0

    def new_id(self) -> str:
        self._counter += 1
        return f"mem:{self._counter}"


def _adapter(clock: _FakeClock | None = None) -> SqliteMemoryAdapter:
    return SqliteMemoryAdapter(
        ":memory:", _FakeEmbeddingPort(), clock or _FakeClock(_NOW), _SequentialIdPort()
    )


def _file_adapter(database_path: Path, clock: _FakeClock | None = None) -> SqliteMemoryAdapter:
    """A real, file-backed adapter -- needed to inspect raw storage via a second connection.

    ``:memory:`` databases are private to their own connection, so
    ``sweep_expired()``'s own "actually gone from storage, not just
    excluded from queries" guarantee can only be checked from outside
    the adapter by opening a second, real connection to a real file.
    """
    return SqliteMemoryAdapter(
        str(database_path), _FakeEmbeddingPort(), clock or _FakeClock(_NOW), _SequentialIdPort()
    )


def _raw_row_count(database_path: Path) -> int:
    """Query the real underlying table directly, bypassing the adapter entirely."""
    connection = sqlite3.connect(database_path)
    try:
        (count,) = connection.execute("SELECT COUNT(*) FROM memory_records").fetchone()
        return int(count)
    finally:
        connection.close()


def _value(text: str, classification: Classification = Classification.PUBLIC) -> Tainted[object]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted(text, provenance)


def test_write_returns_a_new_identifier() -> None:
    adapter = _adapter()

    identifier = adapter.write(_value("tabs"))

    assert identifier == "mem:1"


def test_write_rejects_a_non_string_value() -> None:
    adapter = _adapter()
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
    )

    with pytest.raises(UnsupportedMemoryValueError):
        adapter.write(Tainted(42, provenance))


def test_written_record_is_retrievable_by_a_similar_query() -> None:
    adapter = _adapter()
    adapter.write(_value("tabs"))
    adapter.write(_value("rust"))

    results = adapter.retrieve("tabs query", limit=1)

    assert len(results) == 1
    assert results[0].value.value == "tabs"


def test_retrieve_ranks_by_similarity_descending() -> None:
    adapter = _adapter()
    adapter.write(_value("rust"))
    adapter.write(_value("tabs"))

    results = adapter.retrieve("tabs query", limit=2)

    assert [record.value.value for record in results] == ["tabs", "rust"]


def test_retrieve_respects_limit() -> None:
    adapter = _adapter()
    adapter.write(_value("tabs"))
    adapter.write(_value("rust"))

    results = adapter.retrieve("tabs query", limit=1)

    assert len(results) == 1


def test_retrieve_returns_empty_tuple_when_store_is_empty() -> None:
    adapter = _adapter()

    assert adapter.retrieve("anything", limit=5) == ()


def test_pin_sets_expires_at_to_none() -> None:
    clock = _FakeClock(_NOW)
    adapter = _adapter(clock)
    identifier = adapter.write(_value("tabs"))

    adapter.pin(identifier)
    clock.set_now(_NOW + timedelta(days=36500))

    results = adapter.retrieve("tabs query", limit=1)
    assert len(results) == 1
    assert results[0].expires_at is None


def test_pin_raises_for_an_unknown_identifier() -> None:
    adapter = _adapter()

    with pytest.raises(MemoryRecordNotFoundError):
        adapter.pin("mem:does-not-exist")


def test_sweep_expired_deletes_an_expired_unpinned_record_from_real_storage(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "memory.sqlite3"
    clock = _FakeClock(_NOW)
    adapter = _file_adapter(database_path, clock)
    adapter.write(_value("tabs"))

    clock.set_now(_NOW + timedelta(days=91))
    deleted = adapter.sweep_expired()

    assert deleted == 1
    assert _raw_row_count(database_path) == 0


def test_sweep_expired_leaves_a_pinned_record_in_real_storage(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    clock = _FakeClock(_NOW)
    adapter = _file_adapter(database_path, clock)
    identifier = adapter.write(_value("tabs"))
    adapter.pin(identifier)

    clock.set_now(_NOW + timedelta(days=36500))
    deleted = adapter.sweep_expired()

    assert deleted == 0
    assert _raw_row_count(database_path) == 1


def test_sweep_expired_leaves_an_unexpired_record_in_real_storage(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path, _FakeClock(_NOW))
    adapter.write(_value("tabs"))

    deleted = adapter.sweep_expired()

    assert deleted == 0
    assert _raw_row_count(database_path) == 1


def test_sweep_expired_returns_zero_when_nothing_is_expired() -> None:
    adapter = _adapter()

    assert adapter.sweep_expired() == 0


def test_sweep_expired_only_deletes_expired_records_leaving_others_intact(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "memory.sqlite3"
    clock = _FakeClock(_NOW)
    adapter = _file_adapter(database_path, clock)
    adapter.write(_value("tabs"))
    clock.set_now(_NOW + timedelta(days=91))
    adapter.write(_value("rust"))

    deleted = adapter.sweep_expired()

    assert deleted == 1
    assert _raw_row_count(database_path) == 1


def test_forget_deletes_the_record_from_real_storage(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path)
    identifier = adapter.write(_value("tabs"))

    adapter.forget(identifier)

    assert _raw_row_count(database_path) == 0


def test_forget_raises_for_an_unknown_identifier() -> None:
    adapter = _adapter()

    with pytest.raises(MemoryRecordNotFoundError):
        adapter.forget("mem:does-not-exist")


def test_forget_deletes_a_pinned_record_too(tmp_path: Path) -> None:
    """Pinning protects against automatic TTL expiry, not an explicit, targeted forget."""
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path)
    identifier = adapter.write(_value("tabs"))
    adapter.pin(identifier)

    adapter.forget(identifier)

    assert _raw_row_count(database_path) == 0


def test_forget_leaves_other_records_intact(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path)
    forgotten = adapter.write(_value("tabs"))
    adapter.write(_value("rust"))

    adapter.forget(forgotten)

    assert _raw_row_count(database_path) == 1


def test_expired_unpinned_record_is_not_returned() -> None:
    clock = _FakeClock(_NOW)
    adapter = _adapter(clock)
    adapter.write(_value("tabs"))

    clock.set_now(_NOW + timedelta(days=91))

    assert adapter.retrieve("tabs query", limit=5) == ()


def test_secret_record_is_excluded_and_raises() -> None:
    adapter = _adapter()
    adapter.write(_value("tabs", Classification.SECRET))

    with pytest.raises(MemoryIntegrityViolationError):
        adapter.retrieve("tabs query", limit=5)


def test_a_zero_vector_embedding_never_raises_a_division_error() -> None:
    """An unmapped/zero-magnitude embedding is treated as zero similarity, not a crash."""
    adapter = _adapter()
    adapter.write(_value("unmapped text with no fake vector"))

    results = adapter.retrieve("tabs query", limit=1)

    assert len(results) == 1


def test_provenance_is_carried_forward_unchanged() -> None:
    adapter = _adapter()
    original = _value("tabs", Classification.SENSITIVE)
    adapter.write(original)

    results = adapter.retrieve("tabs query", limit=1)

    assert results[0].value.provenance == original.provenance
