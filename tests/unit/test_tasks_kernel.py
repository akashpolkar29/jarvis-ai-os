"""Unit tests for jarvis.kernel.tasks: a real, persistent Task/TaskStore (WP-107).

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter
-- the true external-I/O edge -- exactly matching
`test_planning_kernel.py`'s/`test_project_kernel.py`'s own established
discipline.
"""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
from jarvis.domain.events import EventBus, TaskCreated, TaskStatusChanged
from jarvis.domain.evidence import Candidate
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.files import PathOutsideAllowedScopeError
from jarvis.kernel.memory import authorize_and_remember
from jarvis.kernel.tasks import (
    STALE_RUNNING_THRESHOLD_SECONDS,
    TASK_KIND,
    VALID_TASK_STATUSES,
    authorize_and_cancel_task,
    authorize_and_create_task,
    authorize_and_get_task,
    authorize_and_list_tasks,
    authorize_and_run_task,
    derive_result_status,
    update_task_status,
)

if TYPE_CHECKING:
    import pytest

    from jarvis.domain.evidence import Attempt
    from jarvis.kernel.tasks import (
        TaskCancelOutcome,
        TaskCreateOutcome,
        TaskGetOutcome,
        TaskRunOutcome,
    )

_NOW = datetime(2026, 9, 9, tzinfo=UTC)
_ALL_TASKS_COUNT = 2
_EXPECTED_TRANSITION_COUNT = 2


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


def _create(  # noqa: PLR0913 -- one per fake-fixture pass-through
    tmp_path: Path,
    goal: str,
    *,
    physical_confirmation_available: bool = True,
    remote_confirmation_available: bool = False,
    id_port: _SequentialIdPort | None = None,
    event_bus: EventBus | None = None,
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
        event_bus=event_bus,
    )


def _cancel(
    tmp_path: Path,
    task_id: str,
    *,
    physical_confirmation_available: bool = True,
    remote_confirmation_available: bool = False,
) -> TaskCancelOutcome:
    return authorize_and_cancel_task(
        task_id,
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
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
    event_bus: EventBus | None = None,
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
        event_bus=event_bus,
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


async def test_run_on_a_step_execution_exception_marks_the_task_failed_not_stuck_at_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP-113 real regression test for the real, named "stuck at running" bug.

    A structurally-valid plan naming a real, wired PLAN_STEP_EXECUTORS
    capability (fs.read_file) whose own real execution raises
    PathOutsideAllowedScopeError -- not a PlanningError/PlanValidationError,
    the two exception types the pre-WP-113 except clause alone caught.
    Before this fix, this exact scenario left the task's own stored
    status at "running" permanently; this proves it now lands at
    "failed" with the real exception surfaced as the reason, and that
    the same, real, unmodified exception still propagates to the caller.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "real_home")
    create_outcome = _create(tmp_path, "read something outside scope")
    assert create_outcome.task_id is not None

    plan_response = json.dumps(
        [{"capability_id": "fs.read_file", "arguments": {"path": "/etc/passwd"}}]
    )
    try:
        await _run(tmp_path, create_outcome.task_id, "read something outside scope", plan_response)
    except PathOutsideAllowedScopeError:
        pass
    else:
        msg = "Expected PathOutsideAllowedScopeError to propagate."
        raise AssertionError(msg)

    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    data = get_outcome.record.value.value
    assert isinstance(data, dict)
    assert data["status"] == "failed"
    assert "PathOutsideAllowedScopeError" in data["reason"]


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


def _set_running_at(tmp_path: Path, task_id: str, goal: str, when: datetime) -> None:
    """Force a real task record's own stored status to "running" with a fixed `updated_at`.

    Mirrors what a real, genuinely-crashed `authorize_and_run_task`
    call would have left behind -- a record stuck at `"running"`, last
    touched at `when`, never revisited by any later call in any
    process. Uses `update_task_status` directly (the same, real,
    shared helper `authorize_and_run_task` itself calls), not a
    hand-built record, so this exercises the real write path.
    """
    update_task_status(
        task_id,
        goal,
        "running",
        None,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(when),
        id_port=_SequentialIdPort(),
    )


