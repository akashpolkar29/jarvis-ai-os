"""Unit tests for jarvis.domain.workflow_registry."""

from __future__ import annotations

import pytest

from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, Effect
from jarvis.domain.errors import (
    WorkflowAlreadyRegistered,
    WorkflowNotRegistered,
    WorkflowReferencesUnknownCapability,
)
from jarvis.domain.registry import CapabilityRegistry
from jarvis.domain.workflow import WorkflowDescriptor, WorkflowId, WorkflowStep
from jarvis.domain.workflow_registry import WorkflowRegistry, validate_workflow_registry


def _capability_descriptor(
    capability_id: str, description: str = "A test capability."
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=CapabilityId(capability_id), effects=Effect.READ_LOCAL, description=description
    )


def _workflow_descriptor(
    workflow_id: str,
    *,
    capability_ids: tuple[str, ...] = ("fs.read_file",),
    name: str = "Test Workflow",
) -> WorkflowDescriptor:
    return WorkflowDescriptor(
        id=WorkflowId(workflow_id),
        name=name,
        description="A test workflow.",
        steps=tuple(
            WorkflowStep(capability_id=CapabilityId(c), arguments={}, description=f"Run {c}.")
            for c in capability_ids
        ),
    )


def test_register_then_get_returns_the_same_descriptor() -> None:
    """get() after register() returns the exact object that was registered."""
    registry = WorkflowRegistry()
    descriptor = _workflow_descriptor("research")

    registry.register(descriptor)

    assert registry.get(descriptor.id) is descriptor


def test_get_unregistered_id_raises() -> None:
    """Looking up an id that was never registered raises WorkflowNotRegistered."""
    registry = WorkflowRegistry()

    with pytest.raises(WorkflowNotRegistered):
        registry.get(WorkflowId("research"))


def test_duplicate_register_raises_and_leaves_original_intact() -> None:
    """A second register() with the same id is rejected, not merged or overwritten."""
    registry = WorkflowRegistry()
    original = _workflow_descriptor("research", name="Original")
    duplicate = _workflow_descriptor("research", name="Different")

    registry.register(original)

    with pytest.raises(WorkflowAlreadyRegistered):
        registry.register(duplicate)

    assert registry.get(original.id) is original


def test_distinct_workflows_do_not_interfere() -> None:
    """Multiple independently registered workflows are each retrievable on their own."""
    registry = WorkflowRegistry()
    research = _workflow_descriptor("research")
    job_search = _workflow_descriptor("job_search", capability_ids=("memory.retrieve",))

    registry.register(research)
    registry.register(job_search)

    assert registry.get(research.id) is research
    assert registry.get(job_search.id) is job_search


def test_contains_reflects_registration_state() -> None:
    """__contains__ is True only for ids that have actually been registered."""
    registry = WorkflowRegistry()
    descriptor = _workflow_descriptor("research")
    unregistered_id = WorkflowId("job_search")

    assert descriptor.id not in registry

    registry.register(descriptor)

    assert descriptor.id in registry
    assert unregistered_id not in registry


def test_len_reflects_number_of_registered_workflows() -> None:
    """len() counts distinct registered workflows."""
    registry = WorkflowRegistry()

    assert len(registry) == 0

    registry.register(_workflow_descriptor("research"))
    registry.register(_workflow_descriptor("job_search", capability_ids=("memory.retrieve",)))

    expected_count = 2
    assert len(registry) == expected_count


def test_iteration_yields_every_registered_descriptor_exactly_once() -> None:
    """Iterating the registry yields every registered descriptor, order not guaranteed."""
    registry = WorkflowRegistry()
    research = _workflow_descriptor("research")
    job_search = _workflow_descriptor("job_search", capability_ids=("memory.retrieve",))
    registry.register(research)
    registry.register(job_search)

    assert {d.id for d in registry} == {research.id, job_search.id}


def test_validate_workflow_registry_passes_when_every_capability_is_real() -> None:
    """validate_workflow_registry raises nothing when every step's capability is registered."""
    workflows = WorkflowRegistry()
    workflows.register(_workflow_descriptor("research", capability_ids=("fs.read_file",)))
    capabilities = CapabilityRegistry()
    capabilities.register(_capability_descriptor("fs.read_file"))

    validate_workflow_registry(workflows, capabilities)  # must not raise


def test_validate_workflow_registry_raises_on_unknown_capability() -> None:
    """Raises when a step names a capability that was never registered."""
    workflows = WorkflowRegistry()
    workflows.register(_workflow_descriptor("research", capability_ids=("fs.read_file",)))
    capabilities = CapabilityRegistry()  # deliberately empty

    with pytest.raises(WorkflowReferencesUnknownCapability, match="fs\\.read_file"):
        validate_workflow_registry(workflows, capabilities)


def test_validate_workflow_registry_checks_every_step_on_a_multi_step_workflow() -> None:
    """A workflow with several steps is only valid if every step's capability is real."""
    workflows = WorkflowRegistry()
    workflows.register(
        _workflow_descriptor("research", capability_ids=("fs.read_file", "fs.list_dir"))
    )
    capabilities = CapabilityRegistry()
    capabilities.register(_capability_descriptor("fs.read_file"))
    # fs.list_dir deliberately not registered

    with pytest.raises(WorkflowReferencesUnknownCapability, match="fs\\.list_dir"):
        validate_workflow_registry(workflows, capabilities)


def test_validate_workflow_registry_passes_on_empty_workflow_registry() -> None:
    """An empty workflow registry trivially validates against any capability registry."""
    validate_workflow_registry(WorkflowRegistry(), CapabilityRegistry())
