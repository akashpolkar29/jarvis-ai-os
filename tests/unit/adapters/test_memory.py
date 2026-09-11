"""Unit tests for jarvis.adapters.memory.SqliteMemoryAdapter.

Uses a fake, deterministic EmbeddingPort throughout -- this adapter's
own real FastEmbedAdapter is exercised only in a real, manual
verification pass (see docs/threat-model/v0.md's "Milestone 4
additions"), matching this project's established precedent for
network/hardware-dependent adapters.
"""

from __future__ import annotations

import sqlite3
import threading
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


def _provenance(classification: Classification = Classification.PUBLIC) -> Provenance:
    return Provenance(trust=Trust.USER_DIRECT, classification=classification, sources=frozenset())


def test_write_rejects_a_non_json_serializable_value() -> None:
    """A value with no real JSON representation (a custom object) is rejected, not silently
    coerced -- see module docstring for why the boundary is "JSON-serializable", not "str"."""
    adapter = _adapter()

    class _NotJsonSerializable:
        pass

    with pytest.raises(UnsupportedMemoryValueError):
        adapter.write(Tainted(_NotJsonSerializable(), _provenance()))


@pytest.mark.parametrize(
    "value",
    [42, 3.14, True, False, None, [1, 2, 3], {"key": "value"}],
    ids=["int", "float", "bool_true", "bool_false", "none", "list", "dict"],
)
def test_write_accepts_every_json_serializable_type_and_round_trips_it(value: object) -> None:
    """Overnight Track 5 pass: JSON-serializable non-str values are now real, supported memories."""
    adapter = _adapter()

    identifier = adapter.write(Tainted(value, _provenance()))
    results = adapter.retrieve("anything", limit=5)

    assert len(results) == 1
    assert results[0].identifier == identifier
    assert results[0].value.value == value
    assert type(results[0].value.value) is type(value)


def test_a_pre_migration_row_with_no_value_json_still_reads_back_as_its_own_raw_text(
    tmp_path: Path,
) -> None:
    """Real backward compatibility: a row written before value_json existed (simulated here by
    inserting directly, bypassing the adapter) is still read back correctly, not corrupted."""
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path)
    # Force the migration to have already run, then simulate a legacy row by
    # inserting directly with value_json left NULL -- the real, pre-Track-5 shape.
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "INSERT INTO memory_records "
            "(identifier, text, embedding, trust, classification, sources, written_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "mem:legacy",
                "a legacy str memory",
                "[1.0, 0.0]",
                int(Trust.USER_DIRECT),
                int(Classification.PUBLIC),
                "[]",
                "2026-01-01T00:00:00+00:00",
                "2026-04-01T00:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    results = adapter.retrieve("anything", limit=5)

    assert len(results) == 1
    assert results[0].value.value == "a legacy str memory"


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


def _obj_value(payload: object) -> Tainted[object]:
    """Like `_value`, but for a non-`str` payload -- `_value` itself is typed to `str` only."""
    return Tainted(payload, _provenance())


def test_compare_and_update_value_succeeds_when_expected_matches(tmp_path: Path) -> None:
    """WP-120: the common, single-process, no-contention case -- the comparison matches."""
    adapter = _file_adapter(tmp_path / "memory.sqlite3")
    identifier = adapter.write(_obj_value({"status": "created"}))

    applied = adapter.compare_and_update_value(
        identifier, {"status": "created"}, _obj_value({"status": "running"})
    )

    assert applied is True
    record = adapter.get_by_identifier(identifier)
    assert record is not None
    assert record.value.value == {"status": "running"}


def test_compare_and_update_value_returns_false_when_expected_does_not_match(
    tmp_path: Path,
) -> None:
    """A real, honest "lost the race" signal -- never an exception, storage left untouched."""
    adapter = _file_adapter(tmp_path / "memory.sqlite3")
    identifier = adapter.write(_obj_value({"status": "running"}))

    applied = adapter.compare_and_update_value(
        identifier, {"status": "created"}, _obj_value({"status": "running-again"})
    )

    assert applied is False
    record = adapter.get_by_identifier(identifier)
    assert record is not None
    assert record.value.value == {"status": "running"}


