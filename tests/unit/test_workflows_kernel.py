"""Unit tests for jarvis.kernel.workflows's authorize_and_run_workflow composition root.

WP-184's own real, built-in workflow registry is deliberately empty
(concrete workflows are added by WP-185/186/187) -- every test here
injects its own small, synthetic ``WorkflowRegistry`` by monkeypatching
``build_default_workflow_registry``, exactly matching how
``test_planning_kernel.py`` fakes only the true external-I/O edge
(there, the reasoning provider; here, which built-in workflows exist)
and runs everything else -- authorization, composition, execution --
for real.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.application.workflow.composer import WorkflowCompositionError
from jarvis.domain.capability import CapabilityId
from jarvis.domain.errors import WorkflowNotRegistered
from jarvis.domain.workflow import WorkflowDescriptor, WorkflowId, WorkflowStep
from jarvis.domain.workflow_registry import WorkflowRegistry
from jarvis.kernel.workflows import authorize_and_run_workflow

_READ_NOTES_WORKFLOW_ID = WorkflowId("read_notes")


def _read_notes_registry() -> WorkflowRegistry:
    registry = WorkflowRegistry()
    registry.register(
        WorkflowDescriptor(
            id=_READ_NOTES_WORKFLOW_ID,
            name="Read Notes",
            description="Read a known local file.",
            steps=(
                WorkflowStep(
                    capability_id=CapabilityId("fs.read_file"),
                    arguments={"path": "${path}"},
                    description="Read the file at the given path.",
                ),
            ),
            parameters=("path",),
        )
    )
    return registry


def _patched(registry: WorkflowRegistry) -> mock._patch[mock.MagicMock]:
    return mock.patch(
        "jarvis.kernel.workflows.build_default_workflow_registry", return_value=registry
    )


def test_unregistered_workflow_id_raises(tmp_path: Path) -> None:
    """A workflow id naming no real, registered workflow is a loud, specific failure."""
    with _patched(_read_notes_registry()), pytest.raises(WorkflowNotRegistered):
        authorize_and_run_workflow(
            WorkflowId("does_not_exist"),
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )


def test_denied_outer_gate_never_composes_or_executes(tmp_path: Path) -> None:
    """The outer gate reuses planning.run_plan (Tier.CONFIRM) -- no confirmation means denied."""
    with _patched(_read_notes_registry()):
        decision, outcome = authorize_and_run_workflow(
            _READ_NOTES_WORKFLOW_ID,
            {"path": str(tmp_path / "notes.txt")},
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert decision.granted is False
    assert outcome is None


def test_granted_outer_gate_composes_and_runs_a_real_allow_tier_workflow(tmp_path: Path) -> None:
    """A granted outer gate runs the workflow's real steps through the unmodified execute_plan."""
    (tmp_path / "notes.txt").write_text("hello")

    with (
        _patched(_read_notes_registry()),
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_read_file") as fake,
    ):
        fake.return_value = mock.Mock(decision=mock.Mock(granted=True))
        decision, outcome = authorize_and_run_workflow(
            _READ_NOTES_WORKFLOW_ID,
            {"path": str(tmp_path / "notes.txt")},
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    fake.assert_called_once()
    assert decision.granted is True
    assert outcome is not None
    assert outcome.composed.halted_step is None
    assert outcome.execution is not None
    assert outcome.execution.aborted is False
    assert len(outcome.execution.step_records) == 1
    assert outcome.execution.step_records[0].decision.granted is True


def test_a_confirm_tier_step_halts_rather_than_silently_executing(tmp_path: Path) -> None:
    """A workflow naming a step with no plan-step executor (e.g. a real CONFIRM-tier one) halts."""
    registry = WorkflowRegistry()
    registry.register(
        WorkflowDescriptor(
            id=WorkflowId("open_results"),
            name="Open Results",
            description="Open a real search-results page -- requires manual confirmation.",
            steps=(
                WorkflowStep(
                    capability_id=CapabilityId("job_search.open_results"),
                    arguments={},
                    description="Open a real job-search results page in the user's browser.",
                ),
            ),
        )
    )

    with _patched(registry):
        decision, outcome = authorize_and_run_workflow(
            WorkflowId("open_results"),
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert decision.granted is True
    assert outcome is not None
    assert outcome.composed.runnable_steps == ()
    assert outcome.composed.halted_step is not None
    assert outcome.composed.halted_step.capability_id == CapabilityId("job_search.open_results")
    assert outcome.execution is not None
    assert outcome.execution.step_records == ()


def test_every_granted_decision_is_durably_appended_to_the_audit_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The outer gate's decision plus every runnable step's own decision land in one chain file.

    Runs the real fs.read_file capability, unmocked -- ``Path.home()``
    (fs.read_file's own default ``allowed_root``) is monkeypatched to
    ``tmp_path`` rather than mocking the composition function itself,
    so this step's own real, internal authorize-then-save happens for
    real, exactly like every other real plan step already does.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "notes.txt").write_text("hello")
    chain_path = tmp_path / "chain.json"

    with _patched(_read_notes_registry()):
        authorize_and_run_workflow(
            _READ_NOTES_WORKFLOW_ID,
            {"path": str(tmp_path / "notes.txt")},
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    expected_record_count = 2  # outer gate + the one real fs.read_file step
    assert len(chain) == expected_record_count
    assert chain.verify().valid is True


def test_the_outer_decision_stays_durable_even_when_composition_later_raises(
    tmp_path: Path,
) -> None:
    """WP-202: failure is durable -- a granted outer gate is saved before compose_workflow runs.

    A real `WorkflowCompositionError` (an unrecognized parameter key,
    WP-194) raised *after* the outer gate was granted must not lose or
    silently roll back that already-real, already-granted decision --
    proven directly by reading the real, on-disk chain after the
    exception propagates.
    """
    chain_path = tmp_path / "chain.json"

    with (
        _patched(_read_notes_registry()),
        pytest.raises(WorkflowCompositionError),
    ):
        authorize_and_run_workflow(
            _READ_NOTES_WORKFLOW_ID,
            {"not_a_real_parameter": "x"},
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=chain_path,
        )

    chain = JsonFileAuditStorageAdapter(chain_path).load()
    assert len(chain) == 1  # the outer gate's own real decision, durably saved
    assert chain.verify().valid is True
    assert chain[0].decision.granted is True
