"""Unit tests for jarvis.domain.workflow."""

from __future__ import annotations

import pytest

from jarvis.domain.capability import CapabilityId
from jarvis.domain.skill import SkillId
from jarvis.domain.workflow import WorkflowDescriptor, WorkflowId, WorkflowStep

VALID_WORKFLOW_IDS = ["job_search_assistant", "research", "a", "coding-dev", "x.y.z"]
INVALID_WORKFLOW_IDS = [
    "",
    " ",
    "job search",
    " research",
    "research ",
    "job\tsearch",
    "job\nsearch",
]


@pytest.mark.parametrize("value", VALID_WORKFLOW_IDS)
def test_workflow_id_accepts_valid_tokens(value: str) -> None:
    """WorkflowId accepts non-empty, whitespace-free tokens."""
    assert WorkflowId(value).value == value


@pytest.mark.parametrize("value", INVALID_WORKFLOW_IDS)
def test_workflow_id_rejects_invalid_tokens(value: str) -> None:
    """WorkflowId rejects empty strings and anything containing whitespace."""
    with pytest.raises(ValueError, match="WorkflowId"):
        WorkflowId(value)


def test_workflow_id_str_is_the_underlying_token() -> None:
    """str(WorkflowId(...)) is the plain token, for log fields."""
    assert str(WorkflowId("research")) == "research"


def _step(**overrides: object) -> WorkflowStep:
    defaults: dict[str, object] = {
        "capability_id": CapabilityId("fs.read_file"),
        "arguments": {"path": "/home/user/notes.txt"},
        "description": "Read a known local file.",
    }
    defaults.update(overrides)
    return WorkflowStep(**defaults)  # type: ignore[arg-type]


def test_workflow_step_accepts_valid_construction() -> None:
    """A well-formed WorkflowStep constructs and exposes its fields verbatim."""
    step = _step()
    assert step.capability_id == CapabilityId("fs.read_file")
    assert step.arguments == {"path": "/home/user/notes.txt"}
    assert step.description == "Read a known local file."


def test_workflow_step_rejects_empty_description() -> None:
    """WorkflowStep raises ValueError on an empty description."""
    with pytest.raises(ValueError, match="description"):
        _step(description="")


def test_workflow_step_is_frozen() -> None:
    """WorkflowStep instances are immutable, matching WorkflowDescriptor."""
    step = _step()
    with pytest.raises(AttributeError):
        step.description = "renamed"  # type: ignore[misc]


def _descriptor(**overrides: object) -> WorkflowDescriptor:
    defaults: dict[str, object] = {
        "id": WorkflowId("research"),
        "name": "Research",
        "description": "Gather and synthesize information.",
        "steps": (_step(),),
    }
    defaults.update(overrides)
    return WorkflowDescriptor(**defaults)  # type: ignore[arg-type]


def test_workflow_descriptor_accepts_valid_construction() -> None:
    """A well-formed WorkflowDescriptor constructs and exposes its fields verbatim."""
    descriptor = _descriptor()
    assert descriptor.id == WorkflowId("research")
    assert descriptor.name == "Research"
    assert descriptor.steps == (_step(),)
    assert descriptor.skill_id is None
    assert descriptor.parameters == ()
    assert descriptor.metadata == {}


def test_workflow_descriptor_rejects_empty_name() -> None:
    """WorkflowDescriptor raises ValueError on an empty name."""
    with pytest.raises(ValueError, match="name"):
        _descriptor(name="")


def test_workflow_descriptor_rejects_empty_description() -> None:
    """WorkflowDescriptor raises ValueError on an empty description."""
    with pytest.raises(ValueError, match="description"):
        _descriptor(description="")


def test_workflow_descriptor_rejects_empty_steps() -> None:
    """WorkflowDescriptor raises ValueError when steps is empty.

    A workflow with no steps composes nothing.
    """
    with pytest.raises(ValueError, match="steps"):
        _descriptor(steps=())


def test_workflow_descriptor_accepts_optional_skill_id_parameters_and_metadata() -> None:
    """skill_id/parameters/metadata are optional, additive fields only."""
    descriptor = _descriptor(
        skill_id=SkillId("research"),
        parameters=("query",),
        metadata={"source": "wp185"},
    )
    assert descriptor.skill_id == SkillId("research")
    assert descriptor.parameters == ("query",)
    assert descriptor.metadata == {"source": "wp185"}


def test_workflow_descriptor_is_frozen() -> None:
    """WorkflowDescriptor instances are immutable, matching SkillDescriptor."""
    descriptor = _descriptor()
    with pytest.raises(AttributeError):
        descriptor.name = "renamed"  # type: ignore[misc]
