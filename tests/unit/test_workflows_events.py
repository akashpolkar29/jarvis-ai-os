"""Unit tests for WP-189's real workflow-lifecycle events.

Uses the same synthetic ``WorkflowRegistry`` injection pattern
``test_workflows_kernel.py`` already established, since WP-184's own
empty-by-default registry means every built-in workflow needs real,
external capabilities (memory/browser/job-search) mocked to run --
these tests care only about which events are published, not about any
one real, built-in workflow's own content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from jarvis.domain.capability import CapabilityId
from jarvis.domain.events import (
    EventBus,
    WorkflowCompleted,
    WorkflowHalted,
    WorkflowRunDenied,
    WorkflowStarted,
    WorkflowStepCompleted,
)
from jarvis.domain.workflow import WorkflowDescriptor, WorkflowId, WorkflowStep
from jarvis.domain.workflow_registry import WorkflowRegistry
from jarvis.kernel.workflows import authorize_and_run_workflow

if TYPE_CHECKING:
    from pathlib import Path

_ALLOW_ONLY_WORKFLOW_ID = WorkflowId("allow_only")
_HALTING_WORKFLOW_ID = WorkflowId("halts_partway")


def _allow_only_registry() -> WorkflowRegistry:
    registry = WorkflowRegistry()
    registry.register(
        WorkflowDescriptor(
            id=_ALLOW_ONLY_WORKFLOW_ID,
            name="Allow Only",
            description="Every step is Tier.ALLOW and wired.",
            steps=(
                WorkflowStep(
                    capability_id=CapabilityId("fs.read_file"),
                    arguments={"path": "${path}"},
                    description="Read a known file.",
                ),
            ),
        )
    )
    return registry


def _halting_registry() -> WorkflowRegistry:
    registry = WorkflowRegistry()
    registry.register(
        WorkflowDescriptor(
            id=_HALTING_WORKFLOW_ID,
            name="Halts Partway",
            description="One ALLOW step, then a CONFIRM step that halts.",
            steps=(
                WorkflowStep(
                    capability_id=CapabilityId("fs.read_file"),
                    arguments={"path": "${path}"},
                    description="Read a known file.",
                ),
                WorkflowStep(
                    capability_id=CapabilityId("job_search.open_results"),
                    arguments={},
                    description="Requires manual confirmation -- halts here.",
                ),
            ),
        )
    )
    return registry


def _patched(registry: WorkflowRegistry) -> mock._patch[mock.MagicMock]:
    return mock.patch(
        "jarvis.kernel.workflows.build_default_workflow_registry", return_value=registry
    )


def _recording_bus() -> tuple[EventBus, list[object]]:
    bus = EventBus()
    received: list[object] = []
    for event_type in (
        WorkflowRunDenied,
        WorkflowStarted,
        WorkflowStepCompleted,
        WorkflowHalted,
        WorkflowCompleted,
    ):
        bus.subscribe(event_type, received.append)
    return bus, received


def test_denied_outer_gate_publishes_only_workflow_run_denied(tmp_path: Path) -> None:
    """A denied outer gate publishes exactly one WorkflowRunDenied, nothing else."""
    bus, received = _recording_bus()

    with _patched(_allow_only_registry()):
        authorize_and_run_workflow(
            _ALLOW_ONLY_WORKFLOW_ID,
            {"path": str(tmp_path / "notes.txt")},
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
            event_bus=bus,
        )

    assert [type(e) for e in received] == [WorkflowRunDenied]
    assert received[0].workflow_id == str(_ALLOW_ONLY_WORKFLOW_ID)  # type: ignore[attr-defined]


def test_a_fully_completed_workflow_publishes_started_step_completed_then_completed(
    tmp_path: Path,
) -> None:
    """A granted, fully-runnable workflow publishes Started, StepCompleted per step, Completed."""
    bus, received = _recording_bus()

    with (
        _patched(_allow_only_registry()),
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_read_file") as fake,
    ):
        fake.return_value = mock.Mock(decision=mock.Mock(granted=True))
        authorize_and_run_workflow(
            _ALLOW_ONLY_WORKFLOW_ID,
            {"path": str(tmp_path / "notes.txt")},
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
            event_bus=bus,
        )

    assert [type(e) for e in received] == [
        WorkflowStarted,
        WorkflowStepCompleted,
        WorkflowCompleted,
    ]
    step_event = received[1]
    assert step_event.capability_id == "fs.read_file"  # type: ignore[attr-defined]


def test_a_halting_workflow_publishes_started_step_completed_then_halted_not_completed(
    tmp_path: Path,
) -> None:
    """A workflow that halts publishes Started, StepCompleted for the ran prefix, then Halted."""
    bus, received = _recording_bus()

    with (
        _patched(_halting_registry()),
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_read_file") as fake,
    ):
        fake.return_value = mock.Mock(decision=mock.Mock(granted=True))
        authorize_and_run_workflow(
            _HALTING_WORKFLOW_ID,
            {"path": str(tmp_path / "notes.txt")},
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
            event_bus=bus,
        )

    assert [type(e) for e in received] == [
        WorkflowStarted,
        WorkflowStepCompleted,
        WorkflowHalted,
    ]
    halted_event = received[2]
    assert halted_event.capability_id == "job_search.open_results"  # type: ignore[attr-defined]


def test_no_event_bus_supplied_does_not_raise(tmp_path: Path) -> None:
    """The default, throwaway EventBus() means omitting event_bus behaves exactly as before."""
    with _patched(_allow_only_registry()):
        decision, outcome = authorize_and_run_workflow(
            _ALLOW_ONLY_WORKFLOW_ID,
            {"path": str(tmp_path / "notes.txt")},
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert decision.granted is False
    assert outcome is None
