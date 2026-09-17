"""Unit tests for jarvis.application.workflow.composer."""

from __future__ import annotations

from unittest import mock

import pytest

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.application.planning.planner import PlanStep
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.application.workflow.composer import (
    WorkflowCompositionError,
    compose_workflow,
    resolve_step_arguments,
)
from jarvis.domain.audit import AuditChain
from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, Effect
from jarvis.domain.registry import CapabilityRegistry
from jarvis.domain.workflow import WorkflowDescriptor, WorkflowId, WorkflowStep

ALLOW_CAPABILITY_ID = CapabilityId("test.allow_step")
ANOTHER_ALLOW_CAPABILITY_ID = CapabilityId("test.another_allow_step")
CONFIRM_CAPABILITY_ID = CapabilityId("test.confirm_step")
UNREGISTERED_CAPABILITY_ID = CapabilityId("test.unregistered_step")


def _capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDescriptor(
            id=ALLOW_CAPABILITY_ID, effects=Effect.READ_LOCAL, description="A test ALLOW step."
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=ANOTHER_ALLOW_CAPABILITY_ID,
            effects=Effect.READ_LOCAL,
            description="Another test ALLOW step.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=CONFIRM_CAPABILITY_ID, effects=Effect.EXECUTE, description="A test CONFIRM step."
        )
    )
    return registry


def _orchestrator(capabilities: CapabilityRegistry | None = None) -> AuthorizationOrchestrator:
    return AuthorizationOrchestrator(
        AuditChain(), capabilities or _capability_registry(), clock=SystemClockAdapter()
    )


def _step(capability_id: CapabilityId, **overrides: object) -> WorkflowStep:
    defaults: dict[str, object] = {
        "capability_id": capability_id,
        "arguments": {},
        "description": f"Run {capability_id}.",
    }
    defaults.update(overrides)
    return WorkflowStep(**defaults)  # type: ignore[arg-type]


def _workflow(*steps: WorkflowStep) -> WorkflowDescriptor:
    return WorkflowDescriptor(
        id=WorkflowId("test_workflow"), name="Test", description="A test workflow.", steps=steps
    )


def test_resolve_step_arguments_substitutes_known_placeholder() -> None:
    """A "${name}" value is replaced by the matching supplied parameter."""
    step = _step(ALLOW_CAPABILITY_ID, arguments={"query": "${company}"})

    resolved = resolve_step_arguments(step, {"company": "Acme"})

    assert resolved == {"query": "Acme"}


def test_resolve_step_arguments_leaves_non_placeholder_values_untouched() -> None:
    """A plain value, or a string not exactly matching "${name}", is carried through verbatim."""
    step = _step(ALLOW_CAPABILITY_ID, arguments={"limit": 5, "note": "see ${company} above"})

    resolved = resolve_step_arguments(step, {"company": "Acme"})

    assert resolved == {"limit": 5, "note": "see ${company} above"}


def test_resolve_step_arguments_raises_on_unknown_parameter() -> None:
    """A placeholder naming a parameter that was not supplied is a real composition error."""
    step = _step(ALLOW_CAPABILITY_ID, arguments={"query": "${missing}"})

    with pytest.raises(WorkflowCompositionError, match="missing"):
        resolve_step_arguments(step, {})


def test_compose_workflow_runs_every_step_when_all_are_allow_tier() -> None:
    """A workflow whose every step is Tier.ALLOW and wired is entirely runnable, nothing halts."""
    workflow = _workflow(_step(ALLOW_CAPABILITY_ID), _step(ANOTHER_ALLOW_CAPABILITY_ID))
    executors = {ALLOW_CAPABILITY_ID: mock.Mock(), ANOTHER_ALLOW_CAPABILITY_ID: mock.Mock()}

    composed = compose_workflow(workflow, {}, _orchestrator(), executors)

    assert len(composed.runnable_steps) == len(workflow.steps)
    assert all(isinstance(s, PlanStep) for s in composed.runnable_steps)
    assert composed.halted_step is None
    assert composed.remaining_steps == ()


