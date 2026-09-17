"""Unit tests for the real, built-in Coding Assistant workflow (WP-187, extended by WP-188).

All four real ``Tier.ALLOW`` steps are mocked at their real
``kernel.capability_dispatch`` dispatch point, exactly matching
``test_workflows_research.py``'s own established discipline -- this
avoids touching a real git repository, scanning the real
``Path.home()`` filesystem, or hitting the real, relative-path
``memory.sqlite3`` file during an ordinary test run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from jarvis.domain.capability import CapabilityId
from jarvis.kernel.workflows import (
    CODING_ASSISTANT_WORKFLOW_ID,
    authorize_and_run_workflow,
    build_default_workflow_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

_EXPECTED_STEP_COUNT = 5
_EXPECTED_RUNNABLE_COUNT = 4

_PARAMETERS = {
    "project_context_query": "rate limiter design decisions",
    "repo_dir": "/tmp/example-repo",
    "file_pattern": "*.py",
    "code_query": "rate limiter",
    "task": "add a docstring to the rate limiter",
}


def test_coding_assistant_is_registered_with_five_real_steps() -> None:
    """The real, built-in registry contains this workflow, with its five documented steps."""
    workflow = build_default_workflow_registry().get(CODING_ASSISTANT_WORKFLOW_ID)

    assert len(workflow.steps) == _EXPECTED_STEP_COUNT
    assert workflow.steps[0].capability_id == CapabilityId("memory.retrieve")
    assert workflow.steps[1].capability_id == CapabilityId("git.status")
    assert workflow.steps[2].capability_id == CapabilityId("fs.find")
    assert workflow.steps[3].capability_id == CapabilityId("fs.search_content")
    assert workflow.steps[4].capability_id == CapabilityId("coding.run_task")


def test_denied_outer_gate_never_recalls_inspects_searches_or_runs_the_coding_agent(
    tmp_path: Path,
) -> None:
    """planning.run_plan's own Tier.CONFIRM outer gate applies here too: no confirmation, no run."""
    decision, outcome = authorize_and_run_workflow(
        CODING_ASSISTANT_WORKFLOW_ID,
        _PARAMETERS,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "chain.json",
    )

    assert decision.granted is False
    assert outcome is None


def test_granted_run_recalls_inspects_and_searches_then_halts_before_the_coding_agent(
    tmp_path: Path,
) -> None:
    """All four ALLOW steps run for real; coding.run_task (CONFIRM) halts, never auto-invoked."""
    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_get_git_status") as fake_status,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_find_files") as fake_find,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_status.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_find.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))

        decision, outcome = authorize_and_run_workflow(
            CODING_ASSISTANT_WORKFLOW_ID,
            _PARAMETERS,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    fake_recall.assert_called_once()
    fake_status.assert_called_once()
    fake_find.assert_called_once()
    fake_search.assert_called_once()
    assert decision.granted is True
    assert outcome is not None
    assert len(outcome.composed.runnable_steps) == _EXPECTED_RUNNABLE_COUNT
    assert outcome.composed.halted_step is not None
    assert outcome.composed.halted_step.capability_id == CapabilityId("coding.run_task")
    assert outcome.composed.remaining_steps == ()
    assert outcome.execution is not None
    assert outcome.execution.aborted is False
    assert len(outcome.execution.step_records) == _EXPECTED_RUNNABLE_COUNT


def test_memory_recall_step_receives_the_real_project_context_query(tmp_path: Path) -> None:
    """The recall step's own query argument is the caller-supplied project_context_query."""
    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_get_git_status") as fake_status,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_find_files") as fake_find,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_status.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_find.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))

        authorize_and_run_workflow(
            CODING_ASSISTANT_WORKFLOW_ID,
            _PARAMETERS,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    called_query = fake_recall.call_args.args[0]
    assert called_query == _PARAMETERS["project_context_query"]
