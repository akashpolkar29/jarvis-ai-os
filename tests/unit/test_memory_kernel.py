"""Unit tests for jarvis.kernel.memory's real, invocable memory capabilities.

A fake, deterministic EmbeddingPort stands in for the real
FastEmbedAdapter, exactly as tests/unit/adapters/test_memory.py
already does -- these tests must be hermetic, never triggering a real
model download.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.kernel.memory import (
    authorize_and_backup_memory,
    authorize_and_forget,
    authorize_and_pin,
    authorize_and_recall,
    authorize_and_remember,
    authorize_and_restore_memory,
    authorize_and_wipe_memory,
)
from jarvis.ports.memory_write import MemoryRecordNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

_GRANTED_CALLS = 1
_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeEmbeddingPort:
    """Maps every text to the same vector -- similarity ranking is not what these tests check."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class _FakeClock:
    def __init__(self, now: datetime = _NOW) -> None:
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


def test_granted_write_persists_and_returns_an_identifier(tmp_path: Path) -> None:
    outcome = authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    assert outcome.decision.granted is True
    assert outcome.identifier == "mem:1"


def test_denied_write_never_reaches_the_store(tmp_path: Path) -> None:
    database_path = tmp_path / "memory.sqlite3"
    outcome = authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    assert outcome.decision.granted is False
    assert outcome.identifier is None

    recall = authorize_and_recall(
        "prefers tabs",
        limit=5,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert recall.records == ()


def test_a_single_granted_write_appends_one_verifiable_record(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain.verify().valid is True


def test_granted_recall_returns_a_previously_written_record(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    write_outcome = authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    recall = authorize_and_recall(
        "what indentation does the user like",
        limit=5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    assert recall.decision.granted is True
    assert len(recall.records) == 1
    assert recall.records[0].identifier == write_outcome.identifier
    assert recall.records[0].value.value == "prefers tabs"


def test_recall_is_always_granted_regardless_of_confirmation(tmp_path: Path) -> None:
    recall = authorize_and_recall(
        "anything",
        limit=5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    assert recall.decision.granted is True
    assert recall.records == ()


def test_a_granted_write_sweeps_a_previously_expired_record_from_real_storage(
    tmp_path: Path,
) -> None:
    """ADR-0051's owed sweep, closed: every granted write also deletes prior expired rows."""
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    clock = _FakeClock(_NOW)

    authorize_and_remember(
        "old fact",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=clock,
        id_port=_SequentialIdPort(),
    )

    clock.set_now(_NOW + timedelta(days=91))
    authorize_and_remember(
        "new fact",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=clock,
        id_port=_SequentialIdPort(),
    )

    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT text FROM memory_records").fetchall()
    finally:
        connection.close()
    assert rows == [("new fact",)]


def test_granted_pin_keeps_the_record_past_its_original_expiry(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    clock = _FakeClock(_NOW)
    write_outcome = authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=clock,
        id_port=_SequentialIdPort(),
    )
    assert write_outcome.identifier is not None

    pin_decision = authorize_and_pin(
        write_outcome.identifier,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=clock,
        id_port=_SequentialIdPort(),
    )
    assert pin_decision.granted is True

    clock.set_now(_NOW + timedelta(days=36500))
    recall = authorize_and_recall(
        "prefers tabs",
        limit=5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=clock,
        id_port=_SequentialIdPort(),
    )
    assert len(recall.records) == 1
    assert recall.records[0].expires_at is None


def test_denied_pin_never_reaches_the_store(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    clock = _FakeClock(_NOW)
    write_outcome = authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=clock,
        id_port=_SequentialIdPort(),
    )
    assert write_outcome.identifier is not None

    pin_decision = authorize_and_pin(
        write_outcome.identifier,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=clock,
        id_port=_SequentialIdPort(),
    )
    assert pin_decision.granted is False

    clock.set_now(_NOW + timedelta(days=91))
    recall = authorize_and_recall(
        "prefers tabs",
        limit=5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=clock,
        id_port=_SequentialIdPort(),
    )
    assert recall.records == ()


def test_granted_pin_of_an_unknown_identifier_raises(tmp_path: Path) -> None:
    with pytest.raises(MemoryRecordNotFoundError):
        authorize_and_pin(
            "mem:does-not-exist",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            database_path=tmp_path / "memory.sqlite3",
            embedding_port=_FakeEmbeddingPort(),
            clock=_FakeClock(),
            id_port=_SequentialIdPort(),
        )


def test_pin_still_appends_a_verifiable_audit_record_even_when_denied(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"

    authorize_and_pin(
        "mem:1",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == _GRANTED_CALLS
    assert chain.verify().valid is True


def test_granted_forget_permanently_deletes_the_record(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    write_outcome = authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert write_outcome.identifier is not None

    forget_decision = authorize_and_forget(
        write_outcome.identifier,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert forget_decision.granted is True

    recall = authorize_and_recall(
        "prefers tabs",
        limit=5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert recall.records == ()


def test_forget_is_denied_without_physical_confirmation(tmp_path: Path) -> None:
    """memory.forget is MANUAL_ONLY -- remote confirmation alone can never grant it."""
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    write_outcome = authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert write_outcome.identifier is not None

    forget_decision = authorize_and_forget(
        write_outcome.identifier,
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert forget_decision.granted is False

    recall = authorize_and_recall(
        "prefers tabs",
        limit=5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert len(recall.records) == 1


def test_granted_forget_of_an_unknown_identifier_raises(tmp_path: Path) -> None:
    with pytest.raises(MemoryRecordNotFoundError):
        authorize_and_forget(
            "mem:does-not-exist",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            database_path=tmp_path / "memory.sqlite3",
            embedding_port=_FakeEmbeddingPort(),
            clock=_FakeClock(),
            id_port=_SequentialIdPort(),
        )


def test_granted_backup_produces_a_real_file(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    destination_path = tmp_path / "backup.sqlite3"
    authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    backup_decision = authorize_and_backup_memory(
        destination_path,
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    assert backup_decision.granted is True
    assert destination_path.exists()


def test_backup_is_denied_without_any_confirmation(tmp_path: Path) -> None:
    """memory.backup is CONFIRM -- remote confirmation alone is sufficient, but neither is not."""
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    destination_path = tmp_path / "backup.sqlite3"

    backup_decision = authorize_and_backup_memory(
        destination_path,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    assert backup_decision.granted is False
    assert not destination_path.exists()


def test_granted_restore_replaces_the_live_stores_content(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    backup_path = tmp_path / "backup.sqlite3"
    id_port = _SequentialIdPort()
    authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )
    authorize_and_backup_memory(
        backup_path,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )
    authorize_and_remember(
        "prefers rust",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )

    restore_decision = authorize_and_restore_memory(
        backup_path,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    assert restore_decision.granted is True
    connection = sqlite3.connect(database_path)
    try:
        (count,) = connection.execute("SELECT COUNT(*) FROM memory_records").fetchone()
        assert count == 1
    finally:
        connection.close()


def test_restore_is_denied_without_physical_confirmation(tmp_path: Path) -> None:
    """memory.restore is MANUAL_ONLY -- remote confirmation alone can never grant it."""
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    backup_path = tmp_path / "backup.sqlite3"
    authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    authorize_and_backup_memory(
        backup_path,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    restore_decision = authorize_and_restore_memory(
        backup_path,
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )

    assert restore_decision.granted is False


def test_granted_restore_of_a_nonexistent_backup_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        authorize_and_restore_memory(
            tmp_path / "does-not-exist.sqlite3",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "audit_chain.json",
            database_path=tmp_path / "memory.sqlite3",
            embedding_port=_FakeEmbeddingPort(),
            clock=_FakeClock(),
            id_port=_SequentialIdPort(),
        )


def test_granted_wipe_deletes_every_record_and_reports_the_real_count(tmp_path: Path) -> None:
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    id_port = _SequentialIdPort()
    authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )
    authorize_and_remember(
        "prefers rust",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )

    wipe_outcome = authorize_and_wipe_memory(
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )

    assert wipe_outcome.decision.granted is True
    assert wipe_outcome.deleted_count == 2  # noqa: PLR2004 -- the real count of records written above

    recall = authorize_and_recall(
        "prefers",
        limit=5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )
    assert recall.records == ()


def test_wipe_is_denied_without_physical_confirmation(tmp_path: Path) -> None:
    """memory.wipe is MANUAL_ONLY -- remote confirmation alone can never grant it."""
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    id_port = _SequentialIdPort()
    authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )

    wipe_outcome = authorize_and_wipe_memory(
        physical_confirmation_available=False,
        remote_confirmation_available=True,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )

    assert wipe_outcome.decision.granted is False
    assert wipe_outcome.deleted_count is None

    recall = authorize_and_recall(
        "prefers",
        limit=5,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )
    assert len(recall.records) == 1
