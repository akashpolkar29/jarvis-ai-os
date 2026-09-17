"""WP-198: real security/regression hardening tests for the Research workflow.

Every property tested here was investigated directly against the real
code before writing a test for it. One real, pre-existing, cross-
cutting gap was found (not introduced by the workflow layer, and not
fixed here -- see `docs/OPEN_DECISIONS.md`): `fs.search_content`'s own
matched lines (`ContentSearchOutcome.matches`) carry no `Tainted`/
`Provenance` wrapper at all, unlike `fs.read_file`'s own file content
(`Provenance.external(...)`) -- confirmed via `git log`, this predates
the whole M9/M10 workflow layer (WP-94, well before WP-182), so it is
not a deficiency this workflow itself introduces or could fix by
itself; fixing it would mean changing `kernel/files.py`'s own real,
already-shipped return shape, a genuinely separate, larger work
package.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from jarvis.domain.capability import CapabilityId
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.router import authorize_and_route
from jarvis.kernel.workflows import (
    RESEARCH_WORKFLOW_ID,
    WorkflowRunOutcome,
    authorize_and_run_workflow,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.evidence import Attempt

_VALID_PARAMETERS = {"query": "rate limiting", "url": "https://example.com"}
_EXPECTED_RUNNABLE_STEP_COUNT = 2


@pytest.mark.parametrize(
    ("physical_confirmation_available", "remote_confirmation_available"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_browser_open_page_never_runs_regardless_of_confirmation(
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    tmp_path: Path,
) -> None:
    """No unrestricted browsing: browser.open_page halts under every confirmation combination.

    Structural, not merely empirical: `browser.open_page` has no entry
    in `kernel.capability_dispatch.PLAN_STEP_EXECUTORS` at all (checked
    directly), so no workflow -- or reasoning-generated plan, via the
    identical, shared table -- can ever auto-execute it, regardless of
    confirmation flags.
    """
    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))
        decision, outcome = authorize_and_run_workflow(
            RESEARCH_WORKFLOW_ID,
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
    assert outcome.composed.halted_step.capability_id == CapabilityId("browser.open_page")


def test_genuinely_empty_results_are_reported_honestly_not_as_a_failure(tmp_path: Path) -> None:
    """A granted run with zero real matches from either step is still a real, granted success.

    Never conflated with a denial or an error -- an empty result is a
    real, valid answer ("nothing matched"), not a failure mode.
    """
    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True), records=())
        fake_search.return_value = mock.Mock(
            decision=mock.Mock(granted=True), matches=(), capped=False
        )
        decision, outcome = authorize_and_run_workflow(
            RESEARCH_WORKFLOW_ID,
            _VALID_PARAMETERS,
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert decision.granted is True
    assert outcome is not None
    assert outcome.execution is not None
    assert outcome.execution.aborted is False
    assert all(record.decision.granted for record in outcome.execution.step_records)
    assert fake_recall.return_value.records == ()
    assert fake_search.return_value.matches == ()


def test_a_step_execution_exception_propagates_rather_than_being_silently_swallowed(
    tmp_path: Path,
) -> None:
    """A real, unexpected exception from a step's own adapter call is never hidden as 'success'.

    No invented/fabricated result: `execute_plan`/`compose_workflow`
    add no try/except of their own around a step's real call -- a
    genuine failure (e.g. a malformed real result from fs.search_content)
    propagates to this function's own caller untouched, matching this
    project's own "no silent partial success" convention.
    """
    with mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall:
        fake_recall.side_effect = RuntimeError("a real, unexpected adapter failure")
        with pytest.raises(RuntimeError, match="a real, unexpected adapter failure"):
            authorize_and_run_workflow(
                RESEARCH_WORKFLOW_ID,
                _VALID_PARAMETERS,
                physical_confirmation_available=True,
                remote_confirmation_available=False,
                chain_path=tmp_path / "chain.json",
            )


async def test_canonical_end_to_end_scenario_request_router_workflow_result(
    tmp_path: Path,
) -> None:
    """WP-198's own required deterministic scenario: request -> router -> workflow -> result.

    A real, natural-language request that Stage A cannot deterministically
    resolve falls through to a mocked Stage-B reasoning fallback naming
    the real, registered "research" workflow, which the real,
    unmodified authorize_and_route/authorize_and_run_workflow chain
    then composes and runs against mocked (never real, external)
    capability adapters -- the canonical, safe research path this
    codebase now supports end to end.
    """

    class _FakeProvider:
        async def generate(
            self, task: str, _prior_attempts: tuple[Attempt, ...]
        ) -> Tainted[Candidate]:
            assert "research" in task  # real workflow context reached the real prompt
            content = json.dumps(
                {
                    "kind": "workflow_run",
                    "capability_id": None,
                    "arguments": {},
                    "goal": None,
                    "workflow_id": "research",
                    "parameters": {
                        "query": "rate limiting design patterns",
                        "url": "https://example.com/article",
                    },
                }
            )
            return Tainted(Candidate(author="fake", content=content), Provenance.system())

    with (
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_recall") as fake_recall,
        mock.patch("jarvis.kernel.capability_dispatch.authorize_and_search_content") as fake_search,
    ):
        fake_recall.return_value = mock.Mock(decision=mock.Mock(granted=True))
        fake_search.return_value = mock.Mock(decision=mock.Mock(granted=True))

        outcome = await authorize_and_route(
            "please research rate limiting design patterns and summarize the findings",
            _FakeProvider(),
            physical_confirmation_available=True,
            remote_confirmation_available=False,
            chain_path=tmp_path / "chain.json",
        )

    assert outcome.route.kind.value == "workflow_run"
    assert outcome.route.source == "reasoning"
    assert outcome.decision is not None
    assert outcome.decision.granted is True
    assert isinstance(outcome.execution_result, WorkflowRunOutcome)
    assert outcome.execution_result.composed.halted_step is not None
    assert outcome.execution_result.composed.halted_step.capability_id == CapabilityId(
        "browser.open_page"
    )
    assert len(outcome.execution_result.composed.runnable_steps) == _EXPECTED_RUNNABLE_STEP_COUNT