def test_get_reports_a_running_task_as_stale_once_past_the_real_threshold(
    tmp_path: Path,
) -> None:
    """WP-116: a "running" task untouched for over the real, documented threshold is flagged."""
    create_outcome = _create(tmp_path, "a goal")
    assert create_outcome.task_id is not None
    stuck_at = _NOW
    _set_running_at(tmp_path, create_outcome.task_id, "a goal", stuck_at)

    just_under = stuck_at + timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS - 1)
    still_fresh = authorize_and_get_task(
        create_outcome.task_id,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(just_under),
        id_port=_SequentialIdPort(),
    )
    assert still_fresh.record is not None
    assert still_fresh.record.value.value["status"] == "running"  # type: ignore[index]
    assert still_fresh.stale is False

    just_over = stuck_at + timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS + 1)
    now_stale = authorize_and_get_task(
        create_outcome.task_id,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(just_over),
        id_port=_SequentialIdPort(),
    )
    assert now_stale.stale is True
    # The real, stored status itself is never touched by detection alone.
    assert now_stale.record is not None
    assert now_stale.record.value.value["status"] == "running"  # type: ignore[index]


async def test_get_of_a_completed_task_is_never_reported_stale_no_matter_how_old(
    tmp_path: Path,
) -> None:
    """WP-116: staleness only ever applies to "running" -- a real, finished task never qualifies."""
    create_outcome = _create(tmp_path, "a goal")
    assert create_outcome.task_id is not None
    run_outcome = await _run(tmp_path, create_outcome.task_id, "a goal", "[]")
    assert run_outcome.status == "completed"

    far_future = _NOW + timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS * 100)
    outcome = authorize_and_get_task(
        create_outcome.task_id,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(far_future),
        id_port=_SequentialIdPort(),
    )
    assert outcome.stale is False


def test_get_of_a_recently_running_task_is_not_yet_stale(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a goal")
    assert create_outcome.task_id is not None
    _set_running_at(tmp_path, create_outcome.task_id, "a goal", _NOW)

    outcome = _get(tmp_path, create_outcome.task_id)
    assert outcome.record is not None
    assert outcome.stale is False


def test_list_reports_stale_task_ids_for_running_tasks_past_the_threshold(
    tmp_path: Path,
) -> None:
    id_port = _SequentialIdPort()
    stale_one = _create(tmp_path, "stale goal", id_port=id_port)
    fresh_one = _create(tmp_path, "fresh goal", id_port=id_port)
    assert stale_one.task_id is not None
    assert fresh_one.task_id is not None
    _set_running_at(tmp_path, stale_one.task_id, "stale goal", _NOW)
    _set_running_at(tmp_path, fresh_one.task_id, "fresh goal", _NOW)

    later = _NOW + timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS + 1)
    list_outcome = authorize_and_list_tasks(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(later),
        id_port=id_port,
    )

    assert list_outcome.stale_task_ids == {stale_one.task_id, fresh_one.task_id}


def test_list_reports_no_stale_task_ids_when_nothing_is_running(tmp_path: Path) -> None:
    id_port = _SequentialIdPort()
    create_outcome = _create(tmp_path, "a goal", id_port=id_port)
    assert create_outcome.task_id is not None

    far_future = _NOW + timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS * 100)
    list_outcome = authorize_and_list_tasks(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(far_future),
        id_port=id_port,
    )

    assert list_outcome.stale_task_ids == frozenset()


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


# ---------------------------------------------------------------------------
# WP-111: real task lifecycle transitions emit real events, proven against
# the real authorize_and_create_task/authorize_and_run_task call chain --
# never a fake, hand-constructed Task object standing in for the real thing.
# ---------------------------------------------------------------------------


def test_a_granted_task_creation_publishes_a_real_task_created_event(tmp_path: Path) -> None:
    bus = EventBus()
    received: list[TaskCreated] = []
    bus.subscribe(TaskCreated, received.append)

    outcome = _create(tmp_path, "build a thing", event_bus=bus)

    assert outcome.task_id is not None
    assert len(received) == 1
    event = received[0]
    assert event.task_id == outcome.task_id
    assert event.goal == "build a thing"
    assert event.status == "created"
    assert event.timestamp == _NOW.isoformat()


def test_a_denied_task_creation_publishes_no_event_at_all(tmp_path: Path) -> None:
    """No real state change happened -- there must be nothing for an event to describe."""
    bus = EventBus()
    received: list[TaskCreated] = []
    bus.subscribe(TaskCreated, received.append)

    outcome = _create(
        tmp_path, "build a thing", physical_confirmation_available=False, event_bus=bus
    )

    assert outcome.task_id is None
    assert received == []