def test_compare_and_update_value_returns_false_for_an_unknown_identifier() -> None:
    adapter = _adapter()

    applied = adapter.compare_and_update_value(
        "mem:does-not-exist", {"status": "created"}, _obj_value({"status": "running"})
    )

    assert applied is False


def test_compare_and_update_value_rejects_a_non_json_serializable_new_value() -> None:
    """Checked before the real write lock is ever acquired -- mirrors update_value's own rule."""
    adapter = _adapter()
    identifier = adapter.write(_obj_value({"status": "created"}))

    class _NotJsonSerializable:
        pass

    with pytest.raises(UnsupportedMemoryValueError):
        adapter.compare_and_update_value(
            identifier, {"status": "created"}, Tainted(_NotJsonSerializable(), _provenance())
        )


def test_compare_and_update_value_rolls_back_and_reraises_on_a_real_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real, simulated mid-write crash leaves the original value untouched, and releases the lock.

    Mirrors `test_audit_storage_adapter.py`'s own established
    "simulate a crash partway through, then confirm the original
    content survives" pattern.
    """
    adapter = _file_adapter(tmp_path / "memory.sqlite3")
    identifier = adapter.write(_obj_value({"status": "created"}))
    real_connection = adapter._connection

    class _FailingOnUpdateConnection:
        """A thin proxy delegating everything to the real connection, except one UPDATE call.

        `sqlite3.Connection.execute` is a read-only instance attribute
        (a C-level slot) -- it cannot be monkeypatched directly on a
        real connection object, so this wraps the whole connection
        instead, matching the only real way to intercept one specific
        call.
        """

        def execute(self, sql: str, parameters: object = ()) -> sqlite3.Cursor:
            if sql.startswith("UPDATE"):
                msg = "simulated mid-write crash"
                raise sqlite3.OperationalError(msg)
            return real_connection.execute(sql, parameters)  # type: ignore[arg-type]

        def __getattr__(self, name: str) -> object:
            return getattr(real_connection, name)

    monkeypatch.setattr(adapter, "_connection", _FailingOnUpdateConnection())

    with pytest.raises(sqlite3.OperationalError):
        adapter.compare_and_update_value(
            identifier, {"status": "created"}, _obj_value({"status": "running"})
        )

    monkeypatch.undo()
    record = adapter.get_by_identifier(identifier)
    assert record is not None
    assert record.value.value == {"status": "created"}

    # The lock must have been genuinely released by the rollback -- a fresh,
    # real, independent connection can immediately write without blocking.
    second_connection = sqlite3.connect(tmp_path / "memory.sqlite3", timeout=1.0)
    try:
        second_connection.execute("BEGIN IMMEDIATE")
        second_connection.rollback()
    finally:
        second_connection.close()


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


def test_backup_produces_a_real_file_with_the_same_row_count(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    destination_path = tmp_path / "backup.sqlite3"
    adapter = _file_adapter(database_path)
    adapter.write(_value("tabs"))
    adapter.write(_value("rust"))

    adapter.backup(str(destination_path))

    assert destination_path.exists()
    assert _raw_row_count(destination_path) == 2  # noqa: PLR2004 -- the real row count written above


def test_restore_replaces_the_live_stores_entire_content(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    backup_path = tmp_path / "backup.sqlite3"
    adapter = _file_adapter(database_path)
    adapter.write(_value("tabs"))
    adapter.backup(str(backup_path))
    # The live store now diverges from the backup -- restore must undo this.
    adapter.write(_value("rust"))
    assert _raw_row_count(database_path) == 2  # noqa: PLR2004 -- the real row count written above

    adapter.restore(str(backup_path))

    assert _raw_row_count(database_path) == 1


def test_restore_raises_for_a_nonexistent_backup_file(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path)

    with pytest.raises(FileNotFoundError):
        adapter.restore(str(tmp_path / "does-not-exist.sqlite3"))


def test_a_restored_record_is_retrievable_with_its_real_content_intact(tmp_path: Path) -> None:
    """A real round trip: write, back up, forget, restore, and get the original value back."""
    database_path = tmp_path / "memory.sqlite3"
    backup_path = tmp_path / "backup.sqlite3"
    adapter = _file_adapter(database_path)
    identifier = adapter.write(_value("tabs"))
    adapter.backup(str(backup_path))
    adapter.forget(identifier)
    assert _raw_row_count(database_path) == 0

    adapter.restore(str(backup_path))

    results = adapter.retrieve("tabs query", limit=1)
    assert len(results) == 1
    assert results[0].value.value == "tabs"


def test_wipe_deletes_every_real_record_and_returns_the_real_count(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path)
    adapter.write(_value("tabs"))
    adapter.write(_value("rust"))

    deleted = adapter.wipe()

    assert deleted == 2  # noqa: PLR2004 -- the real count of records written above
    assert _raw_row_count(database_path) == 0


def test_wipe_on_an_already_empty_store_returns_zero(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path)

    deleted = adapter.wipe()

    assert deleted == 0


def test_a_write_after_wipe_succeeds_normally(tmp_path: Path) -> None:
    """The store stays fully usable after a wipe -- not left in a broken state."""
    database_path = tmp_path / "memory.sqlite3"
    adapter = _file_adapter(database_path)
    adapter.write(_value("tabs"))
    adapter.wipe()

    adapter.write(_value("rust"))

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


def test_opening_a_real_pre_track5_database_migrates_in_the_value_json_column(
    tmp_path: Path,
) -> None:
    """A real database created before value_json existed gets it added on open, not left behind."""
    database_path = tmp_path / "memory.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE memory_records (
                identifier TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                trust INTEGER NOT NULL,
                classification INTEGER NOT NULL,
                sources TEXT NOT NULL,
                written_at TEXT NOT NULL,
                expires_at TEXT
            )
            """
        )
        connection.commit()
        columns_before = {row[1] for row in connection.execute("PRAGMA table_info(memory_records)")}
        assert "value_json" not in columns_before
    finally:
        connection.close()

    _file_adapter(database_path)

    connection = sqlite3.connect(database_path)
    try:
        columns_after = {row[1] for row in connection.execute("PRAGMA table_info(memory_records)")}
    finally:
        connection.close()
    assert "value_json" in columns_after


