"""WP-192: Stage A deterministic grammar for "run <workflow> workflow [with name=value, ...]".

Mirrors `test_router_kernel.py`'s own existing style for task/
communications Stage-A grammar tests exactly, kept in a separate file
purely so that already-huge file doesn't grow further (an established,
already-precedented split -- `test_workflows_*.py` already exists as
several separate files for the identical reason).
"""

from __future__ import annotations

from jarvis.application.routing.router import RouteKind
from jarvis.kernel.router import route_deterministically


def test_resolves_run_research_workflow() -> None:
    route = route_deterministically("run research workflow")

    assert route.kind == RouteKind.WORKFLOW_RUN
    assert route.workflow_id == "research"
    assert route.workflow_parameters == {}
    assert route.source == "deterministic"


def test_resolves_run_coding_workflow_via_alias() -> None:
    route = route_deterministically("run coding workflow")

    assert route.kind == RouteKind.WORKFLOW_RUN
    assert route.workflow_id == "coding_assistant"


def test_resolves_run_job_search_workflow_via_alias() -> None:
    route = route_deterministically("run job search workflow")

    assert route.kind == RouteKind.WORKFLOW_RUN
    assert route.workflow_id == "job_search_assistant"


def test_resolves_the_literal_registered_workflow_id_too() -> None:
    route = route_deterministically("run coding_assistant workflow")

    assert route.kind == RouteKind.WORKFLOW_RUN
    assert route.workflow_id == "coding_assistant"


def test_strips_a_leading_the_or_a_filler_before_the_alias() -> None:
    route = route_deterministically("run the research workflow")

    assert route.kind == RouteKind.WORKFLOW_RUN
    assert route.workflow_id == "research"


def test_strips_please_can_you_filler_before_run() -> None:
    """`_normalize_for_deterministic_routing`'s own, already-existing filler stripping applies."""
    route = route_deterministically("please run research workflow")

    assert route.kind == RouteKind.WORKFLOW_RUN
    assert route.workflow_id == "research"


def test_resolves_inline_with_parameters() -> None:
    route = route_deterministically(
        "run research workflow with query=rate limiting,url=https://example.com"
    )

    assert route.kind == RouteKind.WORKFLOW_RUN
    assert route.workflow_id == "research"
    assert route.workflow_parameters == {
        "query": "rate limiting",
        "url": "https://example.com",
    }


def test_an_unregistered_workflow_name_is_terminal_unknown_not_escalated() -> None:
    """Once "run ... workflow" itself matched, Stage A never escalates to reasoning."""
    route = route_deterministically("run bogus workflow")

    assert route.kind == RouteKind.UNKNOWN
    assert route.detail is not None
    assert "run <workflow> workflow" in route.detail


def test_a_malformed_inline_with_clause_is_terminal_unknown() -> None:
    route = route_deterministically("run research workflow with not-key-value")

    assert route.kind == RouteKind.UNKNOWN
    assert route.detail is not None


def test_a_trailing_clause_that_is_not_with_is_terminal_unknown() -> None:
    route = route_deterministically("run research workflow please")

    assert route.kind == RouteKind.UNKNOWN
    assert route.detail is not None


def test_run_without_a_trailing_workflow_word_falls_through_not_terminal() -> None:
    """ "run the tests" has nothing to do with a workflow -- must reach the generic UNKNOWN path."""
    route = route_deterministically("run the tests")

    assert route.kind == RouteKind.UNKNOWN
    assert route.detail == "No known deterministic command matched this request."


def test_does_not_collide_with_an_unrelated_existing_command() -> None:
    """ "read notes.txt" (an existing, unrelated command) is unaffected by the new grammar."""
    route = route_deterministically("read notes.txt")

    assert route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert route.workflow_id is None
