"""Unit tests for jarvis.kernel.project: a typed-goal workflow atop planning.run_plan.

A fake ReasoningPort stands in for the real, default LocalReasoningAdapter
-- the true external-I/O edge -- exactly matching
`test_planning_kernel.py`'s own established discipline. Everything else
(the outer authorization gate, plan generation/validation, and the
real status-record write) runs for real.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
from jarvis.domain.evidence import Candidate
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import PLANNING_RUN_PLAN_CAPABILITY_ID
from jarvis.kernel.files import PathOutsideAllowedScopeError
from jarvis.kernel.project import (
    _CANONICAL_TO_PROJECT_STATE,
    VALID_PROJECT_STATES,
    authorize_and_get_project_status,
    authorize_and_start_project,
)
from jarvis.kernel.tasks import derive_result_status, write_task_record

if TYPE_CHECKING:
    import pytest

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
        "kind": "task",
        "goal": "a goal with nothing to do",
        "status": "completed",
        "reason": None,
        "created_at": _NOW.isoformat(),
        "updated_at": _NOW.isoformat(),
    }


async def test_a_malformed_plan_raises_and_still_records_a_failed_status(tmp_path: Path) -> None:
    """PlanningError propagates (matching plan run), but a real failed record lands first.

    WP-109: the raw, stored record's own ``status`` is the real,
    canonical ``"failed"`` -- not this module's own public ``"stuck"``
    word, which only ``ProjectStartOutcome.state``/the CLI's own
    printed text use (see module docstring). This proves the raw write
    path directly, not the translated return value.
    """
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
    assert data["kind"] == "task"
    assert data["status"] == "failed"
    assert "PlanningError" in data["reason"]
    assert "not valid JSON" in data["reason"]


async def test_a_plan_naming_an_unregistered_capability_raises_and_records_failed(
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
    assert data["status"] == "failed"


async def test_a_step_execution_exception_still_records_a_failed_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP-113 real regression test for the real gap named in this module's own docstring.

    Before WP-113, a real exception raised by a plan step's own
    execution (not PlanningError/PlanValidationError, the only two
    types the previous except clause caught) propagated out of
    authorize_and_start_project uncaught, leaving **no status record
    at all** for the goal -- this module writes no intermediate
    "running" record the way tasks.authorize_and_run_task does, so
    there was nothing even resembling "stuck" to find, just silence.
    This proves a real "failed" record now lands first.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "real_home")
    plan_response = '[{"capability_id": "fs.read_file", "arguments": {"path": "/etc/passwd"}}]'

    try:
        await _start(tmp_path, "read something outside scope", plan_response)
    except PathOutsideAllowedScopeError:
        pass
    else:
        msg = "Expected PathOutsideAllowedScopeError to propagate."
        raise AssertionError(msg)

    status = _status(tmp_path, "read something outside scope")
    assert status.record is not None
    data = status.record.value.value
    assert isinstance(data, dict)
    assert data["status"] == "failed"
    assert "PathOutsideAllowedScopeError" in data["reason"]


def test_status_for_an_unknown_goal_finds_nothing(tmp_path: Path) -> None:
    status = _status(tmp_path, "a goal never started")
    assert status.record is None
    assert status.decision.granted is True


def test_status_returns_the_most_recent_record_for_a_repeated_goal(tmp_path: Path) -> None:
    id_port = _SequentialIdPort()
    write_task_record(
        "a repeated goal",
        "failed",
        "first attempt failed",
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=tmp_path / "audit_chain.json",
        database_path=tmp_path / "memory.sqlite3",
        embedding_port=_FakeEmbeddingPort(),
        clock=_FakeClock(datetime(2026, 9, 8, 10, tzinfo=UTC)),
        id_port=id_port,
    )
    write_task_record(
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
    assert data["status"] == "completed"


async def test_start_reuses_planning_run_plan_effect_and_tier_exactly(tmp_path: Path) -> None:
    """Even a denied outer-gate Decision carries planning.run_plan's own real classification."""
    outcome = await _start(tmp_path, "x", "[]", physical_confirmation_available=False)

    assert outcome.decision.tier is Tier.CONFIRM
    assert outcome.decision.invocation.descriptor.id == PLANNING_RUN_PLAN_CAPABILITY_ID
    assert outcome.decision.invocation.descriptor.effects == Effect.EXECUTE


def test_valid_states_are_exactly_completed_and_stuck() -> None:
    assert VALID_PROJECT_STATES == ("completed", "stuck")


def test_canonical_to_project_state_maps_failed_to_stuck_and_completed_to_itself() -> None:
    """The one, real WP-109 translation point, tested directly against its own literal mapping."""
    assert _CANONICAL_TO_PROJECT_STATE == {"completed": "completed", "failed": "stuck"}


def test_an_aborted_plan_result_composes_into_the_public_stuck_state() -> None:
    """The full, composed pipeline: tasks.derive_result_status -> project's own translation.

    A pure, direct test of the ``aborted=True`` branch -- not
    reachable through the real registry today (every real
    ``PLAN_STEP_EXECUTORS`` entry is ``Tier.ALLOW``, which always
    grants), so this constructs the dataclasses directly, mirroring
    ``test_tasks_kernel.py``'s own identical-shaped test for
    ``derive_result_status`` alone. This test's own real point is one
    level up: proving this module's own translation step, composed
    with tasks.py's canonical derivation, produces exactly ``"stuck"``
    -- the real, end-to-end guarantee WP-109 exists to prove, not just
    assert about the dictionary in isolation.
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

    canonical_status, reason = derive_result_status(result)
    project_state = _CANONICAL_TO_PROJECT_STATE[canonical_status]

    assert canonical_status == "failed"
    assert project_state == "stuck"
    assert reason is not None
    assert "some.capability" in reason
    assert "NO_PHYSICAL_CONFIRMATION" in reason
