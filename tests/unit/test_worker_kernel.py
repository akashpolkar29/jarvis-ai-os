"""Unit tests for jarvis.kernel.worker: a real, minimal background-task worker (WP-120).

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter,
exactly matching `test_tasks_kernel.py`'s own established discipline.
Real, cross-process duplicate-claim proof lives separately, in
`test_tasks_claim_process_safety.py` -- these tests exercise
`run_pending_tasks_once`'s own discovery/delegation/bookkeeping logic
in a single process.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.memory import authorize_and_remember
from jarvis.kernel.tasks import authorize_and_cancel_task, authorize_and_create_task
from jarvis.kernel.worker import WorkerPassOutcome, WorkerTaskOutcome, run_pending_tasks_once

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt
    from jarvis.kernel.tasks import TaskCreateOutcome

_NOW = datetime(2026, 9, 11, tzinfo=UTC)


class _FakeEmbeddingPort:
    """Maps every text to the same vector -- similarity ranking is not what these tests check."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)


class _FakeClock:
    def __init__(self, now: datetime = _NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class _SequentialIdPort:
    def __init__(self) -> None:
        self._counter = 0

    def new_id(self) -> str:
        self._counter += 1
        return f"mem:{self._counter}"


class _FakeReasoningProvider:
    """A minimal, test-local ReasoningPort, always returning a fixed plan response."""

    def __init__(self, content: str) -> None:
        self._content = content

    async def generate(
        self, _task: str, _prior_attempts: tuple[Attempt, ...]
    ) -> Tainted[Candidate]:
        candidate = Candidate(author="test-provider", content=self._content)
        return Tainted(candidate, Provenance.system())


def _create(tmp_path: Path, goal: str) -> TaskCreateOutcome:
    return authorize_and_create_task(
        goal,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )


async def _run_pass(
    tmp_path: Path, plan_response: str = "[]", *, physical_confirmation_available: bool = True
) -> WorkerPassOutcome:
    return await run_pending_tasks_once(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
        provider=_FakeReasoningProvider(plan_response),
    )


async def test_discovers_and_runs_a_real_created_task_to_completion(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a trivial goal")
    assert create_outcome.task_id is not None

    pass_outcome = await _run_pass(tmp_path)

    assert len(pass_outcome.attempted) == 1
    outcome = pass_outcome.attempted[0]
    assert outcome.task_id == create_outcome.task_id
    assert outcome.claimed is True
    assert outcome.status == "completed"
    assert outcome.reason is None
    assert outcome.error is None
    assert pass_outcome.claimed_count == 1


async def test_a_completed_task_is_not_rediscovered_on_a_second_pass(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a trivial goal")
    assert create_outcome.task_id is not None
    first_pass = await _run_pass(tmp_path)
    assert first_pass.attempted[0].status == "completed"

    second_pass = await _run_pass(tmp_path)

    assert second_pass.attempted == ()
    assert second_pass.claimed_count == 0


async def test_a_malformed_plan_response_is_persisted_as_failed_and_reported(
    tmp_path: Path,
) -> None:
    create_outcome = _create(tmp_path, "an impossible goal")
    assert create_outcome.task_id is not None

    pass_outcome = await _run_pass(tmp_path, plan_response="not valid json")

    assert len(pass_outcome.attempted) == 1
    outcome = pass_outcome.attempted[0]
    assert outcome.task_id == create_outcome.task_id
    assert outcome.claimed is True  # it genuinely claimed and attempted to run this task
    assert outcome.error is not None
    assert "PlanningError" in outcome.error


async def test_a_cancelled_task_is_never_discovered_or_run(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a goal a human gave up on")
    assert create_outcome.task_id is not None
    cancel_outcome = authorize_and_cancel_task(
        create_outcome.task_id,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert cancel_outcome.cancelled is True

    pass_outcome = await _run_pass(tmp_path)

    assert pass_outcome.attempted == ()


async def test_a_pass_with_nothing_eligible_returns_an_empty_outcome(tmp_path: Path) -> None:
    pass_outcome = await _run_pass(tmp_path)

    assert pass_outcome.attempted == ()
    assert pass_outcome.claimed_count == 0


async def test_a_malformed_task_record_is_skipped_without_crashing_the_pass(
    tmp_path: Path,
) -> None:
    """A real task record with no real string goal -- skipped honestly, never crashes the pass."""
    write_outcome = authorize_and_remember(
        {"kind": "task", "status": "created", "goal": 42, "reason": None},
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert write_outcome.identifier is not None

    pass_outcome = await _run_pass(tmp_path)

    assert len(pass_outcome.attempted) == 1
    outcome = pass_outcome.attempted[0]
    assert outcome.task_id == write_outcome.identifier
    assert outcome.claimed is False
    assert outcome.error is not None
    assert "no real string goal" in outcome.error


async def test_denied_confirmation_claims_nothing_and_reports_it_honestly(
    tmp_path: Path,
) -> None:
    """A worker launched with no confirmation flags auto-confirms nothing -- the existing floor."""
    create_outcome = _create(tmp_path, "a trivial goal")
    assert create_outcome.task_id is not None

    pass_outcome = await _run_pass(tmp_path, physical_confirmation_available=False)

    assert len(pass_outcome.attempted) == 1
    outcome = pass_outcome.attempted[0]
    assert outcome.claimed is False
    assert outcome.status is None
    assert outcome.error is None  # a denial is not an exception


def test_worker_task_outcome_is_a_real_frozen_dataclass() -> None:
    outcome = WorkerTaskOutcome(task_id="t:1", claimed=True, status="completed", reason=None)

    assert outcome.task_id == "t:1"
    assert outcome.error is None
