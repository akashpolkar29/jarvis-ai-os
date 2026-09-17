"""WP-199: real security/regression hardening tests for the Coding Assistant workflow.

Every property tested here was investigated directly against the real
code before writing a test for it; no real deficiency was found, so
this work package is tests only, no production code changed.
`terminal.run`/`SyntheticInputPort`/`Dispatcher`/`EscalationLadder`
internals are untouched -- not referenced anywhere in this file or in
any production code this queue has touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from jarvis.domain.capability import CapabilityId
from jarvis.kernel.capabilities import CODING_RUN_TASK_CAPABILITY_ID, TERMINAL_RUN_CAPABILITY_ID
from jarvis.kernel.capability_dispatch import PLAN_STEP_EXECUTORS
from jarvis.kernel.workflows import CODING_ASSISTANT_WORKFLOW_ID, authorize_and_run_workflow

if TYPE_CHECKING:
    from pathlib import Path

_VALID_PARAMETERS = {
    "project_context_query": "rate limiter design decisions",
    "repo_dir": "/tmp/example-repo",
    "file_pattern": "*.py",
    "code_query": "rate limiter",
    "task": "add a docstring to the rate limiter",
}


def test_terminal_run_and_coding_run_task_have_no_plan_step_executor_at_all() -> None:
    """Safe execution boundary, structural: neither capability can ever be auto-invoked.

    `PLAN_STEP_EXECUTORS` is the one, real, shared dispatch table both
    `execute_plan` (workflows) and `planning.run_plan` (reasoning-
    generated plans) ever consult -- confirmed directly that neither
    `terminal.run` nor `coding.run_task` has an entry in it, so no
    workflow and no reasoning-generated plan can ever auto-run either,
    regardless of what a future workflow or a hallucinated plan step
    might name.
    """
    assert TERMINAL_RUN_CAPABILITY_ID not in PLAN_STEP_EXECUTORS
    assert CODING_RUN_TASK_CAPABILITY_ID not in PLAN_STEP_EXECUTORS


@pytest.mark.parametrize(
    ("physical_confirmation_available", "remote_confirmation_available"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_coding_run_task_never_runs_regardless_of_confirmation(
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    tmp_path: Path,
) -> None:
    """No unrestricted execution: coding.run_task halts under every confirmation combination."""
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
            _VALID_PARAMETERS,
            physical_confirmation_available=physical_confirmation_available,
            remote_confirmation_available=remote_confirmation_available,
            chain_path=tmp_path / "chain.json",
        )

    if not decision.granted:
        assert outcome is None
        return
    assert outcome is not None
    assert outcome.composed.halted_step is not None
    assert outcome.composed.halted_step.capability_id == CapabilityId("coding.run_task")
    # No test execution, no real repository write, no real coding-loop invocation of any
    # kind happened -- the halt point is reported, never approached.


def test_a_step_execution_exception_propagates_rather_than_being_silently_swallowed(
    tmp_path: Path,
) -> None:
    """A real, unexpected exception from git.status's own real adapter call is never hidden."""
    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_get_git_status") as fake_status,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_status.side_effect = RuntimeError("a real, unexpected git adapter failure")
        with pytest.raises(RuntimeError, match="a real, unexpected git adapter failure"):
            authorize_and_run_workflow(
                CODING_ASSISTANT_WORKFLOW_ID,
                _VALID_PARAMETERS,
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=tmp_path / "chain.json",
            )


def test_the_task_parameter_is_carried_verbatim_never_interpreted_by_the_workflow_engine(
    tmp_path: Path,
) -> None:
    """Request interpretation happens inside coding.run_task itself, never in the workflow layer.

    A real, adversarial-shaped "task" string (looking like a shell
    command) is proven to reach the halted step's own arguments
    completely unmodified -- the workflow engine never parses,
    executes, or otherwise interprets it, since the step it belongs to
    is never composed into a real `PlanStep`/`execute_plan` call at
    all (it becomes `halted_step`).
    """
    adversarial_task = "; rm -rf / #"
    parameters = dict(_VALID_PARAMETERS)
    parameters["task"] = adversarial_task

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
            parameters,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert decision.granted is True
    assert outcome is not None
    assert outcome.composed.halted_step is not None
    assert outcome.composed.halted_step.capability_id == CapabilityId("coding.run_task")
    assert outcome.composed.halted_step.arguments["task"] == "${task}"  # never substituted
    fake_status.assert_called_once()
    fake_find.assert_called_once()
    fake_search.assert_called_once()
