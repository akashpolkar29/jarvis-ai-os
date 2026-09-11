"""Real, cross-process concurrency tests for SqliteMemoryAdapter.compare_and_update_value (WP-120).

Mirrors `tests/unit/test_audit_storage_process_safety.py`'s own,
already-established pattern exactly: real `multiprocessing.Process`
workers -- genuinely separate OS processes, each with its own Python
interpreter and its own real `sqlite3.connect()` to the same file --
not two sequential, in-process adapter instances standing in for two
processes.

This is the headline, process-level proof the claim mechanism (WP-120,
`jarvis.kernel.worker`) depends on: N real, independent processes all
racing to claim the exact same record must result in exactly one
winner, never zero, never more than one, and the final stored value
must genuinely be the winner's own, not a corrupted mix of two
writers' partial updates.
"""

from __future__ import annotations

import multiprocessing
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from jarvis.adapters.memory import SqliteMemoryAdapter
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

if TYPE_CHECKING:
    from pathlib import Path

_SEED_NOW = datetime(2026, 9, 11, tzinfo=UTC)

_WORKER_COUNT = 8
_WORKER_TIMEOUT_S = 30


class _FakeEmbeddingPort:
    """A real, deterministic, picklable-by-import EmbeddingPort -- module-level, not a closure."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class _FakeClock:
    def now(self) -> datetime:
        return _SEED_NOW


class _SequentialIdPort:
    def __init__(self) -> None:
        self._counter = 0

    def new_id(self) -> str:
        self._counter += 1
        return f"mem:seed:{self._counter}"


def _value(payload: object) -> Tainted[object]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
    )
    return Tainted(payload, provenance)


def _adapter(path_str: str) -> SqliteMemoryAdapter:
    return SqliteMemoryAdapter(path_str, _FakeEmbeddingPort(), _FakeClock(), _SequentialIdPort())


def _worker(  # noqa: PLR0913, PLR0917 -- one per real multiprocessing.Process arg, mirrors the audit precedent
    path_str: str,
    worker_index: int,
    identifier: str,
    expected_value: object,
    barrier: Any,
    result_queue: Any,
) -> None:
    """Run in a real, separate OS process: open a fresh connection, barrier, attempt the CAS.

    Module-level (not a closure) so it is picklable under any real
    multiprocessing start method, matching
    `test_audit_storage_process_safety.py::_worker`'s own identical
    reasoning.
    """
    adapter = _adapter(path_str)

    # Every real worker waits here -- all genuinely attempt the CAS as close
    # to simultaneously as the OS scheduler allows, maximizing real
    # BEGIN IMMEDIATE lock contention rather than leaving it to chance.
    barrier.wait(timeout=_WORKER_TIMEOUT_S)

    try:
        new_value = _value({"status": "running", "claimed_by": worker_index})
        applied = adapter.compare_and_update_value(identifier, expected_value, new_value)
        result_queue.put(("ok", worker_index, applied))
    except Exception as exc:
        result_queue.put(("error", worker_index, f"{type(exc).__name__}: {exc}"))


def test_real_independent_processes_racing_to_claim_exactly_one_wins(tmp_path: Path) -> None:
    """The real, headline proof: N genuinely separate OS processes, exactly one real winner.

    Every worker reads the exact same starting value and races to
    transition it -- `compare_and_update_value` must grant the swap to
    exactly one of them; every other worker must see `False` (lost the
    race), and the store must be left exactly as the one real winner
    left it, never a corrupted mix of two writers' own updates.
    """
    path = tmp_path / "memory.sqlite3"
    seed_value = {"status": "created", "goal": "a real, shared, contended task"}
    seed_adapter = _adapter(str(path))
    identifier = seed_adapter.write(_value(seed_value))

    barrier: Any = multiprocessing.Barrier(_WORKER_COUNT)
    result_queue: Any = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(
            target=_worker,
            args=(str(path), index, identifier, seed_value, barrier, result_queue),
        )
        for index in range(_WORKER_COUNT)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=_WORKER_TIMEOUT_S)
        assert not process.is_alive(), "a real worker process hung past its own timeout"
        assert process.exitcode == 0, "a real worker process crashed"

    results = [result_queue.get_nowait() for _ in processes]
    errors = [(index, detail) for status, index, detail in results if status == "error"]
    assert errors == [], f"a real worker's own compare_and_update_value() raised: {errors}"

    applied_by_worker = {index: applied for status, index, applied in results if status == "ok"}
    assert len(applied_by_worker) == _WORKER_COUNT

    winners = [index for index, applied in applied_by_worker.items() if applied]
    assert len(winners) == 1, f"expected exactly one real winner, got {winners}"
    (winner,) = winners

    final_record = seed_adapter.get_by_identifier(identifier)
    assert final_record is not None
    assert final_record.value.value == {"status": "running", "claimed_by": winner}


def test_real_independent_processes_all_seeing_a_stale_expectation_all_lose(
    tmp_path: Path,
) -> None:
    """If the record has already moved on, every real racer correctly loses -- zero winners.

    A real, negative-case counterpart: every worker is handed an
    `expected_value` that no longer matches what is actually stored
    (simulating every one of them having read a now-stale snapshot) --
    none of them may apply their own write.
    """
    path = tmp_path / "memory.sqlite3"
    seed_adapter = _adapter(str(path))
    seed_value: dict[str, object] = {"status": "completed", "goal": "already finished"}
    identifier = seed_adapter.write(_value(seed_value))
    stale_expected_value = {"status": "created", "goal": "already finished"}

    barrier: Any = multiprocessing.Barrier(_WORKER_COUNT)
    result_queue: Any = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(
            target=_worker,
            args=(str(path), index, identifier, stale_expected_value, barrier, result_queue),
        )
        for index in range(_WORKER_COUNT)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=_WORKER_TIMEOUT_S)
        assert not process.is_alive()
        assert process.exitcode == 0

    results = [result_queue.get_nowait() for _ in processes]
    errors = [(index, detail) for status, index, detail in results if status == "error"]
    assert errors == []

    applied_by_worker = {index: applied for status, index, applied in results if status == "ok"}
    assert len(applied_by_worker) == _WORKER_COUNT
    assert all(applied is False for applied in applied_by_worker.values())

    final_record = seed_adapter.get_by_identifier(identifier)
    assert final_record is not None
    assert final_record.value.value == {"status": "completed", "goal": "already finished"}
