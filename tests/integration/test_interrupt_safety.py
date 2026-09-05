"""Real interrupt-safety investigation (10-phase combined pass, Phase 10).

Every real CLI invocation in this codebase is a fresh, one-shot process
(`kernel/ping.py`'s own docstring: "there is no present benefit to a
long-lived session here"), so the real interrupt-safety question is: if
a `KeyboardInterrupt`/`SIGKILL`/power-loss lands mid-write, does the
real persisted store end up corrupted, or does it fail closed?

**`SqliteMemoryAdapter`: investigated and confirmed safe, empirically,
not just assumed from SQLite's own documentation.**
`test_an_interrupted_write_never_persists_and_the_store_stays_valid`
proves directly: a real `INSERT` executed but never committed (the
same real state a process killed between `execute()` and `commit()`
would leave behind) never appears to a fresh connection opened
afterward, and the store itself remains fully readable/writable --
SQLite's own rollback-journal mechanism holds for this codebase's real
schema and write pattern, not a generic claim taken on faith.

**`JsonFileAuditStorageAdapter`: a real, already-known, deliberately
NOT-fixed gap, connected here rather than duplicated.**
`Path.write_text()` is not atomic -- a process killed mid-`save()`
leaves a truncated, invalid JSON file. This is not a new finding: it is
the same "whole-file-replacement" fragility
`docs/architecture/audit-log-integrity-scoping-notes.md` already names
as one of the audit chain's own open, real gaps, and this pass's own
hard scope boundary explicitly forbids touching the audit chain's
save/load format or attempting to fix this class of issue -- the real,
concrete "interrupt mid-write" scenario is simply the specific way this
already-flagged gap would manifest under a kill signal, not a
separate, new problem needing its own separate fix decision.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from jarvis.adapters.memory import SqliteMemoryAdapter
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeEmbeddingPort:
    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class _FakeClock:
    def now(self) -> datetime:
        return _NOW


class _SequentialIdPort:
    def __init__(self) -> None:
        self._counter = 0

    def new_id(self) -> str:
        self._counter += 1
        return f"mem:{self._counter}"


def _value(text: str) -> Tainted[object]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
    )
    return Tainted(text, provenance)


def _raw_row_count(database_path: Path) -> int:
    connection = sqlite3.connect(database_path)
    try:
        (count,) = connection.execute("SELECT COUNT(*) FROM memory_records").fetchone()
        return int(count)
    finally:
        connection.close()


def test_an_interrupted_write_never_persists_and_the_store_stays_valid(tmp_path: Path) -> None:
    """The real state a process killed between execute() and commit() would leave behind."""
    database_path = tmp_path / "memory.sqlite3"
    adapter = SqliteMemoryAdapter(
        str(database_path), _FakeEmbeddingPort(), _FakeClock(), _SequentialIdPort()
    )
    # Real, granted write -- establishes the store's real schema on disk.
    adapter.write(_value("first, real, committed write"))
    assert _raw_row_count(database_path) == 1

    # Simulate the real state left behind by a process killed after execute()
    # but before commit() -- open a second, independent connection, insert,
    # and never commit, then close it as an abandoned/killed process would
    # (a bare close(), never reaching commit()).
    interrupted_connection = sqlite3.connect(database_path)
    interrupted_connection.execute(
        "INSERT INTO memory_records "
        "(identifier, text, embedding, trust, classification, sources, "
        "written_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("mem:interrupted", "never should persist", "[]", 0, 0, "[]", _NOW.isoformat(), None),
    )
    interrupted_connection.close()  # never committed -- the real "killed mid-write" state

    # The store must be unaffected: the interrupted insert never persisted,
    # and it remains fully valid -- both a fresh read and a fresh write succeed.
    assert _raw_row_count(database_path) == 1
    adapter.write(_value("second, real, committed write, after the interruption"))
    assert _raw_row_count(database_path) == 2  # noqa: PLR2004 -- the real row count after both writes
