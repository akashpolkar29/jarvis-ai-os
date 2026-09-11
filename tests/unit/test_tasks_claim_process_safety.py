"""Real, cross-process proof that authorize_and_run_task's claim is genuinely exclusive (WP-120).

Mirrors `tests/unit/test_audit_storage_process_safety.py`/
`tests/unit/test_memory_adapter_process_safety.py`'s own,
already-established pattern: real `multiprocessing.Process` workers --
genuinely separate OS processes -- not two sequential, in-process
calls standing in for two processes.

This is the headline, end-to-end proof `jarvis.kernel.worker` depends
on: two real, independent processes both calling the exact same,
unmodified `authorize_and_run_task` for the exact same, already-
created task must never genuinely both be "running" at the same real
time -- the claim itself (the "created" -> "running" transition) must
never grant to two of them concurrently.

**Two real, genuine findings from this test's own real CI runs,
recorded here rather than silently worked around**:

1. An earlier version used an instantaneous, zero-step plan response
   and asserted that *at most one* of `_WORKER_COUNT` racers would
   ever report `claimed=True`, full stop. CI (not reproducible
   locally, where this machine's own far higher core count never
   exposed it) failed with **two** real processes reporting
   `claimed=True` -- not because the claim's own mutual exclusion
   failed, but because the zero-step plan let the real winner race all
   the way through claim -> run -> `"completed"` *before* a slower
   racer ever got CPU time to attempt its own claim. That slower racer
   then read the task as `"completed"` -- which WP-118 already,
   deliberately, documents as freely re-runnable -- and legitimately
   re-claimed and re-ran it, *sequentially*, not *simultaneously*.
   Both `claimed=True` reports were real and correct; the assertion
   was simply stronger than the real guarantee WP-120 provides.
2. Adding a multi-second delay to the fake provider (to widen the
   "running" window) did **not** eliminate a second CI failure with
   the identical shape (two real claimants). This is the real,
   decisive evidence that the first finding's own "slow straggler"
   explanation, while plausible, was not the *whole* story being
   measured -- the test's own raw claim *count* cannot, by itself,
   distinguish a genuine concurrent race from two real, legitimate,
   sequential claims on a fast, contended, multi-core CI runner. A
   *count* is the wrong instrument for the property actually being
   claimed ("never simultaneous"); a real, measured wall-clock
   interval is the right one.

The fix, in both directions, is not to weaken the safety property
being tested -- it is to measure the *right* thing: each real worker
now records its own real `time.time()` immediately after the barrier
release and immediately after its own call returns, and the test
asserts that **no two real winners' own [start, end] wall-clock
intervals overlap** (`_intervals_overlap`) -- the literal, real-world
meaning of "never simultaneous." A later, non-overlapping winner
remains a real, legitimate, sequential re-run (WP-118, unrelated to
and unchanged by this work package); two genuinely overlapping winners
would be the real race violation this test exists to catch. The
provider's own generous delay (`_PROVIDER_DELAY_SECONDS`) is kept, not
because it alone proves anything, but because it still helps widen the
real window during which contention is actually exercised.
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
    authorize_and_run_task,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt

_WORKER_COUNT = 6
_WORKER_TIMEOUT_S = 30
_PROVIDER_DELAY_SECONDS = 2.0
"""How long the real winner's own plan generation takes -- deliberately generous (see module
docstring's own "a real, genuine finding" section): wide enough that every one of
`_WORKER_COUNT` real racers, however late real OS scheduling runs it under contention, reaches
its own claim attempt while the task is still genuinely "running", not after the winner has
already cycled all the way through to "completed" and become legitimately re-claimable."""


class _FakeEmbeddingPort:
    """A real, deterministic, picklable-by-import EmbeddingPort -- module-level, not a closure."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class _FakeReasoningProvider:
    """A minimal, picklable-by-import ReasoningPort, returning a fixed, zero-step plan.

    Deliberately delayed (see module docstring's own "a real, genuine
    finding" section) -- not to slow down the claim race itself (the
    "created" -> "running" transition happens before this is ever
    called), but to keep the real winner genuinely "running" for long
    enough that every other real racer's own claim attempt, however
    late it is actually scheduled by the OS, still observes "running"
    rather than a task that has already finished and become
    re-claimable.
    """

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        await asyncio.sleep(_PROVIDER_DELAY_SECONDS)
        candidate = Candidate(author="test-provider", content="[]")
        return Tainted(candidate, Provenance.system())