async def test_running_a_task_to_completion_publishes_real_status_changed_events_in_order(
    tmp_path: Path,
) -> None:
    """A real authorize_and_run_task call on a zero-step plan: created -> running -> completed."""
    bus = EventBus()
    created_events: list[TaskCreated] = []
    changed_events: list[TaskStatusChanged] = []
    bus.subscribe(TaskCreated, created_events.append)
    bus.subscribe(TaskStatusChanged, changed_events.append)

    create_outcome = _create(tmp_path, "a trivial goal", event_bus=bus)
    assert create_outcome.task_id is not None

    run_outcome = await _run(
        tmp_path, create_outcome.task_id, "a trivial goal", "[]", event_bus=bus
    )

    assert run_outcome.status == "completed"
    assert len(created_events) == 1
    assert created_events[0].status == "created"
    # Exactly two real transitions for a zero-step plan: created -> running, running -> completed.
    assert len(changed_events) == _EXPECTED_TRANSITION_COUNT
    assert changed_events[0].previous_status == "created"
    assert changed_events[0].new_status == "running"
    assert changed_events[1].previous_status == "running"
    assert changed_events[1].new_status == "completed"
    for event in changed_events:
        assert event.task_id == create_outcome.task_id
        assert event.goal == "a trivial goal"


async def test_a_malformed_plan_publishes_a_real_failed_status_changed_event(
    tmp_path: Path,
) -> None:
    """A real PlanningError still leaves a real, observable created -> running -> failed trail."""
    bus = EventBus()
    changed_events: list[TaskStatusChanged] = []
    bus.subscribe(TaskStatusChanged, changed_events.append)

    create_outcome = _create(tmp_path, "an impossible goal", event_bus=bus)
    assert create_outcome.task_id is not None

    with contextlib.suppress(PlanningError):
        await _run(
            tmp_path,
            create_outcome.task_id,
            "an impossible goal",
            "not valid json",
            event_bus=bus,
        )

    assert len(changed_events) == _EXPECTED_TRANSITION_COUNT
    assert changed_events[0].new_status == "running"
    assert changed_events[1].previous_status == "running"
    assert changed_events[1].new_status == "failed"
    assert changed_events[1].reason is not None
    assert "PlanningError" in changed_events[1].reason


async def test_a_denied_running_transition_publishes_no_status_changed_event(
    tmp_path: Path,
) -> None:
    """No real state change happened (the task stays "created") -- nothing real to describe."""
    bus = EventBus()
    changed_events: list[TaskStatusChanged] = []
    bus.subscribe(TaskStatusChanged, changed_events.append)

    create_outcome = _create(tmp_path, "a goal nobody confirms", event_bus=bus)
    assert create_outcome.task_id is not None

    run_outcome = await _run(
        tmp_path,
        create_outcome.task_id,
        "a goal nobody confirms",
        "[]",
        physical_confirmation_available=False,
        event_bus=bus,
    )

    assert run_outcome.decision.granted is False
    assert changed_events == []


def test_omitting_event_bus_is_a_harmless_no_op_matching_prior_behavior(tmp_path: Path) -> None:
    """Every existing caller that never passes event_bus behaves exactly as before this change."""
    outcome = _create(tmp_path, "build a thing")  # no event_bus at all

    assert outcome.task_id is not None  # unchanged, real behavior -- no crash, no new requirement


