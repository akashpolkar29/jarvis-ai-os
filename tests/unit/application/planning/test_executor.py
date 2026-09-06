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
from jarvis.kernel.capabilities import (
    MEMORY_WIPE_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
    build_default_registry,
)
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


def test_a_real_manual_only_capability_not_wired_is_rejected_before_authorization() -> None:
    """Adversarial verification (ADR-0062): memory.wipe (real, MANUAL_ONLY) has no executor wired.

    Confirms the FIRST of the executor's own two real, independent
    guards: `memory.wipe` is not in `PLAN_STEP_EXECUTORS` at all today,
    so a plan step naming it is rejected via the "no registered
    executor" check, before `get_descriptor`/`authorize_by_id` is ever
    reached -- not because of its tier specifically, but because it is
    simply not a wired capability. Nothing is authorized, nothing is
    executed, no memory-wipe side effect of any kind occurs.
    """
    steps = (PlanStep(MEMORY_WIPE_CAPABILITY_ID, {}),)

    with pytest.raises(PlanValidationError):
        execute_plan(
            steps,
            _orchestrator(),
            PLAN_STEP_EXECUTORS,
            physical_confirmation_available=True,
            remote_confirmation_available=True,
            chain_path=mock.Mock(),
        )


def test_a_real_manual_only_capability_if_hypothetically_wired_still_fails_the_tier_check() -> None:
    """Adversarial verification (ADR-0062): the tier check is a real, second, independent guard.

    Simulates the exact scenario ADR-0062's own text flags as a real
    risk: a future, careless addition of a non-ALLOW capability to a
    plan-step-executors mapping. `memory.wipe`'s own REAL descriptor
    (read from the real, live `build_default_registry()`, not a fake
    one) is `Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`, always
    `Tier.MANUAL_ONLY` -- confirms the tier check independently catches
    this even when a capability *is* present in the executors mapping,
    and that the hypothetical executor itself is never called (no
    silent mis-authorization, no crash, no real side effect).
    """
    hypothetically_wired_executor = mock.Mock()
    steps = (PlanStep(MEMORY_WIPE_CAPABILITY_ID, {}),)

    with pytest.raises(PlanValidationError):
        execute_plan(
            steps,
            _orchestrator(),
            {MEMORY_WIPE_CAPABILITY_ID: hypothetically_wired_executor},
            physical_confirmation_available=True,
            remote_confirmation_available=True,
            chain_path=mock.Mock(),
        )
    hypothetically_wired_executor.assert_not_called()


def test_a_dynamic_effect_capability_not_in_the_static_registry_is_rejected_cleanly() -> None:
    """Adversarial verification: a plan step naming a real, dynamic-effect, unregistered capability.

    `communications.send_email` is deliberately never in
    `build_default_registry()` (its real Effect varies per invocation
    -- see `kernel/capabilities.py`'s own comment). Confirms this is
    still a clean `PlanValidationError`, caught by the "no registered
    executor" check before `get_descriptor` would otherwise raise
    `CapabilityNotRegistered` uncaught -- not a crash, not an
    unhandled exception escaping `execute_plan`.
    """
    steps = (PlanStep(CapabilityId("communications.send_email"), {}),)

    with pytest.raises(PlanValidationError):
        execute_plan(
            steps,
            _orchestrator(),
            PLAN_STEP_EXECUTORS,
            physical_confirmation_available=True,
            remote_confirmation_available=True,
            chain_path=mock.Mock(),
        )
