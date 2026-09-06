"""Unit tests for jarvis.application.planning.planner."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from jarvis.application.planning.planner import PlanningError, PlanStep, generate_plan
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


async def test_generate_plan_returns_real_steps_for_a_valid_response() -> None:
    """A well-formed JSON array of steps becomes exactly that many real PlanSteps."""
    response = json.dumps(
        [
            {"capability_id": "fs.read_file", "arguments": {"path": "/tmp/a.txt"}},
            {"capability_id": "git.status", "arguments": {"repo_dir": "/tmp/repo"}},
        ]
    )
    provider = _FakeReasoningProvider(response)
    goal = Tainted("read a.txt then check repo status", Provenance.user())

    steps = await generate_plan(goal, provider, _always_registered)

    assert steps == (
        PlanStep(CapabilityId("fs.read_file"), {"path": "/tmp/a.txt"}),
        PlanStep(CapabilityId("git.status"), {"repo_dir": "/tmp/repo"}),
    )


async def test_generate_plan_returns_empty_tuple_for_an_empty_plan() -> None:
    """A real, valid, empty JSON array is a valid (if useless) plan -- not an error."""
    provider = _FakeReasoningProvider("[]")
    goal = Tainted("do nothing", Provenance.user())

    steps = await generate_plan(goal, provider, _always_registered)

    assert steps == ()


async def test_generate_plan_raises_on_malformed_json() -> None:
    """Non-JSON provider output raises PlanningError, not a bare JSONDecodeError."""
    provider = _FakeReasoningProvider("not json at all")
    goal = Tainted("goal", Provenance.user())

    with pytest.raises(PlanningError):
        await generate_plan(goal, provider, _always_registered)


async def test_generate_plan_raises_when_response_is_not_a_json_array() -> None:
    """A JSON object (not an array) at the top level is a real planning failure."""
    provider = _FakeReasoningProvider(json.dumps({"capability_id": "fs.read_file"}))
    goal = Tainted("goal", Provenance.user())

    with pytest.raises(PlanningError):
        await generate_plan(goal, provider, _always_registered)


@pytest.mark.parametrize(
    "raw_step",
    [
        "not an object",
        {"capability_id": "fs.read_file"},
        {"arguments": {}},
        {"capability_id": 123, "arguments": {}},
        {"capability_id": "fs.read_file", "arguments": "not an object"},
        {"capability_id": "  ", "arguments": {}},
    ],
)
async def test_generate_plan_raises_on_a_malformed_step(raw_step: object) -> None:
    """Every real malformed-step shape raises PlanningError, not a silent coercion."""
    provider = _FakeReasoningProvider(json.dumps([raw_step]))
    goal = Tainted("goal", Provenance.user())

    with pytest.raises(PlanningError):
        await generate_plan(goal, provider, _always_registered)


async def test_generate_plan_raises_when_a_step_names_an_unregistered_capability() -> None:
    """A structurally valid step naming a real-shaped but unregistered capability id fails."""
    response = json.dumps([{"capability_id": "fs.read_file", "arguments": {"path": "/tmp/a.txt"}}])
    provider = _FakeReasoningProvider(response)
    goal = Tainted("goal", Provenance.user())

    with pytest.raises(PlanningError):
        await generate_plan(goal, provider, _never_registered)
