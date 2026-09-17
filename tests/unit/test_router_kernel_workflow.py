"""WP-191/192 (M10): RouteKind.WORKFLOW_RUN safely reaches authorize_and_run_workflow.

The first two tests below (WP-191) monkeypatch
`jarvis.kernel.router._route_deterministically` to hand back an
already-constructed `WORKFLOW_RUN` route -- at WP-191's own point in
the queue, no real grammar could produce one yet, so this proved the
downstream dispatch wiring was sound in isolation first ("prove the
plumbing, then make it reachable", the same sequencing
`test_workflows_kernel.py` already used for the workflow layer
itself). WP-192 then built the real Stage-A grammar
(`tests/unit/test_router_deterministic_workflow.py` covers that
grammar itself in isolation) -- the final test in this file exercises
the whole thing with real, typed text and no monkeypatched routing at
all, proving the two halves genuinely compose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from jarvis.application.routing.router import RouteKind, RouteResult
from jarvis.domain.capability import CapabilityId
from jarvis.kernel.router import authorize_and_route
from jarvis.kernel.workflows import RESEARCH_WORKFLOW_ID, WorkflowRunOutcome

if TYPE_CHECKING:
    from pathlib import Path

_RESEARCH_PARAMETERS = {"query": "rate limiting", "url": "https://example.com"}


def _fake_workflow_route(workflow_id: str, parameters: dict[str, str]) -> RouteResult:
    return RouteResult(
        kind=RouteKind.WORKFLOW_RUN,
        original_input=f"run {workflow_id} workflow",
        confidence=1.0,
        source="deterministic",
        workflow_id=workflow_id,
        workflow_parameters=parameters,
    )


async def test_denied_outer_gate_never_composes_or_executes_the_workflow(tmp_path: Path) -> None:
    """planning.run_plan's own Tier.CONFIRM outer gate applies via this route too."""
    route = _fake_workflow_route(str(RESEARCH_WORKFLOW_ID), _RESEARCH_PARAMETERS)
    with mock.patch("jarvis.kernel.router._route_deterministically", return_value=(route, False)):
        outcome = await authorize_and_route(
            "run research workflow",
            physical_confirmation_available=False,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert outcome.route.kind == RouteKind.WORKFLOW_RUN
    assert outcome.decision is not None
    assert outcome.decision.granted is False
    assert outcome.execution_result is None
    assert outcome.task_id is None


async def test_granted_outer_gate_runs_the_real_research_workflow_through_authorize_and_route(
    tmp_path: Path,
) -> None:
    """A granted route reaches the real, unmodified authorize_and_run_workflow end to end."""
    route = _fake_workflow_route(str(RESEARCH_WORKFLOW_ID), _RESEARCH_PARAMETERS)
    with (
        mock.patch("jarvis.kernel.router._route_deterministically", return_value=(route, False)),
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))

        outcome = await authorize_and_route(
            "run research workflow",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    fake_recall.assert_called_once()
    fake_search.assert_called_once()
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert isinstance(outcome.execution_result, WorkflowRunOutcome)
    assert outcome.execution_result.composed.halted_step is not None
    assert outcome.execution_result.composed.halted_step.capability_id == CapabilityId(
        "browser.open_page"
    )
    assert outcome.task_id is None


async def test_real_typed_text_reaches_the_real_workflow_with_no_routing_mocked(
    tmp_path: Path,
) -> None:
    """WP-192: "jarvis do "run research workflow with ..."" works end to end, genuinely."""
    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))

        outcome = await authorize_and_route(
            "run research workflow with query=rate limiting,url=https://example.com",
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert outcome.route.kind == RouteKind.WORKFLOW_RUN
    assert outcome.route.source == "deterministic"
    fake_recall.assert_called_once()
    fake_search.assert_called_once()
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert isinstance(outcome.execution_result, WorkflowRunOutcome)
    assert outcome.execution_result.composed.halted_step is not None
    assert outcome.execution_result.composed.halted_step.capability_id == CapabilityId(
        "browser.open_page"
    )
