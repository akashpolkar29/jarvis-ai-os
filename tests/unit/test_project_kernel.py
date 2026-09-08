"""Unit tests for jarvis.kernel.project: a typed-goal workflow atop planning.run_plan.

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter
-- the true external-I/O edge -- exactly matching
`test_planning_kernel.py`'s own established discipline. Everything else
(the outer authorization gate, plan generation/validation, and the
real status-record write) runs for real.
"""

from __future__ import annotations

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
from jarvis.kernel.capabilities import PLANNING_RUN_PLAN_CAPABILITY_ID
from jarvis.kernel.project import (
    VALID_PROJECT_STATES,
    _record_project_goal_state,
    _state_for_result,
    authorize_and_get_project_status,
    authorize_and_start_project,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt
    from jarvis.kernel.project import ProjectStartOutcome, ProjectStatusOutcome

_NOW = datetime(2026, 9, 8, tzinfo=UTC)


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
        self.calls: list[str] = []

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        self.calls.append(task)
        candidate = Candidate(author="test-provider", content=self._content)
        return Tainted(candidate, Provenance.system())


async def _start(  # noqa: PLR0913 -- one per fake-fixture pass-through
    tmp_path: Path,
    goal: str,
    plan_response: str,
    *,
    physical_confirmation_available: bool = True,
    remote_confirmation_available: bool = False,
    id_port: _SequentialIdPort | None = None,
) -> ProjectStartOutcome:
    return await authorize_and_start_project(
        goal,
        _FakeReasoningProvider(plan_response),
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=id_port or _SequentialIdPort(),
    )


def _status(tmp_path: Path, goal: str) -> ProjectStatusOutcome:
    return authorize_and_get_project_status(
        goal,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(),
        id_port=_SequentialIdPort(),
    )


async def test_denied_outer_gate_never_writes_a_status_record(tmp_path: Path) -> None:
    """planning.run_plan is Tier.CONFIRM -- no confirmation means denied, nothing recorded."""
    outcome = await _start(tmp_path, "do something", "[]", physical_confirmation_available=False)

    assert outcome.decision.granted is False
    assert outcome.state is None
    assert outcome.reason is None
    assert outcome.record_identifier is None

    status = _status(tmp_path, "do something")
    assert status.record is None


async def test_a_granted_zero_step_plan_completes_and_is_recorded(tmp_path: Path) -> None:
    """An empty plan is a valid, trivially-completed plan (planner.py's own documented behavior)."""
    outcome = await _start(tmp_path, "a goal with nothing to do", "[]")

    assert outcome.decision.granted is True
    assert outcome.state == "completed"
    assert outcome.reason is None
    assert outcome.record_identifier is not None

    status = _status(tmp_path, "a goal with nothing to do")
    assert status.record is not None
    data = status.record.value.value
    assert data == {
        "kind": "project_goal",
        "goal": "a goal with nothing to do",
        "state": "completed",
        "reason": None,
        "recorded_at": _NOW.isoformat(),
    }


async def test_a_malformed_plan_raises_and_still_records_a_stuck_status(tmp_path: Path) -> None:
    """PlanningError propagates (matching plan run), but a real stuck record lands first."""
    try:
        await _start(tmp_path, "an impossible goal", "not valid json")
    except PlanningError:
        pass
    else:
        msg = "Expected PlanningError to propagate."
        raise AssertionError(msg)

    status = _status(tmp_path, "an impossible goal")
    assert status.record is not None
    data = status.record.value.value
    assert isinstance(data, dict)
    assert data["kind"] == "project_goal"
    assert data["state"] == "stuck"
    assert "PlanningError" in data["reason"]
    assert "not valid JSON" in data["reason"]


async def test_a_plan_naming_an_unregistered_capability_raises_and_records_stuck(
    tmp_path: Path,
) -> None:
    """PlanningError for an unregistered capability id -- a second real trigger."""
    plan_response = '[{"capability_id": "not.a.real.capability", "arguments": {}}]'

    try:
        await _start(tmp_path, "a goal naming a fake capability", plan_response)
    except PlanningError:
        pass
    else:
        msg = "Expected PlanningError to propagate."
        raise AssertionError(msg)

    status = _status(tmp_path, "a goal naming a fake capability")
    assert status.record is not None
    data = status.record.value.value
    assert isinstance(data, dict)
    assert data["state"] == "stuck"


def test_status_for_an_unknown_goal_finds_nothing(tmp_path: Path) -> None:
    status = _status(tmp_path, "a goal never started")
    assert status.record is None
    assert status.decision.granted is True


def test_status_returns_the_most_recent_record_for_a_repeated_goal(tmp_path: Path) -> None:
    id_port = _SequentialIdPort()
    _record_project_goal_state(
        "a repeated goal",
        "stuck",
        "first attempt failed",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(datetime(2026, 9, 8, 10, tzinfo=UTC)),
        id_port=id_port,
    )
    _record_project_goal_state(
        "a repeated goal",
        "completed",
        None,
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(datetime(2026, 9, 8, 11, tzinfo=UTC)),
        id_port=id_port,
    )

    status = _status(tmp_path, "a repeated goal")
    assert status.record is not None
    data = status.record.value.value
    assert isinstance(data, dict)
    assert data["state"] == "completed"


async def test_start_reuses_planning_run_plan_effect_and_tier_exactly(tmp_path: Path) -> None:
    """Even a denied outer-gate Decision carries planning.run_plan's own real classification."""
    outcome = await _start(tmp_path, "x", "[]", physical_confirmation_available=False)

    assert outcome.decision.tier is Tier.CONFIRM
    assert outcome.decision.invocation.descriptor.id == PLANNING_RUN_PLAN_CAPABILITY_ID
    assert outcome.decision.invocation.descriptor.effects == Effect.EXECUTE


def test_valid_states_are_exactly_completed_and_stuck() -> None:
    assert VALID_PROJECT_STATES == ("completed", "stuck")


def test_state_for_result_reports_completed_when_not_aborted() -> None:
    result = PlanExecutionResult(step_records=(), aborted=False)
    assert _state_for_result(result) == ("completed", None)


def test_state_for_result_reports_stuck_with_reason_when_aborted() -> None:
    """A pure, direct test of the aborted=True branch -- not reachable through the real registry.

    Every real ``PLAN_STEP_EXECUTORS`` entry is ``Tier.ALLOW``, which
    always grants, so this constructs the dataclasses directly rather
    than trying to force it through ``authorize_and_start_project``.
    See ``kernel/project.py``'s own module docstring for the full
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

    state, reason = _state_for_result(result)

    assert state == "stuck"
    assert reason is not None
    assert "some.capability" in reason
    assert "NO_PHYSICAL_CONFIRMATION" in reason
