"""Unit tests for the real, built-in Research workflow (WP-186).

Both real ``Tier.ALLOW`` steps (``memory.retrieve``/``fs.search_content``)
are mocked at their real ``kernel.capability_dispatch`` dispatch point,
exactly matching ``test_workflows_job_search.py``'s own established
discipline -- this avoids touching this repository's own real,
relative-path ``memory.sqlite3`` file or scanning the real
``Path.home()`` filesystem during an ordinary test run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from jarvis.domain.capability import CapabilityId
from jarvis.kernel.workflows import (
    RESEARCH_WORKFLOW_ID,
    authorize_and_run_workflow,
    build_default_workflow_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

_EXPECTED_STEP_COUNT = 3
_EXPECTED_RUNNABLE_COUNT = 2

_PARAMETERS = {"query": "rate limiting design notes", "url": "https://example.com/article"}


def test_research_is_registered_with_three_real_steps() -> None:
    """The real, built-in registry contains this workflow, with its three documented steps."""
    workflow = build_default_workflow_registry().get(RESEARCH_WORKFLOW_ID)

    assert len(workflow.steps) == _EXPECTED_STEP_COUNT
    assert workflow.steps[0].capability_id == CapabilityId("memory.retrieve")
    assert workflow.steps[1].capability_id == CapabilityId("fs.search_content")
    assert workflow.steps[2].capability_id == CapabilityId("browser.open_page")


def test_denied_outer_gate_never_recalls_or_searches_or_opens_a_page(tmp_path: Path) -> None:
    """planning.run_plan's own Tier.CONFIRM outer gate applies here too: no confirmation, no run."""
    decision, outcome = authorize_and_run_workflow(
        RESEARCH_WORKFLOW_ID,
        _PARAMETERS,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "chain.json",
    )

    assert decision.granted is False
    assert outcome is None


def test_granted_run_recalls_and_searches_then_halts_before_opening_a_page(tmp_path: Path) -> None:
    """The two ALLOW steps run for real; browser.open_page (CONFIRM) halts, never runs."""
    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))

        decision, outcome = authorize_and_run_workflow(
            RESEARCH_WORKFLOW_ID,
            _PARAMETERS,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    fake_recall.assert_called_once()
    fake_search.assert_called_once()
    assert decision.granted is True
    assert outcome is not None
    assert len(outcome.composed.runnable_steps) == _EXPECTED_RUNNABLE_COUNT
    assert outcome.composed.halted_step is not None
    assert outcome.composed.halted_step.capability_id == CapabilityId("browser.open_page")
    assert outcome.composed.remaining_steps == ()
    assert outcome.execution is not None
    assert outcome.execution.aborted is False
    assert len(outcome.execution.step_records) == _EXPECTED_RUNNABLE_COUNT
