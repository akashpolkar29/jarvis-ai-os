"""Real, cross-process proof that authorize_and_run_task's claim is genuinely exclusive (WP-120).

Mirrors `tests/unit/test_audit_storage_process_safety.py`/
`tests/unit/test_memory_adapter_process_safety.py`'s own,
already-established pattern: real `multiprocessing.Process` workers --
genuinely separate OS processes -- not two sequential, in-process
calls standing in for two processes.

This is the headline, end-to-end proof `jarvis.kernel.worker` depends
on: two real, independent processes both calling the exact same,
unmodified `authorize_and_run_task` for the exact same, already-
created task must never both be "running" at the same real time --
the claim itself (the "created" -> "running" transition) must grant
to exactly one of them.

**A real, genuine finding from this test's own first CI run, recorded
here rather than silently worked around**: an earlier version of this
test used an instantaneous, zero-step plan response and asserted that
*at most one* of `_WORKER_COUNT` racers would ever report
`claimed=True`, full stop. On a real, busier CI runner (not
reproducible locally, where this machine's own faster, less-contended
scheduling never exposed it), that assertion failed with **two** real
processes reporting `claimed=True` -- not because the claim's own
mutual exclusion failed, but because the zero-step plan let the real
winner race all the way through claim -> run -> `"completed"` before a
slower racer (genuinely delayed by real OS scheduling under
contention, not a bug) ever got CPU time to attempt its own claim.
That slower racer then read the task as `"completed"` -- which WP-118
already, deliberately, documents as freely re-runnable -- and
legitimately re-claimed and re-ran it, *sequentially*, not
*simultaneously*. Both `claimed=True` reports were real and correct;
the test's own assertion was simply stronger than the real guarantee
WP-120 provides (no *concurrent* double-execution, never a promise
that a fast-completing task can't be legitimately re-run by a second,
slower caller racing the same initial request).

The fix here is not to weaken the safety property being tested -- it
is to make the fake provider take a real, deliberately generous amount
of time (`_PROVIDER_DELAY_SECONDS`) before returning its plan, so the
task remains genuinely `"running"` for long enough that every real
racer, however late the OS schedules it, attempts its own claim while
the task is still `"running"` (and therefore loses, correctly) rather
than racing against a task that has already cycled all the way through
to `"completed"` and become re-claimable again.
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
    from pathlib import Path as _Path  # noqa: PLC0415 -- re-imported in the child process

    barrier.wait(timeout=_WORKER_TIMEOUT_S)

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
        result_queue.put(("ok", run_outcome.claimed, run_outcome.status))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def test_real_independent_processes_racing_to_run_the_same_task_exactly_one_executes(
    tmp_path: Path,
) -> None:
    """The real, headline proof: N genuinely separate OS processes, exactly one real executor.

    Every worker calls the exact same, unmodified
    `authorize_and_run_task` for the exact same task id -- the real
    claim mechanism (WP-120) must grant execution to exactly one of
    them; every other worker must report `claimed=False`, having
    attempted no plan execution at all.
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

    claimed_flags = [claimed for status, claimed, _task_status in results if status == "ok"]
    assert len(claimed_flags) == _WORKER_COUNT
    assert sum(claimed_flags) == 1, f"expected exactly one real claimant, got {claimed_flags}"

    # Every loser honestly re-reads whatever the real, current status is at
    # the exact moment it loses -- "running" (the winner hasn't finished its
    # own, separate "running" -> "completed" write yet) or "completed" (it
    # already has) are both real, legitimate, timing-dependent outcomes;
    # asserting one specific value here would make this test flaky.
    loser_statuses = {
        task_status for status, claimed, task_status in results if status == "ok" and not claimed
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
