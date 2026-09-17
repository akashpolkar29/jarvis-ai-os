"""WP-201: the canonical workflow-routing regression suite.

Three compact, deterministic, fully-mocked-external-edge scenarios,
one per real, built-in workflow, each exercising the full real chain:

    natural-language/typed request
    -> kernel.router.authorize_and_route (Stage A or Stage B)
    -> the real, registered workflow (kernel.workflows)
    -> the real, unmodified authorization path (planning.run_plan's
       own outer gate, then execute_plan's own per-step authorization)
    -> real execution of the Tier.ALLOW-eligible prefix
    -> a real, structured RouteOutcome/WorkflowRunOutcome result

Deliberately varies which router stage each scenario exercises
(Research via Stage B's reasoning fallback, Coding and Job Search via
Stage A's deterministic grammar) so this one file's own three tests
together cover both real routing paths reaching the identical
downstream execution, not just one repeated three times. No real
external service, credential, or network call anywhere -- every real
capability's own true I/O edge (`kernel.capability_dispatch`'s own
`authorize_and_*` functions) is mocked, matching this codebase's own
established "only the true external-I/O edge is faked" convention.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest import mock

from jarvis.application.routing.router import RouteKind
from jarvis.domain.capability import CapabilityId
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.router import authorize_and_route
from jarvis.kernel.workflows import WorkflowRunOutcome

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt

_EXPECTED_RESEARCH_RUNNABLE_STEPS = 2
_EXPECTED_CODING_RUNNABLE_STEPS = 4
_EXPECTED_JOB_SEARCH_RUNNABLE_STEPS = 1


class _FakeReasoningProvider:
    """A minimal, test-local ReasoningPort naming a real, registered workflow."""

    def __init__(self, workflow_id: str, parameters: dict[str, str]) -> None:
        self._workflow_id = workflow_id
        self._parameters = parameters

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        assert self._workflow_id in task  # real workflow context reached the real prompt
        content = json.dumps(
            {
                "kind": "workflow_run",
                "capability_id": None,
                "arguments": {},
                "goal": None,
                "workflow_id": self._workflow_id,
                "parameters": self._parameters,
            }
        )
        return Tainted(Candidate(author="fake", content=content), Provenance.system())


async def test_research_scenario_request_through_stage_b_reasoning_to_a_structured_result(
    tmp_path: Path,
) -> None:
    """Research: a natural-language request Stage A cannot resolve reaches the real workflow."""
    provider = _FakeReasoningProvider(
        "research", {"query": "rate limiting design patterns", "url": "https://example.com"}
    )

    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))

        outcome = await authorize_and_route(
            "please research rate limiting design patterns and summarize the findings",
            provider,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert outcome.route.kind == RouteKind.WORKFLOW_RUN
    assert outcome.route.source == "reasoning"
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert isinstance(outcome.execution_result, WorkflowRunOutcome)
    research_composed = outcome.execution_result.composed
    assert len(research_composed.runnable_steps) == _EXPECTED_RESEARCH_RUNNABLE_STEPS
    assert research_composed.halted_step is not None
    assert research_composed.halted_step.capability_id == CapabilityId("browser.open_page")
    fake_recall.assert_called_once()
    fake_search.assert_called_once()


async def test_coding_scenario_deterministic_request_through_execution_to_a_real_halt(
    tmp_path: Path,
) -> None:
    """Coding: a typed "run coding workflow with ..." request reaches real, granted execution."""
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

        outcome = await authorize_and_route(
            "run coding workflow with project_context_query=rate limiter,"
            "repo_dir=/tmp/example-repo,file_pattern=*.py,code_query=rate limiter,"
            "task=add a docstring",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert outcome.route.kind == RouteKind.WORKFLOW_RUN
    assert outcome.route.source == "deterministic"
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert isinstance(outcome.execution_result, WorkflowRunOutcome)
    coding_composed = outcome.execution_result.composed
    coding_execution = outcome.execution_result.execution
    assert len(coding_composed.runnable_steps) == _EXPECTED_CODING_RUNNABLE_STEPS
    assert coding_composed.halted_step is not None
    assert coding_composed.halted_step.capability_id == CapabilityId("coding.run_task")
    assert coding_execution is not None
    assert all(record.decision.granted for record in coding_execution.step_records)


async def test_job_search_scenario_deterministic_request_safely_halts_before_any_browser_action(
    tmp_path: Path,
) -> None:
    """Job search: a typed request recalls real context, then safely halts -- never searches."""
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall:
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))

        outcome = await authorize_and_route(
            "run job search workflow with profile_query=job search preferences,"
            "site=linkedin,keywords=python,location=remote",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert outcome.route.kind == RouteKind.WORKFLOW_RUN
    assert outcome.route.source == "deterministic"
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert isinstance(outcome.execution_result, WorkflowRunOutcome)
    assert (
        len(outcome.execution_result.composed.runnable_steps) == _EXPECTED_JOB_SEARCH_RUNNABLE_STEPS
    )
    assert outcome.execution_result.composed.halted_step is not None
    assert outcome.execution_result.composed.halted_step.capability_id == CapabilityId(
        "job_search.open_results"
    )
    fake_recall.assert_called_once()
