"""Unit tests for jarvis.domain.skill."""

from __future__ import annotations

import pytest

from jarvis.domain.capability import CapabilityId
from jarvis.domain.skill import SkillDescriptor, SkillId

VALID_SKILL_IDS = ["filesystem", "job_research", "a", "coding-dev", "x.y.z"]
INVALID_SKILL_IDS = [
    "",
    " ",
    "file system",
    " filesystem",
    "filesystem ",
    "file\tsystem",
    "file\nsystem",
]


@pytest.mark.parametrize("value", VALID_SKILL_IDS)
def test_skill_id_accepts_valid_tokens(value: str) -> None:
    """SkillId accepts non-empty, whitespace-free tokens."""
    assert SkillId(value).value == value


@pytest.mark.parametrize("value", INVALID_SKILL_IDS)
def test_skill_id_rejects_invalid_tokens(value: str) -> None:
    """SkillId rejects empty strings and anything containing whitespace."""
    with pytest.raises(ValueError, match="SkillId"):
        SkillId(value)


def test_skill_id_str_is_the_underlying_token() -> None:
    """str(SkillId(...)) is the plain token, for log fields."""
    assert str(SkillId("filesystem")) == "filesystem"


def _descriptor(**overrides: object) -> SkillDescriptor:
    defaults: dict[str, object] = {
        "id": SkillId("filesystem"),
        "name": "Filesystem",
        "description": "Read, search, and manage local files.",
        "domain": "filesystem",
        "capability_ids": (CapabilityId("fs.read_file"),),
    }
    defaults.update(overrides)
    return SkillDescriptor(**defaults)  # type: ignore[arg-type]


def test_skill_descriptor_accepts_valid_construction() -> None:
    """A well-formed SkillDescriptor constructs and exposes its fields verbatim."""
    descriptor = _descriptor()
    assert descriptor.id == SkillId("filesystem")
    assert descriptor.name == "Filesystem"
    assert descriptor.capability_ids == (CapabilityId("fs.read_file"),)
    assert descriptor.instructions is None
    assert descriptor.tags == ()


def test_skill_descriptor_rejects_empty_name() -> None:
    """SkillDescriptor raises ValueError on an empty name."""
    with pytest.raises(ValueError, match="name"):
        _descriptor(name="")


def test_skill_descriptor_rejects_empty_description() -> None:
    """SkillDescriptor raises ValueError on an empty description."""
    with pytest.raises(ValueError, match="description"):
        _descriptor(description="")


def test_skill_descriptor_rejects_empty_domain() -> None:
    """SkillDescriptor raises ValueError on an empty domain."""
    with pytest.raises(ValueError, match="domain"):
        _descriptor(domain="")


def test_skill_descriptor_rejects_empty_capability_ids() -> None:
    """SkillDescriptor raises ValueError when capability_ids is empty.

    A skill with no real capability behind it describes nothing
    invocable, and would not be a grouping of existing behavior at all.
    """
    with pytest.raises(ValueError, match="capability_ids"):
        _descriptor(capability_ids=())


def test_skill_descriptor_accepts_optional_instructions_and_tags() -> None:
    """instructions/tags are optional, additive discoverability metadata only."""
    descriptor = _descriptor(
        instructions="Prefer fs.read_file over fs.search_content for a known path.",
        tags=("files", "local"),
    )
    assert descriptor.instructions is not None
    assert descriptor.tags == ("files", "local")


def test_skill_descriptor_is_frozen() -> None:
    """SkillDescriptor instances are immutable, matching CapabilityDescriptor."""
    descriptor = _descriptor()
    with pytest.raises(AttributeError):
        descriptor.name = "renamed"  # type: ignore[misc]
