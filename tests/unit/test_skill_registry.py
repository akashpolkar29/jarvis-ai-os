"""Unit tests for jarvis.domain.skill_registry."""

from __future__ import annotations

import pytest

from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, Effect
from jarvis.domain.errors import (
    SkillAlreadyRegistered,
    SkillNotRegistered,
    SkillReferencesUnknownCapability,
)
from jarvis.domain.registry import CapabilityRegistry
from jarvis.domain.skill import SkillDescriptor, SkillId
from jarvis.domain.skill_registry import SkillRegistry, validate_skill_registry


def _capability_descriptor(
    capability_id: str, description: str = "A test capability."
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=CapabilityId(capability_id), effects=Effect.READ_LOCAL, description=description
    )


def _skill_descriptor(
    skill_id: str,
    *,
    capability_ids: tuple[str, ...] = ("fs.read_file",),
    name: str = "Test Skill",
) -> SkillDescriptor:
    return SkillDescriptor(
        id=SkillId(skill_id),
        name=name,
        description="A test skill.",
        domain="test",
        capability_ids=tuple(CapabilityId(c) for c in capability_ids),
    )


def test_register_then_get_returns_the_same_descriptor() -> None:
    """get() after register() returns the exact object that was registered."""
    registry = SkillRegistry()
    descriptor = _skill_descriptor("filesystem")

    registry.register(descriptor)

    assert registry.get(descriptor.id) is descriptor


def test_get_unregistered_id_raises() -> None:
    """Looking up an id that was never registered raises SkillNotRegistered."""
    registry = SkillRegistry()

    with pytest.raises(SkillNotRegistered):
        registry.get(SkillId("filesystem"))


def test_duplicate_register_raises_and_leaves_original_intact() -> None:
    """A second register() with the same id is rejected, not merged or overwritten."""
    registry = SkillRegistry()
    original = _skill_descriptor("filesystem", name="Original")
    duplicate = _skill_descriptor("filesystem", name="Different")

    registry.register(original)

    with pytest.raises(SkillAlreadyRegistered):
        registry.register(duplicate)

    assert registry.get(original.id) is original


def test_distinct_skills_do_not_interfere() -> None:
    """Multiple independently registered skills are each retrievable on their own."""
    registry = SkillRegistry()
    filesystem = _skill_descriptor("filesystem")
    tasks = _skill_descriptor("tasks", capability_ids=("memory.retrieve",))

    registry.register(filesystem)
    registry.register(tasks)

    assert registry.get(filesystem.id) is filesystem
    assert registry.get(tasks.id) is tasks


def test_contains_reflects_registration_state() -> None:
    """__contains__ is True only for ids that have actually been registered."""
    registry = SkillRegistry()
    descriptor = _skill_descriptor("filesystem")
    unregistered_id = SkillId("tasks")

    assert descriptor.id not in registry

    registry.register(descriptor)

    assert descriptor.id in registry
    assert unregistered_id not in registry


def test_len_reflects_number_of_registered_skills() -> None:
    """len() counts distinct registered skills."""
    registry = SkillRegistry()

    assert len(registry) == 0

    registry.register(_skill_descriptor("filesystem"))
    registry.register(_skill_descriptor("tasks", capability_ids=("memory.retrieve",)))

    expected_count = 2
    assert len(registry) == expected_count


def test_iteration_yields_every_registered_descriptor_exactly_once() -> None:
    """Iterating the registry yields every registered descriptor, order not guaranteed."""
    registry = SkillRegistry()
    filesystem = _skill_descriptor("filesystem")
    tasks = _skill_descriptor("tasks", capability_ids=("memory.retrieve",))
    registry.register(filesystem)
    registry.register(tasks)

    assert set(iter(registry)) == {filesystem, tasks}


def test_validate_skill_registry_passes_when_every_capability_is_real() -> None:
    """validate_skill_registry raises nothing when every skill's capabilities are registered."""
    skills = SkillRegistry()
    skills.register(_skill_descriptor("filesystem", capability_ids=("fs.read_file",)))
    capabilities = CapabilityRegistry()
    capabilities.register(_capability_descriptor("fs.read_file"))

    validate_skill_registry(skills, capabilities)  # must not raise


def test_validate_skill_registry_raises_on_unknown_capability() -> None:
    """validate_skill_registry raises when a skill names a capability that was never registered."""
    skills = SkillRegistry()
    skills.register(_skill_descriptor("filesystem", capability_ids=("fs.read_file",)))
    capabilities = CapabilityRegistry()  # deliberately empty

    with pytest.raises(SkillReferencesUnknownCapability, match="fs\\.read_file"):
        validate_skill_registry(skills, capabilities)


def test_validate_skill_registry_checks_every_capability_id_on_a_multi_capability_skill() -> None:
    """A skill naming several capabilities is only valid if all of them are real."""
    skills = SkillRegistry()
    skills.register(_skill_descriptor("filesystem", capability_ids=("fs.read_file", "fs.list_dir")))
    capabilities = CapabilityRegistry()
    capabilities.register(_capability_descriptor("fs.read_file"))
    # fs.list_dir deliberately not registered

    with pytest.raises(SkillReferencesUnknownCapability, match="fs\\.list_dir"):
        validate_skill_registry(skills, capabilities)


def test_validate_skill_registry_passes_on_empty_skill_registry() -> None:
    """An empty skill registry trivially validates against any capability registry."""
    validate_skill_registry(SkillRegistry(), CapabilityRegistry())
