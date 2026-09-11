"""Real, cross-process proof that a due, scheduled task is never run simultaneously (WP-122).

Mirrors `tests/unit/test_tasks_claim_process_safety.py`'s own,
already-established headline pattern exactly -- real
`multiprocessing.Process` workers, genuinely separate OS processes --
but races `jarvis.kernel.worker.run_pending_tasks_once` itself (the
real thing two independent `jarvis task worker` invocations would each
call), not `authorize_and_run_task`/`authorize_and_retry_task`
directly. This is the faithful, real-world shape WP-122 actually
introduces: a task's own real `scheduled_at` due-time check
(`jarvis.kernel.worker._is_due`) is a pure, local, read-only filter
over what one pass will *attempt* -- it adds no new locking of its
own. The real mutual-exclusion guarantee this test proves still comes
entirely from the exact, unmodified WP-120 claim mechanism inside
`authorize_and_run_task`, reached here only through
`run_pending_tasks_once`'s own real discovery-then-delegate shape.

Uses the identical, real `_intervals_overlap` wall-clock-window
technique `test_tasks_claim_process_safety.py` already established
(see that module's own docstring for the two, real CI findings that
led to measuring overlap rather than counting claims) -- a raw claim
count cannot, by itself, distinguish a genuine concurrent race from
two real, legitimate, sequential claims on a fast, contended,
multi-core runner.
"""

from __future__ import annotations

import asyncio
import multiprocessing
from typing import TYPE_CHECKING, Any

from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.tasks import (
    authorize_and_create_task,
    authorize_and_get_task,
    authorize_and_schedule_task,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt

_WORKER_COUNT = 6
_WORKER_TIMEOUT_S = 30
_PROVIDER_DELAY_SECONDS = 2.0
"""See `test_tasks_claim_process_safety.py`'s own identical constant -- deliberately generous so
every real racer's own claim attempt, however late it is actually scheduled under contention,
still observes the task as genuinely "running", not already "completed" and re-claimable."""


class _FakeEmbeddingPort:
    """A real, deterministic, picklable-by-import EmbeddingPort -- module-level, not a closure."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class _FakeReasoningProvider:
    """A minimal, picklable-by-import ReasoningPort, returning a fixed, zero-step plan."""

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        await asyncio.sleep(_PROVIDER_DELAY_SECONDS)
        candidate = Candidate(author="test-provider", content="[]")
        return Tainted(candidate, Provenance.system())


def _worker(
    chain_path_str: str,
    database_path_str: str,
    barrier: Any,
    result_queue: Any,
) -> None:
    """Run in a real, separate OS process: barrier, then race one real worker pass.

    Module-level (not a closure) so it is picklable under any real
    multiprocessing start method, matching
    `test_tasks_claim_process_safety.py`'s own established precedent.
    Imports `jarvis.kernel.worker` inside the function body -- not at
    module scope -- purely so this file's own top-level imports stay
    minimal and obviously mirror its sibling's shape; there is no real
    import-order hazard here either way.
    """
    import time  # noqa: PLC0415 -- re-imported in the child process
    from pathlib import Path as _Path  # noqa: PLC0415 -- re-imported in the child process

    from jarvis.kernel.worker import run_pending_tasks_once  # noqa: PLC0415

    barrier.wait(timeout=_WORKER_TIMEOUT_S)
    # See `test_tasks_claim_process_safety.py`'s own identical, real
    # justification for why the ClockPort ban does not apply to test
    # infrastructure measuring real, cross-process wall-clock time.
    started_at = time.time()  # noqa: TID251

    try:
        pass_outcome = asyncio.run(
            run_pending_tasks_once(
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=_Path(chain_path_str),
                database_path=_Path(database_path_str),
                embedding_port=_FakeEmbeddingPort(),
                provider=_FakeReasoningProvider(),
            )
        )
        ended_at = time.time()  # noqa: TID251
        claimed_count = pass_outcome.claimed_count
        status = pass_outcome.attempted[0].status if pass_outcome.attempted else None
        result_queue.put(("ok", claimed_count, status, started_at, ended_at))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _intervals_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Whether two real, closed [start, end] wall-clock intervals share any real instant."""
    return a[0] <= b[1] and b[0] <= a[1]


def test_real_independent_worker_processes_racing_on_the_same_due_task_never_run_simultaneously(
    tmp_path: Path,
) -> None:
    """The real, headline WP-122 proof: N genuinely separate worker processes, never two at once.

    Every worker calls the exact same, unmodified
    `run_pending_tasks_once` against the exact same, already-created,
    already-past-due-scheduled task. No second claim mechanism exists
    for scheduling itself (see module docstring) -- the real mutual
    exclusion is entirely WP-120's own, already-hardened claim inside
    `authorize_and_run_task`, reached here through the real worker.
    """
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    goal = "a real, shared, contended, due, scheduled task"
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

    # A real, far-past timestamp -- genuinely due the moment any worker checks,
    # matching this work package's own chosen missed-schedule policy.
    schedule_outcome = authorize_and_schedule_task(
        task_id,
        "2020-01-01T00:00:00+00:00",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=chain_path,
        database_path=database_path,
        embedding_port=_FakeEmbeddingPort(),
    )
    assert schedule_outcome.scheduled is True

    barrier: Any = multiprocessing.Barrier(_WORKER_COUNT)
    result_queue: Any = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(
            target=_worker,
            args=(str(chain_path), str(database_path), barrier, result_queue),
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
    assert errors == [], f"a real worker's own run_pending_tasks_once() raised: {errors}"

    oks = [r for r in results if r[0] == "ok"]
    assert len(oks) == _WORKER_COUNT

    claimed_counts = [claimed_count for _status, claimed_count, _task_status, _s, _e in oks]
    assert sum(claimed_counts) >= 1, "expected at least one real claimant, got none"

    # The real, headline safety property, identical to
    # `test_tasks_claim_process_safety.py`'s own: no two real winners' own
    # measured [start, end] wall-clock windows may overlap.
    winner_intervals = [
        (started, ended)
        for _status, claimed_count, _task_status, started, ended in oks
        if claimed_count >= 1
    ]
    for i, interval_a in enumerate(winner_intervals):
        for interval_b in winner_intervals[i + 1 :]:
            assert not _intervals_overlap(interval_a, interval_b), (
                f"two real winners' own pass windows overlapped: {interval_a} vs {interval_b} "
                "-- this means two worker processes genuinely ran the same scheduled task "
                "simultaneously"
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
    assert final.record.value.value["status"] == "completed"  # type: ignore[index]
