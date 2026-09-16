"""Unit tests for jarvis.application.routing.router's Stage-B reasoning-fallback logic."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from jarvis.application.routing.router import (
    RouteKind,
    RoutingError,
    _build_routing_prompt,
    _select_relevant_skills,
    generate_route,
)
from jarvis.domain.capability import CapabilityId
from jarvis.domain.evidence import Candidate
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.skill import SkillDescriptor, SkillId

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt


class _FakeReasoningProvider:
    """A minimal, test-local ReasoningPort, always returning a fixed Candidate.

    Records every prompt it was actually called with, so tests can
    assert on what the real, final prompt text contained (WP-175).
    """

    def __init__(self, content: str) -> None:
        self._content = content
        self.received_prompts: list[str] = []

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        self.received_prompts.append(task)
        candidate = Candidate(author="test-provider", content=self._content)
        return Tainted(candidate, Provenance.system())


def _skill(
    skill_id: str,
    *,
    domain: str = "test",
    name: str = "Test Skill",
    tags: tuple[str, ...] = (),
) -> SkillDescriptor:
    return SkillDescriptor(
        id=SkillId(skill_id),
        name=name,
        description=f"A test skill for {skill_id}.",
        domain=domain,
        capability_ids=(CapabilityId("fs.read_file"),),
        tags=tags,
    )


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


def test_select_relevant_skills_matches_on_domain_substring() -> None:
    """A skill whose domain appears in the request text is selected."""
    filesystem = _skill("filesystem", domain="filesystem")
    calendar = _skill("calendar", domain="calendar")

    matches = _select_relevant_skills("please search the filesystem", (filesystem, calendar))

    assert matches == (filesystem,)


def test_select_relevant_skills_matches_on_tag_substring() -> None:
    """A skill whose tag appears in the request text is selected, even if id/domain don't match."""
    filesystem = _skill("filesystem", domain="filesystem", tags=("files", "search"))

    matches = _select_relevant_skills("please search my documents", (filesystem,))

    assert matches == (filesystem,)


def test_select_relevant_skills_returns_empty_when_nothing_matches() -> None:
    """No fallback to the full list -- an irrelevant request yields no skill context at all."""
    filesystem = _skill("filesystem", domain="filesystem")

    matches = _select_relevant_skills("xyzzy plugh qux", (filesystem,))

    assert matches == ()


def test_select_relevant_skills_is_deterministic_regardless_of_input_order() -> None:
    """Sorted by skill id internally -- the same candidates in any order give the same result."""
    a = _skill("a-skill", domain="alpha")
    b = _skill("b-skill", domain="alpha")

    forward = _select_relevant_skills("alpha request", (a, b))
    reversed_input = _select_relevant_skills("alpha request", (b, a))

    assert forward == reversed_input == (a, b)


def test_select_relevant_skills_respects_the_limit() -> None:
    """At most `limit` skills are returned, even when more than that many match."""
    skills = tuple(_skill(f"skill-{i}", domain="shared") for i in range(10))

    matches = _select_relevant_skills("shared request", skills, limit=3)

    expected_match_count = 3
    assert len(matches) == expected_match_count


def test_build_routing_prompt_without_skills_matches_the_original_prompt_shape() -> None:
    """No skills supplied -> no skill-context section at all, byte-for-byte the pre-WP-175 shape."""
    prompt = _build_routing_prompt("read my file")

    assert "Potentially relevant" not in prompt
    assert "read my file" in prompt


def test_build_routing_prompt_with_skills_includes_compact_context_only() -> None:
    """Relevant skills add a compact block naming id/domain/description/capabilities only."""
    filesystem = _skill("filesystem", domain="filesystem")

    prompt = _build_routing_prompt("read a file", (filesystem,))

    assert "filesystem" in prompt
    assert "fs.read_file" in prompt
    assert "Potentially relevant" in prompt


def test_build_routing_prompt_never_includes_skill_instructions() -> None:
    """A skill's own free-text instructions never reach the prompt -- compact context only."""
    skill = SkillDescriptor(
        id=SkillId("filesystem"),
        name="Filesystem",
        description="Read and search local files.",
        domain="filesystem",
        capability_ids=(CapabilityId("fs.read_file"),),
        instructions="SECRET_MARKER_SHOULD_NEVER_APPEAR_IN_A_PROMPT",
    )

    prompt = _build_routing_prompt("read a file", (skill,))

    assert "SECRET_MARKER_SHOULD_NEVER_APPEAR_IN_A_PROMPT" not in prompt


async def test_generate_route_with_no_matching_skills_sends_the_original_prompt_shape() -> None:
    """A request matching none of the supplied skills is routed exactly as it was before WP-175."""
    response = json.dumps({"kind": "unknown", "capability_id": None, "arguments": {}, "goal": None})
    provider = _FakeReasoningProvider(response)
    text = Tainted("asdkjaslkdj", Provenance.user())
    unrelated_skill = _skill("browser", domain="browser")

    await generate_route(text, provider, _always_registered, (unrelated_skill,))

    assert "Potentially relevant" not in provider.received_prompts[0]


async def test_generate_route_with_a_matching_skill_includes_it_in_the_real_prompt() -> None:
    """A relevant skill genuinely reaches the real prompt sent to the provider."""
    response = json.dumps(
        {
            "kind": "deterministic_command",
            "capability_id": "fs.read_file",
            "arguments": {"path": "/tmp/a.txt"},
            "goal": None,
        }
    )
    provider = _FakeReasoningProvider(response)
    text = Tainted("read a file from the filesystem at /tmp/a.txt", Provenance.user())
    filesystem_skill = _skill("filesystem", domain="filesystem")

    route = await generate_route(text, provider, _always_registered, (filesystem_skill,))

    assert "filesystem" in provider.received_prompts[0]
    assert route.kind == RouteKind.DETERMINISTIC_COMMAND


async def test_generate_route_still_rejects_unregistered_capability_with_skill_context() -> None:
    """Skill context is purely advisory -- is_registered still runs unconditionally."""
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
    filesystem_skill = _skill("filesystem", domain="filesystem")

    with pytest.raises(RoutingError):
        await generate_route(text, provider, _never_registered, (filesystem_skill,))
