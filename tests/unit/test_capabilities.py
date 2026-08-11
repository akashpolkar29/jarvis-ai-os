"""Unit tests for jarvis.kernel.capabilities.build_default_registry."""

from __future__ import annotations

from jarvis.domain.capability import Effect
from jarvis.kernel.capabilities import (
    MUSIC_NEXT_CAPABILITY_ID,
    MUSIC_PAUSE_CAPABILITY_ID,
    MUSIC_PLAY_CAPABILITY_ID,
    MUSIC_PREVIOUS_CAPABILITY_ID,
    PING_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
    build_default_registry,
)

_EXPECTED_CAPABILITY_COUNT = 6


def test_build_default_registry_does_not_raise() -> None:
    """build_default_registry() completes without raising CapabilityAlreadyRegistered.

    This is the real collision test, not an assumption: register()
    raises on a duplicate id, so this passing IS the proof no two
    capabilities declared here share an id.
    """
    build_default_registry()


def test_build_default_registry_registers_exactly_the_expected_ids() -> None:
    """The registry contains exactly the six known capability ids, no more, no fewer."""
    registry = build_default_registry()

    ids = {descriptor.id for descriptor in registry}

    assert ids == {
        PING_CAPABILITY_ID,
        MUSIC_PLAY_CAPABILITY_ID,
        MUSIC_PAUSE_CAPABILITY_ID,
        MUSIC_NEXT_CAPABILITY_ID,
        MUSIC_PREVIOUS_CAPABILITY_ID,
        READ_FILE_CAPABILITY_ID,
    }
    assert len(registry) == _EXPECTED_CAPABILITY_COUNT


def test_ping_has_read_local_effects() -> None:
    """ping is registered with Effect.READ_LOCAL, matching its no-op nature."""
    registry = build_default_registry()

    assert registry.get(PING_CAPABILITY_ID).effects == Effect.READ_LOCAL


def test_music_capabilities_have_write_local_effects() -> None:
    """All four music.* capabilities are registered with Effect.WRITE_LOCAL."""
    registry = build_default_registry()

    for capability_id in (
        MUSIC_PLAY_CAPABILITY_ID,
        MUSIC_PAUSE_CAPABILITY_ID,
        MUSIC_NEXT_CAPABILITY_ID,
        MUSIC_PREVIOUS_CAPABILITY_ID,
    ):
        assert registry.get(capability_id).effects == Effect.WRITE_LOCAL


def test_read_file_has_egress_local_effects() -> None:
    """fs.read_file is registered with Effect.EGRESS_LOCAL, not READ_LOCAL."""
    registry = build_default_registry()

    assert registry.get(READ_FILE_CAPABILITY_ID).effects == Effect.EGRESS_LOCAL


def test_every_descriptor_has_a_non_empty_description() -> None:
    """Every registered capability has a real, non-empty description.

    CapabilityDescriptor.__post_init__ already validates this at
    construction time, so this test is really confirming
    build_default_registry() never tries to slip an empty one past
    that guard -- a real, if very unlikely, transcription mistake.
    """
    registry = build_default_registry()

    for descriptor in registry:
        assert descriptor.description
