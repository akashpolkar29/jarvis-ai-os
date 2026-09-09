"""Unit tests for jarvis.kernel.tasks: a real, persistent Task/TaskStore (WP-107).

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter
-- the true external-I/O edge -- exactly matching
`test_planning_kernel.py`'s/`test_project_kernel.py`'s own established
discipline.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from jarvis.application.planning.executor import PlanExecutionResult, PlanStepRecord
from jarvis.application.planning.planner import PlanningError, PlanStep
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.evidence import Candidate
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.memory import authorize_and_remember
from jarvis.kernel.tasks import (
    TASK_KIND,
    VALID_TASK_STATUSES,
    authorize_and_create_task,
    authorize_and_get_task,
    authorize_and_list_tasks,
    authorize_and_run_task,
    derive_result_status,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt
    from jarvis.kernel.tasks import TaskCreateOutcome, TaskGetOutcome, TaskRunOutcome

_NOW = datetime(2026, 9, 9, tzinfo=UTC)
_ALL_TASKS_COUNT = 2


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


def _create(
    tmp_path: Path,
    goal: str,
    *,
    physical_confirmation_available: bool = True,
    remote_confirmation_available: bool = False,
    id_port: _SequentialIdPort | None = None,
) -> TaskCreateOutcome:
    return authorize_and_create_task(
        goal,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port or _SequentialIdPort(),
    )


def _get(tmp_path: Path, task_id: str) -> TaskGetOutcome:
    return authorize_and_get_task(
        task_id,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )


async def _run(  # noqa: PLR0913 -- one per fake-fixture pass-through
    tmp_path: Path,
    task_id: str,
    goal: str,
    plan_response: str,
    *,
    physical_confirmation_available: bool = True,
    remote_confirmation_available: bool = False,
) -> TaskRunOutcome:
    return await authorize_and_run_task(
        task_id,
        goal,
        _FakeReasoningProvider(plan_response),
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )


def test_create_writes_a_real_task_with_status_created(tmp_path: Path) -> None:
    outcome = _create(tmp_path, "build a thing")

    assert outcome.decision.granted is True
    assert outcome.task_id is not None

    get_outcome = _get(tmp_path, outcome.task_id)
    assert get_outcome.record is not None
    data = get_outcome.record.value.value
    assert data == {
        "kind": TASK_KIND,
        "goal": "build a thing",
        "status": "created",
        "reason": None,
        "created_at": _NOW.isoformat(),
        "updated_at": _NOW.isoformat(),
    }


def test_create_denied_without_confirmation_writes_nothing(tmp_path: Path) -> None:
    outcome = _create(tmp_path, "build a thing", physical_confirmation_available=False)

    assert outcome.decision.granted is False
    assert outcome.task_id is None


async def test_run_on_a_zero_step_plan_completes_and_preserves_created_at(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a trivial goal")
    assert create_outcome.task_id is not None

    run_outcome = await _run(tmp_path, create_outcome.task_id, "a trivial goal", "[]")

    assert run_outcome.decision.granted is True
    assert run_outcome.status == "completed"
    assert run_outcome.reason is None

    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    data = get_outcome.record.value.value
    assert isinstance(data, dict)
    assert data["status"] == "completed"
    # The real bug this proves fixed: update_task_status must preserve
    # created_at across a transition, not silently drop it via a blind
    # overwrite (update_value replaces the whole stored value).
    assert data["created_at"] == _NOW.isoformat()


async def test_run_on_a_malformed_plan_raises_and_marks_the_task_failed(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "an impossible goal")
    assert create_outcome.task_id is not None

    try:
        await _run(tmp_path, create_outcome.task_id, "an impossible goal", "not valid json")
    except PlanningError:
        pass
    else:
        msg = "Expected PlanningError to propagate."
        raise AssertionError(msg)

    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    data = get_outcome.record.value.value
    assert isinstance(data, dict)
    assert data["status"] == "failed"
    assert "PlanningError" in data["reason"]


async def test_run_denied_without_confirmation_leaves_the_task_at_created(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a goal nobody confirms")
    assert create_outcome.task_id is not None

    run_outcome = await _run(
        tmp_path,
        create_outcome.task_id,
        "a goal nobody confirms",
        "[]",
        physical_confirmation_available=False,
    )

    assert run_outcome.decision.granted is False
    assert run_outcome.status is None

    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    data = get_outcome.record.value.value
    assert isinstance(data, dict)
    assert data["status"] == "created"


def test_get_of_an_unknown_task_id_returns_none(tmp_path: Path) -> None:
    outcome = _get(tmp_path, "no-such-id")
    assert outcome.record is None


def test_get_ignores_a_non_task_memory_record(tmp_path: Path) -> None:
    write_outcome = authorize_and_remember(
        "an ordinary memory, not a task",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )
    assert write_outcome.identifier is not None

    outcome = _get(tmp_path, write_outcome.identifier)
    assert outcome.record is None


async def test_list_filters_by_status_and_ignores_ordinary_memories(tmp_path: Path) -> None:
    id_port = _SequentialIdPort()
    completed = _create(tmp_path, "task one", id_port=id_port)
    stuck = _create(tmp_path, "task two", id_port=id_port)
    assert completed.task_id is not None
    assert stuck.task_id is not None

    await _run(tmp_path, completed.task_id, "task one", "[]")
    with contextlib.suppress(PlanningError):
        await _run(tmp_path, stuck.task_id, "task two", "not valid json")

    authorize_and_remember(
        "prefers tabs",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )

    all_tasks = authorize_and_list_tasks(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )
    assert len(all_tasks.records) == _ALL_TASKS_COUNT

    completed_only = authorize_and_list_tasks(
        status="completed",
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port,
    )
    assert len(completed_only.records) == 1
    assert completed_only.records[0].identifier == completed.task_id


def test_derive_result_status_reports_completed_when_not_aborted() -> None:
    result = PlanExecutionResult(step_records=(), aborted=False)
    assert derive_result_status(result) == ("completed", None)


def test_derive_result_status_reports_failed_with_reason_when_aborted() -> None:
    """A pure, direct test of the aborted=True branch -- not reachable through the real registry.

    Every real ``PLAN_STEP_EXECUTORS`` entry is ``Tier.ALLOW``, which
    always grants, so this constructs the dataclasses directly rather
    than trying to force it through ``authorize_and_run_task``. See
    ``kernel/project.py``'s own identical precedent for the full
    reasoning.
    """
    descriptor = CapabilityDescriptor(
        id=CapabilityId("some.capability"),
        effects=Effect.WRITE_LOCAL,
        description="A test capability.",
    )
    invocation = CapabilityInvocation(descriptor, Tainted({}, Provenance.user()))
    denied_decision = Decision(
        tier=Tier.CONFIRM,
        granted=False,
        reasons=DecisionReason.NO_PHYSICAL_CONFIRMATION,
        invocation=invocation,
    )
    step = PlanStep(capability_id=CapabilityId("some.capability"), arguments={})
    record = PlanStepRecord(step=step, decision=denied_decision, result=None)
    result = PlanExecutionResult(step_records=(record,), aborted=True)

    status, reason = derive_result_status(result)

    assert status == "failed"
    assert reason is not None
    assert "some.capability" in reason
    assert "NO_PHYSICAL_CONFIRMATION" in reason


def test_valid_task_statuses_are_exactly_the_documented_six() -> None:
    assert VALID_TASK_STATUSES == (
        "created",
        "running",
        "waiting_approval",
        "completed",
        "failed",
        "cancelled",
    )