def test_compose_workflow_halts_at_a_capability_with_no_registered_executor() -> None:
    """A step naming a capability with no entry in the supplied executors mapping halts, never runs."""  # noqa: E501
    workflow = _workflow(_step(ALLOW_CAPABILITY_ID), _step(ANOTHER_ALLOW_CAPABILITY_ID))
    # ANOTHER_ALLOW_CAPABILITY_ID deliberately absent from executors below
    executors = {ALLOW_CAPABILITY_ID: mock.Mock()}

    composed = compose_workflow(workflow, {}, _orchestrator(), executors)

    assert len(composed.runnable_steps) == 1
    assert composed.halted_step is not None
    assert composed.halted_step.capability_id == ANOTHER_ALLOW_CAPABILITY_ID
    assert composed.remaining_steps == ()


def test_compose_workflow_halts_at_an_unregistered_capability() -> None:
    """A step naming a capability id that is not registered at all halts, never runs."""
    workflow = _workflow(_step(UNREGISTERED_CAPABILITY_ID))
    executors = {UNREGISTERED_CAPABILITY_ID: mock.Mock()}

    composed = compose_workflow(workflow, {}, _orchestrator(), executors)

    assert composed.runnable_steps == ()
    assert composed.halted_step is not None
    assert composed.halted_step.capability_id == UNREGISTERED_CAPABILITY_ID


def test_compose_workflow_halts_at_a_confirm_tier_step_and_never_silently_executes_it() -> None:
    """A CONFIRM+ step is never included in runnable_steps -- it becomes the halt point instead."""
    workflow = _workflow(_step(ALLOW_CAPABILITY_ID), _step(CONFIRM_CAPABILITY_ID))
    executors = {ALLOW_CAPABILITY_ID: mock.Mock(), CONFIRM_CAPABILITY_ID: mock.Mock()}

    composed = compose_workflow(workflow, {}, _orchestrator(), executors)

    assert len(composed.runnable_steps) == 1
    assert composed.halted_step is not None
    assert composed.halted_step.capability_id == CONFIRM_CAPABILITY_ID
    executors[CONFIRM_CAPABILITY_ID].assert_not_called()


def test_compose_workflow_reports_every_step_after_the_halt_point_as_remaining() -> None:
    """Steps after the halt point are collected in remaining_steps, in order, never attempted."""
    workflow = _workflow(
        _step(CONFIRM_CAPABILITY_ID), _step(ALLOW_CAPABILITY_ID), _step(ANOTHER_ALLOW_CAPABILITY_ID)
    )
    executors = {
        CONFIRM_CAPABILITY_ID: mock.Mock(),
        ALLOW_CAPABILITY_ID: mock.Mock(),
        ANOTHER_ALLOW_CAPABILITY_ID: mock.Mock(),
    }

    composed = compose_workflow(workflow, {}, _orchestrator(), executors)

    assert composed.runnable_steps == ()
    assert composed.halted_step is not None
    assert composed.halted_step.capability_id == CONFIRM_CAPABILITY_ID
    remaining_ids = [s.capability_id for s in composed.remaining_steps]
    assert remaining_ids == [ALLOW_CAPABILITY_ID, ANOTHER_ALLOW_CAPABILITY_ID]
    executors[ALLOW_CAPABILITY_ID].assert_not_called()


def test_compose_workflow_resolves_placeholders_in_runnable_steps() -> None:
    """A runnable step's own ${...} placeholders are resolved before becoming a real PlanStep."""
    workflow = _workflow(_step(ALLOW_CAPABILITY_ID, arguments={"query": "${company}"}))
    executors = {ALLOW_CAPABILITY_ID: mock.Mock()}

    composed = compose_workflow(workflow, {"company": "Acme"}, _orchestrator(), executors)

    assert composed.runnable_steps[0].arguments == {"query": "Acme"}


def test_compose_workflow_propagates_an_unresolved_placeholder_before_the_halt_point() -> None:
    """A real WorkflowCompositionError from a runnable step propagates, not silently skipped."""
    workflow = _workflow(_step(ALLOW_CAPABILITY_ID, arguments={"query": "${missing}"}))
    executors = {ALLOW_CAPABILITY_ID: mock.Mock()}

    with pytest.raises(WorkflowCompositionError):
        compose_workflow(workflow, {}, _orchestrator(), executors)
