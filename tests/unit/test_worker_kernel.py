"""Unit tests for jarvis.kernel.worker: a real, minimal background-task worker (WP-120).

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter,
exactly matching `test_tasks_kernel.py`'s own established discipline.
Real, cross-process duplicate-claim proof lives separately, in
`test_tasks_claim_process_safety.py` -- these tests exercise
`run_pending_tasks_once`'s own discovery/delegation/bookkeeping logic
in a single process.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.memory import authorize_and_remember
from jarvis.kernel.tasks import (
    authorize_and_cancel_task,
    authorize_and_create_task,
    authorize_and_schedule_task,
    is_task_due,
)
from jarvis.kernel.worker import (
    WorkerPassOutcome,
    WorkerTaskOutcome,
    run_pending_tasks_once,
)

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


def _schedule(tmp_path: Path, task_id: str, scheduled_at: str) -> None:
    outcome = authorize_and_schedule_task(
        task_id,
        scheduled_at,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert outcome.scheduled is True


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


async def test_a_scheduled_task_not_yet_due_is_not_attempted(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a goal scheduled for the future")
    assert create_outcome.task_id is not None
    future = (_NOW + timedelta(hours=1)).isoformat()
    _schedule(tmp_path, create_outcome.task_id, future)

    pass_outcome = await _run_pass(tmp_path)

    assert pass_outcome.attempted == ()
    assert pass_outcome.claimed_count == 0


async def test_a_scheduled_task_exactly_at_now_is_due(tmp_path: Path) -> None:
    """The real, chosen policy is <=, not <, for "is this due yet"."""
    create_outcome = _create(tmp_path, "a goal scheduled for exactly now")
    assert create_outcome.task_id is not None
    _schedule(tmp_path, create_outcome.task_id, _NOW.isoformat())

    pass_outcome = await _run_pass(tmp_path)

    assert len(pass_outcome.attempted) == 1
    assert pass_outcome.attempted[0].status == "completed"


async def test_a_scheduled_task_in_the_past_is_due_and_runs_through_the_canonical_path(
    tmp_path: Path,
) -> None:
    """The real, chosen missed-schedule policy: past due is simply due, executed once, now."""
    create_outcome = _create(tmp_path, "a goal scheduled in the past")
    assert create_outcome.task_id is not None
    past = (_NOW - timedelta(hours=3)).isoformat()
    _schedule(tmp_path, create_outcome.task_id, past)

    pass_outcome = await _run_pass(tmp_path)

    assert len(pass_outcome.attempted) == 1
    outcome = pass_outcome.attempted[0]
    assert outcome.task_id == create_outcome.task_id
    assert outcome.claimed is True
    assert outcome.status == "completed"


async def test_a_scheduled_task_executes_only_once_even_across_several_passes(
    tmp_path: Path,
) -> None:
    create_outcome = _create(tmp_path, "a goal scheduled in the past, run once")
    assert create_outcome.task_id is not None
    past = (_NOW - timedelta(hours=3)).isoformat()
    _schedule(tmp_path, create_outcome.task_id, past)

    first_pass = await _run_pass(tmp_path)
    second_pass = await _run_pass(tmp_path)
    third_pass = await _run_pass(tmp_path)

    assert len(first_pass.attempted) == 1
    assert first_pass.attempted[0].status == "completed"
    assert second_pass.attempted == ()
    assert third_pass.attempted == ()


async def test_a_failed_scheduled_task_persists_failed_and_preserves_scheduled_at(
    tmp_path: Path,
) -> None:
    create_outcome = _create(tmp_path, "a goal scheduled in the past that fails")
    assert create_outcome.task_id is not None
    past = (_NOW - timedelta(hours=3)).isoformat()
    _schedule(tmp_path, create_outcome.task_id, past)

    pass_outcome = await _run_pass(tmp_path, plan_response="not valid json")

    assert len(pass_outcome.attempted) == 1
    outcome = pass_outcome.attempted[0]
    assert outcome.claimed is True
    assert outcome.error is not None
    assert "PlanningError" in outcome.error


async def test_a_cancelled_scheduled_task_is_never_discovered_or_run(tmp_path: Path) -> None:
    """Scheduling composes safely with cancellation via the existing, unmodified status filter."""
    create_outcome = _create(tmp_path, "a scheduled goal a human gave up on")
    assert create_outcome.task_id is not None
    past = (_NOW - timedelta(hours=3)).isoformat()
    _schedule(tmp_path, create_outcome.task_id, past)
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


async def test_an_unscheduled_task_is_attempted_immediately_unchanged_from_before_wp122(
    tmp_path: Path,
) -> None:
    """A task with scheduled_at=None (every task's own real default) is eligible immediately."""
    create_outcome = _create(tmp_path, "an ordinary, unscheduled goal")
    assert create_outcome.task_id is not None

    pass_outcome = await _run_pass(tmp_path)

    assert len(pass_outcome.attempted) == 1
    assert pass_outcome.attempted[0].status == "completed"


async def test_a_legacy_created_task_record_with_no_scheduled_at_key_is_immediately_eligible(
    tmp_path: Path,
) -> None:
    """Backward compatibility: a real pre-WP-122 record (no "scheduled_at" key at all)."""
    write_outcome = authorize_and_remember(
        {
            "kind": "task",
            "status": "created",
            "goal": "a legacy goal with no scheduled_at key",
            "reason": None,
        },
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
    assert outcome.claimed is True
    assert outcome.status == "completed"


def test_is_due_treats_a_non_dict_record_value_as_due() -> None:
    """A real, defensive branch -- never reachable via the real pipeline (see module docstring
    and `is_task_due`'s own, now living in `jarvis.kernel.tasks` per WP-124), since
    `authorize_and_list_tasks` already filters to real task dicts, but `is_task_due` is a
    general-purpose pure predicate, tested directly on its own terms."""
    assert is_task_due("not a dict", _NOW) is True


def test_is_due_treats_a_malformed_scheduled_at_string_as_due() -> None:
    """Mirrors `authorize_and_schedule_task`'s own real validation guarantee that this should
    never occur through the real write path -- still handled honestly, not assumed impossible."""
    data = {"kind": "task", "status": "created", "scheduled_at": "not a real timestamp"}
    assert is_task_due(data, _NOW) is True


def test_is_due_treats_no_scheduled_at_key_at_all_as_due() -> None:
    assert is_task_due({"kind": "task", "status": "created"}, _NOW) is True


def test_is_due_treats_a_none_scheduled_at_as_due() -> None:
    assert is_task_due({"kind": "task", "status": "created", "scheduled_at": None}, _NOW) is True


def test_is_due_treats_a_future_scheduled_at_as_not_due() -> None:
    future = (_NOW + timedelta(hours=1)).isoformat()
    assert is_task_due({"kind": "task", "status": "created", "scheduled_at": future}, _NOW) is False
