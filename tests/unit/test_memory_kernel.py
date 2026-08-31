"""Unit tests for jarvis.kernel.memory.authorize_and_remember/authorize_and_recall.

A fake, deterministic EmbeddingPort stands in for the real
FastEmbedAdapter, exactly as tests/unit/adapters/test_memory.py
already does -- these tests must be hermetic, never triggering a real
model download.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.kernel.memory import authorize_and_recall, authorize_and_remember

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