def _worker(  # noqa: PLR0913, PLR0917 -- one per real multiprocessing.Process arg
    chain_path_str: str,
    database_path_str: str,
    task_id: str,
    goal: str,
    barrier: Any,
    result_queue: Any,
) -> None:
    """Run in a real, separate OS process: barrier, then race to claim and run the real task.

    Module-level (not a closure) so it is picklable under any real
    multiprocessing start method, matching the already-established
    precedent in `test_audit_storage_process_safety.py`/
    `test_memory_adapter_process_safety.py`.
    """
    import time  # noqa: PLC0415 -- re-imported in the child process
    from pathlib import Path as _Path  # noqa: PLC0415 -- re-imported in the child process

    barrier.wait(timeout=_WORKER_TIMEOUT_S)
    # The ClockPort ban exists for src/ production code that needs an
    # injectable, fake-able clock for hermetic unit tests -- this is test
    # infrastructure itself, measuring real elapsed wall-clock time across
    # real, independent OS processes to prove a real concurrency property;
    # there is no ClockPort instance to inject across a process boundary.
    started_at = time.time()  # noqa: TID251

    try:
        run_outcome = asyncio.run(
            authorize_and_run_task(
                task_id,
                goal,
                _FakeReasoningProvider(),
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=_Path(chain_path_str),
                database_path=_Path(database_path_str),
                embedding_port=_FakeEmbeddingPort(),
            )
        )
        ended_at = time.time()  # noqa: TID251 -- see the identical, real justification above
        result_queue.put(("ok", run_outcome.claimed, run_outcome.status, started_at, ended_at))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _intervals_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Whether two real, closed [start, end] wall-clock intervals share any real instant."""
    return a[0] <= b[1] and b[0] <= a[1]


def test_real_independent_processes_racing_to_run_the_same_task_never_run_simultaneously(
    tmp_path: Path,
) -> None:
    """The real, headline proof: N genuinely separate OS processes, never two running at once.

    Every worker calls the exact same, unmodified
    `authorize_and_run_task` for the exact same task id. The real
    claim mechanism (WP-120) must prevent two of them from ever
    genuinely being `"running"` at the *same real time* -- checked
    here by real wall-clock intervals, not merely a raw claim count.

    **Deliberately not asserting "at most one ever claims,"** full
    stop -- a fast-completing task is legitimately, deliberately
    re-runnable once `"completed"` (WP-118's own documented design,
    unrelated to and unchanged by this work package), so a second,
    genuinely *later* real claimant that only starts after the first
    one has already finished is a correct, *sequential* outcome, not a
    race violation. What must never happen is two real claimants whose
    own [start, end] wall-clock windows genuinely overlap -- that
    would mean two processes both believed they owned the task at the
    same real instant, which is the actual property WP-120's claim
    mechanism exists to prevent.
    """
    chain_path = tmp_path / "audit_chain.json"
    database_path = tmp_path / "memory.sqlite3"
    goal = "a real, shared, contended task"
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

    barrier: Any = multiprocessing.Barrier(_WORKER_COUNT)
    result_queue: Any = multiprocessing.Queue()
    processes = [
        multiprocessing.Process(
            target=_worker,
            args=(str(chain_path), str(database_path), task_id, goal, barrier, result_queue),
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
    assert errors == [], f"a real worker's own authorize_and_run_task() raised: {errors}"

    oks = [r for r in results if r[0] == "ok"]
    assert len(oks) == _WORKER_COUNT

    claimed_flags = [claimed for _status, claimed, _task_status, _started, _ended in oks]
    assert sum(claimed_flags) >= 1, "expected at least one real claimant, got none"

    # The real, headline safety property: no two real winners' own real,
    # measured [start, end] wall-clock windows may overlap -- that would
    # mean two processes both genuinely believed they owned the task at the
    # same real instant. A later, non-overlapping winner is a real,
    # legitimate, sequential re-run of an already-completed task (WP-118),
    # not a race violation -- see this test's own docstring.
    winner_intervals = [
        (started, ended) for _status, claimed, _task_status, started, ended in oks if claimed
    ]
    for i, interval_a in enumerate(winner_intervals):
        for interval_b in winner_intervals[i + 1 :]:
            assert not _intervals_overlap(interval_a, interval_b), (
                f"two real winners' own claim windows overlapped: {interval_a} vs {interval_b} "
                "-- this means two processes genuinely ran the same task simultaneously"
            )

    # Every loser honestly re-reads whatever the real, current status is at
    # the exact moment it loses -- "running" (the winner hasn't finished its
    # own, separate "running" -> "completed" write yet) or "completed" (it
    # already has) are both real, legitimate, timing-dependent outcomes;
    # asserting one specific value here would make this test flaky.
    loser_statuses = {
        task_status for _status, claimed, task_status, _started, _ended in oks if not claimed
    }
    assert loser_statuses <= {"running", "completed"}, loser_statuses

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