def test_cancel_of_a_created_task_transitions_it_to_cancelled(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a goal nobody wants anymore")
    assert create_outcome.task_id is not None

    cancel_outcome = _cancel(tmp_path, create_outcome.task_id)

    assert cancel_outcome.cancelled is True
    assert cancel_outcome.decision.granted is True
    assert cancel_outcome.reason is None

    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    data = get_outcome.record.value.value
    assert isinstance(data, dict)
    assert data["status"] == "cancelled"
    assert data["goal"] == "a goal nobody wants anymore"
    assert data["created_at"] == _NOW.isoformat()  # preserved, not clobbered


def test_cancel_of_a_stale_running_task_transitions_it_to_cancelled(tmp_path: Path) -> None:
    """A human giving up on a task whose owning process has already died (WP-116's own signal)."""
    create_outcome = _create(tmp_path, "a task whose process died")
    assert create_outcome.task_id is not None
    long_ago = _NOW - timedelta(seconds=STALE_RUNNING_THRESHOLD_SECONDS + 1)
    _set_running_at(tmp_path, create_outcome.task_id, "a task whose process died", long_ago)

    cancel_outcome = _cancel(tmp_path, create_outcome.task_id)

    assert cancel_outcome.cancelled is True
    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    assert get_outcome.record.value.value["status"] == "cancelled"  # type: ignore[index]
    assert get_outcome.stale is False  # no longer "running" at all, so no longer stale either


def test_cancel_of_an_unknown_task_id_reports_not_found(tmp_path: Path) -> None:
    cancel_outcome = _cancel(tmp_path, "task:no-such-id")

    assert cancel_outcome.cancelled is False
    assert cancel_outcome.reason == "No task found for this identifier."
    assert cancel_outcome.decision.granted is True  # the lookup itself is Tier.ALLOW


async def test_cancel_of_an_already_completed_task_is_refused_and_writes_nothing(
    tmp_path: Path,
) -> None:
    create_outcome = _create(tmp_path, "a trivial goal")
    assert create_outcome.task_id is not None
    await _run(tmp_path, create_outcome.task_id, "a trivial goal", "[]")

    cancel_outcome = _cancel(tmp_path, create_outcome.task_id)

    assert cancel_outcome.cancelled is False
    assert cancel_outcome.reason == "Task is already 'completed' and cannot be cancelled."

    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    assert get_outcome.record.value.value["status"] == "completed"  # type: ignore[index]


def test_cancel_of_an_already_cancelled_task_is_refused(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "cancel me twice")
    assert create_outcome.task_id is not None
    first = _cancel(tmp_path, create_outcome.task_id)
    assert first.cancelled is True

    second = _cancel(tmp_path, create_outcome.task_id)

    assert second.cancelled is False
    assert second.reason == "Task is already 'cancelled' and cannot be cancelled."


def test_cancel_denied_without_confirmation_leaves_the_task_at_created(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a goal")
    assert create_outcome.task_id is not None

    cancel_outcome = _cancel(
        tmp_path, create_outcome.task_id, physical_confirmation_available=False
    )

    assert cancel_outcome.cancelled is False
    assert cancel_outcome.decision.granted is False
    assert cancel_outcome.reason == "Cancellation was not authorized."

    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    assert get_outcome.record.value.value["status"] == "created"  # type: ignore[index]


def test_cancel_publishes_a_real_status_changed_event(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a goal")
    assert create_outcome.task_id is not None
    published: list[TaskStatusChanged] = []
    bus = EventBus()
    bus.subscribe(TaskStatusChanged, published.append)

    outcome = authorize_and_cancel_task(
        create_outcome.task_id,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
        event_bus=bus,
    )

    assert outcome.cancelled is True
    assert len(published) == 1
    assert published[0].previous_status == "created"
    assert published[0].new_status == "cancelled"


def test_cancel_refused_for_a_terminal_status_publishes_no_event(tmp_path: Path) -> None:
    create_outcome = _create(tmp_path, "a goal")
    assert create_outcome.task_id is not None
    _cancel(tmp_path, create_outcome.task_id)  # first cancel: created -> cancelled
    published: list[TaskStatusChanged] = []
    bus = EventBus()
    bus.subscribe(TaskStatusChanged, published.append)

    outcome = authorize_and_cancel_task(
        create_outcome.task_id,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
        event_bus=bus,
    )

    assert outcome.cancelled is False
    assert published == []


async def test_run_refuses_to_resume_an_already_cancelled_task(tmp_path: Path) -> None:
    """WP-118: the real gap WP-117 itself opened -- run must not silently undo a cancel."""
    create_outcome = _create(tmp_path, "a goal a human gave up on")
    assert create_outcome.task_id is not None
    cancel_outcome = _cancel(tmp_path, create_outcome.task_id)
    assert cancel_outcome.cancelled is True

    run_outcome = await _run(tmp_path, create_outcome.task_id, "a goal a human gave up on", "[]")

    assert run_outcome.status == "cancelled"
    assert run_outcome.reason == "Task was cancelled; run refuses to resume a cancelled task."
    assert run_outcome.decision.granted is True  # the memory.get lookup, always Tier.ALLOW

    get_outcome = _get(tmp_path, create_outcome.task_id)
    assert get_outcome.record is not None
    assert get_outcome.record.value.value["status"] == "cancelled"  # type: ignore[index]


async def test_run_publishes_no_status_changed_event_for_an_already_cancelled_task(
    tmp_path: Path,
) -> None:
    create_outcome = _create(tmp_path, "a goal")
    assert create_outcome.task_id is not None
    _cancel(tmp_path, create_outcome.task_id)
    published: list[TaskStatusChanged] = []
    bus = EventBus()
    bus.subscribe(TaskStatusChanged, published.append)

    await _run(tmp_path, create_outcome.task_id, "a goal", "[]", event_bus=bus)

    assert published == []


async def test_run_still_works_normally_on_a_task_that_was_never_cancelled(
    tmp_path: Path,
) -> None:
    """The new WP-118 lookup must not change behavior for the ordinary, non-cancelled path."""
    create_outcome = _create(tmp_path, "a trivial goal")
    assert create_outcome.task_id is not None

    run_outcome = await _run(tmp_path, create_outcome.task_id, "a trivial goal", "[]")

    assert run_outcome.status == "completed"
    assert run_outcome.reason is None