def test_provenance_is_carried_forward_unchanged() -> None:
    adapter = _adapter()
    original = _value("tabs", Classification.SENSITIVE)
    adapter.write(original)

    results = adapter.retrieve("tabs query", limit=1)

    assert results[0].value.provenance == original.provenance


def test_using_the_same_adapter_from_a_second_thread_fails_closed_not_silently_corrupted() -> None:
    """Real concurrency investigation, property-matrix/fuzzing/concurrency Track 3, 2026-09-04.

    ``sqlite3.connect()`` defaults to ``check_same_thread=True``, so a
    ``SqliteMemoryAdapter`` instance -- like every adapter in this
    project, constructed once per process, never shared across threads
    by any real caller -- fails loudly and safely if it ever is: a
    real, typed ``sqlite3.ProgrammingError``, not silent data
    corruption or a hang. Confirmed directly rather than assumed from
    documentation. No fix needed: this is Python's own stdlib safety
    net operating exactly as intended, and this project's own real
    usage pattern (one adapter instance, one process, no concurrent
    caller anywhere in the current call graph) never exercises the
    cross-thread path this default exists to guard against.
    """
    adapter = _adapter()
    errors: list[BaseException] = []

    def _write_from_another_thread() -> None:
        try:
            adapter.write(_value("tabs"))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=_write_from_another_thread)
    thread.start()
    thread.join(timeout=5)

    assert len(errors) == 1
    assert isinstance(errors[0], sqlite3.ProgrammingError)
