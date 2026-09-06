"""Unit tests for jarvis.application.planning.executor."""

from __future__ import annotations

from unittest import mock

import pytest

from jarvis.application.planning.executor import (
    PlanStepOutcome,
    PlanStepRecord,
    PlanValidationError,
    execute_plan,
)
from jarvis.application.planning.planner import PlanStep
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.audit import AuditChain
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.registry import CapabilityRegistry
from jarvis.kernel.capabilities import READ_FILE_CAPABILITY_ID, build_default_registry
from jarvis.kernel.capability_dispatch import PLAN_STEP_EXECUTORS

_TWO_STEPS = 2


def _orchestrator() -> AuthorizationOrchestrator:
    return AuthorizationOrchestrator(AuditChain(), build_default_registry())


def _decision(granted: bool, capability_id: str = "test.cap") -> Decision:
    invocation = CapabilityInvocation(
        CapabilityDescriptor(
            id=CapabilityId(capability_id), effects=Effect.READ_LOCAL, description="x"
        ),
        Tainted({}, Provenance.user()),
    )
    return Decision(
        tier=Tier.ALLOW,
        granted=granted,
        reasons=DecisionReason.BASE_TIER,
        invocation=invocation,
    )


def test_execute_plan_raises_when_a_step_names_an_unregistered_executor() -> None:
    """A step naming a capability with no entry in the supplied executors mapping fails pre-flight."""  # noqa: E501
    steps = (PlanStep(CapabilityId("git.commit"), {}),)

    with pytest.raises(PlanValidationError):
        execute_plan(
            steps,
            _orchestrator(),
            {},
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=mock.Mock(),
        )


def test_execute_plan_raises_when_a_step_tier_is_above_allow() -> None:
    """A step whose real descriptor tier is above Tier.ALLOW fails pre-flight, before any step runs."""  # noqa: E501
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDescriptor(
            id=READ_FILE_CAPABILITY_ID, effects=Effect.WRITE_LOCAL, description="fake, confirm-tier"
        )
    )
    orchestrator = AuthorizationOrchestrator(AuditChain(), registry)
    steps = (PlanStep(READ_FILE_CAPABILITY_ID, {"path": "/tmp/a.txt"}),)
    fake_executor = mock.Mock()

    with pytest.raises(PlanValidationError):
        execute_plan(
            steps,
            orchestrator,
            {READ_FILE_CAPABILITY_ID: fake_executor},
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=mock.Mock(),
        )
    fake_executor.assert_not_called()


def test_execute_plan_runs_every_step_when_all_are_granted() -> None:
    """Every step in a real, valid plan runs in order; aborted is False when all are granted."""
    steps = (
        PlanStep(READ_FILE_CAPABILITY_ID, {"path": "/tmp/a.txt"}),
        PlanStep(READ_FILE_CAPABILITY_ID, {"path": "/tmp/b.txt"}),
    )
    outcome = PlanStepOutcome(decision=_decision(granted=True), result=None)
    fake_executor = mock.Mock(return_value=outcome)

    result = execute_plan(
        steps,
        _orchestrator(),
        {READ_FILE_CAPABILITY_ID: fake_executor},
        physical_confirmation_available=True,
        remote_confirmation_available=False,
        chain_path=mock.Mock(),
    )

    assert result.aborted is False
    assert len(result.step_records) == _TWO_STEPS
    assert fake_executor.call_count == _TWO_STEPS
    assert all(isinstance(r, PlanStepRecord) and r.decision.granted for r in result.step_records)


def test_execute_plan_aborts_on_the_first_denied_step() -> None:
    """A denied step stops execution immediately; later steps are never attempted."""
    steps = (
        PlanStep(READ_FILE_CAPABILITY_ID, {"path": "/tmp/a.txt"}),
        PlanStep(READ_FILE_CAPABILITY_ID, {"path": "/tmp/b.txt"}),
    )
    fake_executor = mock.Mock(
        return_value=PlanStepOutcome(decision=_decision(granted=False), result=None)
    )

    result = execute_plan(
        steps,
        _orchestrator(),
        {READ_FILE_CAPABILITY_ID: fake_executor},
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=mock.Mock(),
    )

    assert result.aborted is True
    assert len(result.step_records) == 1
    assert fake_executor.call_count == 1
    assert result.step_records[0].decision.granted is False
    assert result.step_records[0].result is None


def test_execute_plan_empty_plan_runs_nothing_and_is_not_aborted() -> None:
    """An empty, real, valid plan runs zero steps and is not considered aborted."""
    result = execute_plan(
        (),
        _orchestrator(),
        {},
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=mock.Mock(),
    )

    assert result.aborted is False
    assert result.step_records == ()


def test_execute_plan_works_with_the_real_kernel_dispatch_registry() -> None:
    """A real, end-to-end smoke test: PLAN_STEP_EXECUTORS itself is a valid executors mapping."""
    steps = (PlanStep(READ_FILE_CAPABILITY_ID, {"path": "/tmp/a.txt"}),)
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_read_file") as fake:
        fake.return_value = mock.Mock(decision=_decision(granted=True))

        result = execute_plan(
            steps,
            _orchestrator(),
            PLAN_STEP_EXECUTORS,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=mock.Mock(),
        )

    assert result.aborted is False
    assert len(result.step_records) == 1
