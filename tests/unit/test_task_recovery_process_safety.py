"""Real, cross-process proof that authorize_and_recover_task's CAS is genuinely exclusive (WP-126).

Mirrors `tests/unit/test_tasks_claim_process_safety.py`'s own,
already-established headline pattern exactly -- real
`multiprocessing.Process` workers, genuinely separate OS processes --
racing `jarvis.kernel.tasks.authorize_and_recover_task` for the exact
same, already-stale task.

Unlike the run/retry claim race (where a later, sequential winner is a
real, legitimate re-run of an already-`"completed"` task, so the right
assertion is "no two winners' wall-clock windows overlap"), recovery
has no such legitimate-repeat case: once one real recovery attempt
applies, the task is `"failed"`, and every other racer's own fresh,
internal re-read sees `"failed"`, not `"running"`, and is refused by
the fast-path status check before ever reaching the real CAS at all.
So the right, stronger assertion here is simply "exactly one real
racer ever reports `recovered=True`" -- not an overlap measurement.
"""

from __future__ import annotations

import multiprocessing
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from jarvis.kernel.tasks import (
    authorize_and_create_task,
    authorize_and_get_task,
    update_task_status,
)

if TYPE_CHECKING:
    from pathlib import Path

_WORKER_COUNT = 6
_WORKER_TIMEOUT_S = 30


class _FakeEmbeddingPort:
    """A real, deterministic, picklable-by-import EmbeddingPort -- module-level, not a closure."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class _FixedClock:
    """A real, picklable-by-import ClockPort fixed to one real, past wall-clock instant.

    Used only for parent-process setup (writing a genuinely
    stale-relative-to-now `updated_at`) -- every real worker below
    uses the real, unfaked `SystemClockAdapter` default, so staleness
    is judged against real wall-clock time exactly as production code
    would.
    """

    def __init__(self, when: datetime) -> None:
        self._when = when

    def now(self) -> datetime:
        return self._when


def _worker(
    chain_path_str: str,
    database_path_str: str,
    task_id: str,
    barrier: Any,
    result_queue: Any,
) -> None:
    """Run in a real, separate OS process: barrier, then race one real recovery attempt.

    Module-level (not a closure) so it is picklable under any real
    multiprocessing start method, matching
    `test_tasks_claim_process_safety.py`'s own established precedent.
    Imports `jarvis.kernel.tasks.authorize_and_recover_task` inside the
    function body purely so this file's own top-level imports stay
    minimal -- no real import-order hazard either way.
    """
    from pathlib import Path as _Path  # noqa: PLC0415 -- re-imported in the child process

    from jarvis.kernel.tasks import authorize_and_recover_task  # noqa: PLC0415

    barrier.wait(timeout=_WORKER_TIMEOUT_S)

    try:
        recover_outcome = authorize_and_recover_task(
            task_id,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=_Path(chain_path_str),
            database_path=_Path(database_path_str),
            embedding_port=_FakeEmbeddingPort(),
        )
        result_queue.put(("ok", recover_outcome.recovered, recover_outcome.reason))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def test_real_independent_processes_racing_to_recover_the_same_stale_task_only_one_wins(
    tmp_path: Path,
) -> None:
    """The real, headline WP-126 proof: N genuinely separate processes, exactly one recovers.

    Every worker calls the exact same, unmodified
    `authorize_and_recover_task` against the exact same,
    already-stale, already-"running" task. The real mutual exclusion
    comes entirely from `authorize_and_compare_and_update`'s own,
    already-hardened compare-and-swap (WP-120) -- this function adds
    no new locking of its own.
    """
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    goal = "a real, shared, contended, stale, running task"
    create_outcome = authorize_and_create_task(
        goal,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )
    assert create_outcome.task_id is not None
    task_id = create_outcome.task_id

    # A real, far-past wall-clock instant -- genuinely stale against any real
    # SystemClockAdapter.now() by the time the real workers below actually run.
    # Test infrastructure measuring/seeding real wall-clock time, not production
    # code with an injectable ClockPort -- see test_tasks_claim_process_safety.py's
    # own identical, real justification for its own time.time() usage.
    long_ago = datetime.now(UTC) - timedelta(hours=1)  # noqa: TID251
    update_task_status(
        task_id,
        goal,
        "running",
        None,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
        clock=_FixedClock(long_ago),
        id_port=None,
    )
    pre_check = authorize_and_get_task(
        task_id,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )
    assert pre_check.stale is True

    barrier: Any = multiprocessing.Barrier(_WORKER_COUNT)
    result_queue: Any = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(
            target=_worker,
            args=(str(chain_path), str(database_path), task_id, barrier, result_queue),
        )
        for _ in range(_WORKER_COUNT)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=_WORKER_TIMEOUT_S)
        assert not process.is_alive(), "a real worker process hung past its own timeout"
        assert process.exitcode == 0, "a real worker process crashed"

    results = [result_queue.get_nowait() for _ in processes]
    errors = [detail for status, *detail in results if status == "error"]
    assert errors == [], f"a real worker's own authorize_and_recover_task() raised: {errors}"

    recovered_flags = [recovered for _status, recovered, _reason in results]
    assert recovered_flags.count(True) == 1, (
        f"expected exactly one real winner, got {recovered_flags.count(True)}: {results}"
    )

    final = authorize_and_get_task(
        task_id,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )
    assert final.record is not None
    assert final.record.value.value["status"] == "failed"  # type: ignore[index]
