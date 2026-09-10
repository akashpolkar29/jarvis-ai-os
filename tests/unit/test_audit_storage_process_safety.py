"""Real, cross-process concurrency tests for JsonFileAuditStorageAdapter (WP-115).

Unlike `tests/unit/test_audit_storage_adapter.py`'s own
`test_two_independent_writers_racing_on_the_same_file_both_records_survive`
(two sequential, in-process adapter instances standing in for two
processes), the tests here use real `multiprocessing.Process` workers
-- genuinely separate OS processes, each with its own Python
interpreter, its own memory, and its own real file descriptors --
exercising the real `fcntl.flock()` mechanism across an actual process
boundary, not merely simulating one.

Deterministic, not timing-based: every worker below blocks on a real
`multiprocessing.Barrier` immediately before its own `save()` call, so
all workers genuinely attempt to save at (as close as the OS scheduler
allows to) the same instant -- maximizing real lock contention -- but
correctness here never depends on how much overlap actually occurs.
The fix must hold regardless of interleaving; the barrier only makes
the contended path likely to actually be exercised, rather than
leaving it to chance the way a bare `time.sleep()`-based test would.
"""

from __future__ import annotations

import multiprocessing
from typing import TYPE_CHECKING, Any

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.audit import AuditChain
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
)
from jarvis.domain.policy import PolicyContext, evaluate
from jarvis.domain.provenance import Provenance, Tainted

if TYPE_CHECKING:
    from pathlib import Path

_NO_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False, remote_confirmation_available=False
)

_WORKER_COUNT = 8
_WORKER_TIMEOUT_S = 30


def _worker(
    path_str: str,
    worker_index: int,
    barrier: Any,
    result_queue: Any,
) -> None:
    """Run in a real, separate OS process: load, append one unique record, barrier, save.

    Module-level (not a closure) so it is picklable under any real
    multiprocessing start method, not just ``fork`` (the real Linux
    default this project targets, but this keeps the test honest about
    not relying on fork-specific semantics like memory sharing).
    """
    from pathlib import Path as _Path  # noqa: PLC0415 -- must be re-imported in the child process

    capability_id = f"test.worker_{worker_index}"
    adapter = JsonFileAuditStorageAdapter(_Path(path_str))
    chain = adapter.load()
    invocation = CapabilityInvocation(
        CapabilityDescriptor(
            id=CapabilityId(capability_id),
            effects=Effect.READ_LOCAL,
            description="A real, per-worker test capability.",
        ),
        Tainted({}, Provenance.user()),
    )
    chain.append(evaluate(invocation, _NO_CONFIRMATION), written_at="2026-09-11T00:00:00+00:00")

    # Every real worker waits here -- all genuinely attempt save() as close
    # to simultaneously as the OS scheduler allows, maximizing real flock()
    # contention rather than leaving it to chance.
    barrier.wait(timeout=_WORKER_TIMEOUT_S)

    try:
        adapter.save(chain)
        result_queue.put(("ok", capability_id))
    except Exception as exc:
        result_queue.put(("error", f"{capability_id}: {type(exc).__name__}: {exc}"))


def test_real_independent_processes_all_survive_a_concurrent_save(tmp_path: Path) -> None:
    """The real, headline proof: N genuinely separate OS processes, zero lost records.

    Each of `_WORKER_COUNT` real child processes loads the same
    starting (empty) chain, appends its own uniquely-identifiable
    record, barrier-synchronizes, then saves -- all racing for the
    same real `fcntl.flock()` on the same real lock file. Every single
    worker's own record must be present in the final chain, which must
    still be a single, valid, contiguously-sequenced hash chain.
    """
    path = tmp_path / "audit.json"
    # Establish the file for real before any worker starts, matching the
    # real, common case (an already-existing audit chain, not every
    # worker racing to create it from nothing too).
    JsonFileAuditStorageAdapter(path).save(AuditChain())

    barrier: Any = multiprocessing.Barrier(_WORKER_COUNT)
    result_queue: Any = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(target=_worker, args=(str(path), index, barrier, result_queue))
        for index in range(_WORKER_COUNT)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=_WORKER_TIMEOUT_S)
        assert not process.is_alive(), "a real worker process hung past its own timeout"
        assert process.exitcode == 0, "a real worker process crashed"

    results = [result_queue.get_nowait() for _ in processes]
    errors = [detail for status, detail in results if status == "error"]
    assert errors == [], f"a real worker's own save() raised: {errors}"

    expected_capability_ids = {f"test.worker_{index}" for index in range(_WORKER_COUNT)}

    final_chain = JsonFileAuditStorageAdapter(path).load()
    final_capability_ids = {
        record.decision.invocation.descriptor.id.value for record in final_chain
    }

    assert final_capability_ids == expected_capability_ids, (
        "at least one real worker's own record was silently lost"
    )
    assert len(final_chain) == _WORKER_COUNT
    verification = final_chain.verify()
    assert verification.valid is True, f"final chain failed verify(): {verification}"
    assert [record.sequence for record in final_chain] == list(range(_WORKER_COUNT))


def test_real_independent_processes_appending_onto_real_pre_existing_history(
    tmp_path: Path,
) -> None:
    """As above, but starting from a real, non-empty chain -- the realistic production shape.

    Proves the fix holds when workers must correctly rebase their own
    new records onto real, pre-existing history, not just an empty
    genesis chain.
    """
    path = tmp_path / "audit.json"
    seed_chain = AuditChain()
    seed_invocation = CapabilityInvocation(
        CapabilityDescriptor(
            id=CapabilityId("test.seed"), effects=Effect.READ_LOCAL, description="Seed record."
        ),
        Tainted({}, Provenance.user()),
    )
    seed_chain.append(
        evaluate(seed_invocation, _NO_CONFIRMATION), written_at="2026-09-11T00:00:00+00:00"
    )
    JsonFileAuditStorageAdapter(path).save(seed_chain)

    barrier: Any = multiprocessing.Barrier(_WORKER_COUNT)
    result_queue: Any = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(target=_worker, args=(str(path), index, barrier, result_queue))
        for index in range(_WORKER_COUNT)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=_WORKER_TIMEOUT_S)
        assert not process.is_alive()
        assert process.exitcode == 0

    results = [result_queue.get_nowait() for _ in processes]
    errors = [detail for status, detail in results if status == "error"]
    assert errors == []

    final_chain = JsonFileAuditStorageAdapter(path).load()
    final_capability_ids = {
        record.decision.invocation.descriptor.id.value for record in final_chain
    }
    expected = {"test.seed", *(f"test.worker_{index}" for index in range(_WORKER_COUNT))}

    assert final_capability_ids == expected
    assert len(final_chain) == _WORKER_COUNT + 1
    assert final_chain.verify().valid is True
    assert [record.sequence for record in final_chain] == list(range(_WORKER_COUNT + 1))
