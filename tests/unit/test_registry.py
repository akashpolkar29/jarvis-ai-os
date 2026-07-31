"""Unit tests for jarvis.domain.registry."""

from __future__ import annotations

import pytest

from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, Effect
from jarvis.domain.errors import CapabilityAlreadyRegistered, CapabilityNotRegistered
from jarvis.domain.registry import CapabilityRegistry


def _descriptor(
    capability_id: str, description: str = "A test capability."
) -> CapabilityDescriptor:
    """Build a CapabilityDescriptor with the given id."""
    return CapabilityDescriptor(
        id=CapabilityId(capability_id),
        effects=Effect.READ_LOCAL,
        description=description,
    )


def test_register_then_get_returns_the_same_descriptor() -> None:
    """get() after register() returns the exact object that was registered."""
    registry = CapabilityRegistry()
    descriptor = _descriptor("fs.read_file")

    registry.register(descriptor)

    assert registry.get(descriptor.id) is descriptor


def test_get_unregistered_id_raises() -> None:
    """Looking up an id that was never registered raises CapabilityNotRegistered."""
    registry = CapabilityRegistry()

    with pytest.raises(CapabilityNotRegistered):
        registry.get(CapabilityId("fs.read_file"))


def test_duplicate_register_raises_and_leaves_original_intact() -> None:
    """A second register() with the same id is rejected, not merged or overwritten."""
    registry = CapabilityRegistry()
    original = _descriptor("fs.read_file", description="Original.")
    duplicate = _descriptor("fs.read_file", description="Different.")

    registry.register(original)

    with pytest.raises(CapabilityAlreadyRegistered):
        registry.register(duplicate)

    assert registry.get(original.id) is original


def test_distinct_capabilities_do_not_interfere() -> None:
    """Multiple independently registered capabilities are each retrievable on their own."""
    registry = CapabilityRegistry()
    read_descriptor = _descriptor("fs.read_file")
    write_descriptor = _descriptor("fs.write_file")

    registry.register(read_descriptor)
    registry.register(write_descriptor)

    assert registry.get(read_descriptor.id) is read_descriptor
    assert registry.get(write_descriptor.id) is write_descriptor


def test_contains_reflects_registration_state() -> None:
    """__contains__ is True only for ids that have actually been registered."""
    registry = CapabilityRegistry()
    descriptor = _descriptor("fs.read_file")
    unregistered_id = CapabilityId("fs.write_file")

    assert descriptor.id not in registry

    registry.register(descriptor)

    assert descriptor.id in registry
    assert unregistered_id not in registry


def test_len_reflects_number_of_registered_capabilities() -> None:
    """len() counts distinct registered capabilities."""
    registry = CapabilityRegistry()

    assert len(registry) == 0

    registry.register(_descriptor("fs.read_file"))
    registry.register(_descriptor("fs.write_file"))

    expected_count = 2
    assert len(registry) == expected_count


def test_iteration_yields_every_registered_descriptor_exactly_once() -> None:
    """Iterating the registry yields every registered descriptor, order not guaranteed."""
    registry = CapabilityRegistry()
    read_descriptor = _descriptor("fs.read_file")
    write_descriptor = _descriptor("fs.write_file")
    registry.register(read_descriptor)
    registry.register(write_descriptor)

    assert set(iter(registry)) == {read_descriptor, write_descriptor}
