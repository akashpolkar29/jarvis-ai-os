"""Unit tests for jarvis.application.routing.router's Stage-B reasoning-fallback logic."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from jarvis.application.routing.router import RouteKind, RoutingError, generate_route
from jarvis.domain.capability import CapabilityId
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt


class _FakeReasoningProvider:
    """A minimal, test-local ReasoningPort, always returning a fixed Candidate."""

    def __init__(self, content: str) -> None:
        self._content = content

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        del task
        candidate = Candidate(author="test-provider", content=self._content)
        return Tainted(candidate, Provenance.system())


def _always_registered(_capability_id: CapabilityId) -> bool:
    return True


def _never_registered(_capability_id: CapabilityId) -> bool:
    return False


async def test_generate_route_returns_a_deterministic_command_route() -> None:
    """A well-formed deterministic_command response becomes a real RouteResult."""
    response = json.dumps(
        {
            "kind": "deterministic_command",
            "capability_id": "fs.read_file",
            "arguments": {"path": "/tmp/a.txt"},
            "goal": None,
        }
    )
    provider = _FakeReasoningProvider(response)
    text = Tainted("read the file at /tmp/a.txt please", Provenance.user())

    route = await generate_route(text, provider, _always_registered)

    assert route.kind == RouteKind.DETERMINISTIC_COMMAND
    assert route.capability_id == CapabilityId("fs.read_file")
    assert route.arguments is not None
    assert route.arguments.value == {"path": "/tmp/a.txt"}
    assert route.source == "reasoning"
    assert route.goal is None


async def test_generate_route_returns_a_complex_goal_route() -> None:
    """A well-formed complex_goal response becomes a real RouteResult with a goal, no capability."""
    response = json.dumps(
        {"kind": "complex_goal", "capability_id": None, "arguments": {}, "goal": "find internships"}
    )
    provider = _FakeReasoningProvider(response)
    text = Tainted("find me good internships", Provenance.user())

    route = await generate_route(text, provider, _always_registered)

    assert route.kind == RouteKind.COMPLEX_GOAL
    assert route.goal == "find internships"
    assert route.capability_id is None
    assert route.arguments is None


async def test_generate_route_returns_unknown_route() -> None:
    """A well-formed unknown response is a real, valid RouteResult, not an error."""
    response = json.dumps({"kind": "unknown", "capability_id": None, "arguments": {}, "goal": None})
    provider = _FakeReasoningProvider(response)
    text = Tainted("asdkjaslkdj", Provenance.user())

    route = await generate_route(text, provider, _always_registered)

    assert route.kind == RouteKind.UNKNOWN
    assert route.detail is not None


async def test_generate_route_raises_on_malformed_json() -> None:
    """Non-JSON provider output raises RoutingError, not a bare JSONDecodeError."""
    provider = _FakeReasoningProvider("not json at all")
    text = Tainted("goal", Provenance.user())

    with pytest.raises(RoutingError):
        await generate_route(text, provider, _always_registered)


async def test_generate_route_raises_when_response_is_not_a_json_object() -> None:
    """A JSON array (not an object) at the top level is a real routing failure."""
    provider = _FakeReasoningProvider(json.dumps(["deterministic_command"]))
    text = Tainted("goal", Provenance.user())

    with pytest.raises(RoutingError):
        await generate_route(text, provider, _always_registered)


async def test_generate_route_raises_on_unrecognized_kind() -> None:
    """A 'kind' outside the three real, known values is a real routing failure."""
    response = json.dumps({"kind": "help", "capability_id": None, "arguments": {}, "goal": None})
    provider = _FakeReasoningProvider(response)
    text = Tainted("goal", Provenance.user())

    with pytest.raises(RoutingError):
        await generate_route(text, provider, _always_registered)


async def test_generate_route_rejects_an_unregistered_capability_id() -> None:
    """A model naming a real-shaped but unregistered capability id is rejected, never trusted."""
    response = json.dumps(
        {
            "kind": "deterministic_command",
            "capability_id": "shell.execute_arbitrary_command",
            "arguments": {},
            "goal": None,
        }
    )
    provider = _FakeReasoningProvider(response)
    text = Tainted("do something dangerous", Provenance.user())

    with pytest.raises(RoutingError):
        await generate_route(text, provider, _never_registered)


async def test_generate_route_rejects_non_string_capability_id() -> None:
    """A non-string capability_id fails validation before any registry lookup even happens."""
    response = json.dumps(
        {"kind": "deterministic_command", "capability_id": 123, "arguments": {}, "goal": None}
    )
    provider = _FakeReasoningProvider(response)
    text = Tainted("goal", Provenance.user())

    with pytest.raises(RoutingError):
        await generate_route(text, provider, _always_registered)


async def test_generate_route_rejects_non_object_arguments() -> None:
    """Non-object 'arguments' for a deterministic_command route is a real validation failure."""
    response = json.dumps(
        {
            "kind": "deterministic_command",
            "capability_id": "fs.read_file",
            "arguments": "not an object",
            "goal": None,
        }
    )
    provider = _FakeReasoningProvider(response)
    text = Tainted("goal", Provenance.user())

    with pytest.raises(RoutingError):
        await generate_route(text, provider, _always_registered)


async def test_generate_route_rejects_empty_goal_for_complex_goal() -> None:
    """A complex_goal response with an empty/missing goal is a real validation failure."""
    response = json.dumps(
        {"kind": "complex_goal", "capability_id": None, "arguments": {}, "goal": ""}
    )
    provider = _FakeReasoningProvider(response)
    text = Tainted("goal", Provenance.user())

    with pytest.raises(RoutingError):
        await generate_route(text, provider, _always_registered)


async def test_generate_route_confidence_is_never_taken_from_the_model() -> None:
    """Even if the model's own JSON smuggles a 'confidence' key, it is never read or trusted."""
    response = json.dumps(
        {
            "kind": "deterministic_command",
            "capability_id": "fs.read_file",
            "arguments": {"path": "/tmp/a.txt"},
            "goal": None,
            "confidence": 0.99,
        }
    )
    provider = _FakeReasoningProvider(response)
    text = Tainted("goal", Provenance.user())

    route = await generate_route(text, provider, _always_registered)

    assert route.confidence != pytest.approx(0.99)
