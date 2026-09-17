"""WP-193 (M10): the Stage-B reasoning fallback can discover and select registered workflows.

Mirrors `test_router_kernel.py`'s own existing "Stage B: reasoning
fallback" style exactly, kept in a separate file for the same,
already-established reason every other `test_router_*_workflow.py`
file is.
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


class _FakeReasoningProvider:
    """A minimal, test-local ReasoningPort, always returning a fixed routing response."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[str] = []

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        self.calls.append(task)
        candidate = Candidate(author="test-provider", content=self._content)
        return Tainted(candidate, Provenance.system())


def _workflow_run_response(workflow_id: str, parameters: dict[str, str]) -> str:
    return json.dumps(
        {
            "kind": "workflow_run",
            "capability_id": None,
            "arguments": {},
            "goal": None,
            "workflow_id": workflow_id,
            "parameters": parameters,
        }
    )


async def test_reasoning_selects_a_real_registered_workflow_and_runs_it(tmp_path: Path) -> None:
    """A genuinely unrecognized-by-Stage-A request can still resolve to a real workflow."""
    provider = _FakeReasoningProvider(
        _workflow_run_response("research", {"query": "rate limiting", "url": "https://example.com"})
    )

    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))

        outcome = await authorize_and_route(
            "please research the latest information about rate limiting and summarize it",
            provider,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert len(provider.calls) == 1
    assert outcome.route.kind == RouteKind.WORKFLOW_RUN
    assert outcome.route.source == "reasoning"
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert isinstance(outcome.execution_result, WorkflowRunOutcome)
    assert outcome.execution_result.composed.halted_step is not None
    assert outcome.execution_result.composed.halted_step.capability_id == CapabilityId(
        "browser.open_page"
    )


async def test_reasoning_prompt_genuinely_includes_relevant_workflow_context(
    tmp_path: Path,
) -> None:
    """WP-193: the real prompt Stage B sends includes compact, relevant workflow metadata."""
    provider = _FakeReasoningProvider(
        json.dumps({"kind": "unknown", "capability_id": None, "arguments": {}, "goal": None})
    )

    await authorize_and_route(
        "please research something clever, whatever that means",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "chain.json",
    )

    assert len(provider.calls) == 1
    assert "research" in provider.calls[0]


async def test_reasoning_cannot_invent_an_unregistered_workflow_id(tmp_path: Path) -> None:
    """A model naming a real-shaped but unregistered workflow id is rejected, never trusted."""
    provider = _FakeReasoningProvider(_workflow_run_response("not_a_real_workflow", {}))

    outcome = await authorize_and_route(
        "do a thing that sounds vaguely like a workflow",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "chain.json",
    )

    assert outcome.route.kind == RouteKind.UNKNOWN
    assert outcome.decision is None


async def test_a_malformed_workflow_run_response_is_handled_safely_not_a_crash(
    tmp_path: Path,
) -> None:
    """A workflow_run response missing its own required workflow_id never crashes authorize_and_route."""  # noqa: E501
    response = json.dumps(
        {"kind": "workflow_run", "capability_id": None, "arguments": {}, "goal": None}
    )
    provider = _FakeReasoningProvider(response)

    outcome = await authorize_and_route(
        "something that should have named a workflow but didn't",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "chain.json",
    )

    assert outcome.route.kind == RouteKind.UNKNOWN
    assert outcome.decision is None


async def test_denied_outer_gate_for_a_reasoning_sourced_workflow_route(tmp_path: Path) -> None:
    """The real, unmodified Tier.CONFIRM outer gate applies to a reasoning-sourced route too."""
    provider = _FakeReasoningProvider(_workflow_run_response("research", {"query": "x"}))

    outcome = await authorize_and_route(
        "please research something",
        provider,
        physical_confirmation_available=False,
        remote_confirmation_available=False,
        chain_path=tmp_path / "chain.json",
    )

    assert outcome.route.kind == RouteKind.WORKFLOW_RUN
    assert outcome.decision is not None
    assert outcome.decision.granted is False
    assert outcome.execution_result is None
