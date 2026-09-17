"""Unit tests for the real, built-in Job Search Assistant workflow (WP-185)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from jarvis.domain.capability import CapabilityId
from jarvis.kernel.workflows import (
    JOB_SEARCH_ASSISTANT_WORKFLOW_ID,
    authorize_and_run_workflow,
    build_default_workflow_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

_EXPECTED_STEP_COUNT = 2

_PARAMETERS = {
    "profile_query": "job search preferences",
    "site": "linkedin",
    "keywords": "python",
    "location": "remote",
}


def test_job_search_assistant_is_registered_with_two_real_steps() -> None:
    """The real, built-in registry contains this workflow, with its two documented steps."""
    workflow = build_default_workflow_registry().get(JOB_SEARCH_ASSISTANT_WORKFLOW_ID)

    assert len(workflow.steps) == _EXPECTED_STEP_COUNT
    assert workflow.steps[0].capability_id == CapabilityId("memory.retrieve")
    assert workflow.steps[1].capability_id == CapabilityId("job_search.open_results")


def test_denied_outer_gate_never_recalls_memory_or_opens_a_browser(tmp_path: Path) -> None:
    """planning.run_plan's own Tier.CONFIRM outer gate applies here too: no confirmation, no run."""
    decision, outcome = authorize_and_run_workflow(
        JOB_SEARCH_ASSISTANT_WORKFLOW_ID,
        _PARAMETERS,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "chain.json",
    )

    assert decision.granted is False
    assert outcome is None


def test_granted_run_recalls_memory_then_halts_before_opening_a_browser(tmp_path: Path) -> None:
    """memory.retrieve (ALLOW) runs for real; job_search.open_results (CONFIRM) halts, unrun."""
    with mock.patch("jarvis.kernel.job_search.BraveCliAdapter") as fake_brave:
        decision, outcome = authorize_and_run_workflow(
            JOB_SEARCH_ASSISTANT_WORKFLOW_ID,
            _PARAMETERS,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    fake_brave.assert_not_called()  # job_search.open_results's own real browser launch
    assert decision.granted is True
    assert outcome is not None
    assert len(outcome.composed.runnable_steps) == 1
    assert outcome.composed.runnable_steps[0].capability_id == CapabilityId("memory.retrieve")
    assert outcome.composed.halted_step is not None
    assert outcome.composed.halted_step.capability_id == CapabilityId("job_search.open_results")
    assert outcome.composed.remaining_steps == ()
    assert outcome.execution is not None
    assert outcome.execution.aborted is False
    assert len(outcome.execution.step_records) == 1
