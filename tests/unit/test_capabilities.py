"""Unit tests for jarvis.kernel.capabilities.build_default_registry."""

from __future__ import annotations

from jarvis.domain.capability import Effect, Tier
from jarvis.kernel.capabilities import (
    DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
    DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID,
    DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID,
    DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID,
    MUSIC_NEXT_CAPABILITY_ID,
    MUSIC_PAUSE_CAPABILITY_ID,
    MUSIC_PLAY_CAPABILITY_ID,
    MUSIC_PREVIOUS_CAPABILITY_ID,
    PING_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
    TERMINAL_RUN_CAPABILITY_ID,
    build_default_registry,
)

_EXPECTED_CAPABILITY_COUNT = 11


def test_build_default_registry_does_not_raise() -> None:
    """build_default_registry() completes without raising CapabilityAlreadyRegistered.

    This is the real collision test, not an assumption: register()
    raises on a duplicate id, so this passing IS the proof no two
    capabilities declared here share an id.
    """
    build_default_registry()


def test_build_default_registry_registers_exactly_the_expected_ids() -> None:
    """The registry contains exactly the known capability ids, no more, no fewer."""
    registry = build_default_registry()

    ids = {descriptor.id for descriptor in registry}

    assert ids == {
        PING_CAPABILITY_ID,
        MUSIC_PLAY_CAPABILITY_ID,
        MUSIC_PAUSE_CAPABILITY_ID,
        MUSIC_NEXT_CAPABILITY_ID,
        MUSIC_PREVIOUS_CAPABILITY_ID,
        READ_FILE_CAPABILITY_ID,
        DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
        DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID,
        DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID,
        DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID,
        TERMINAL_RUN_CAPABILITY_ID,
    }
    assert len(registry) == _EXPECTED_CAPABILITY_COUNT


def test_desktop_brave_open_url_has_execute_effects() -> None:
    """desktop.brave_open_url is registered with Effect.EXECUTE (floors Tier.CONFIRM)."""
    registry = build_default_registry()

    assert registry.get(DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID).effects == Effect.EXECUTE


def test_desktop_vscode_open_file_has_execute_effects() -> None:
    """desktop.vscode_open_file is registered with Effect.EXECUTE (floors Tier.CONFIRM)."""
    registry = build_default_registry()

    assert registry.get(DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID).effects == Effect.EXECUTE


def test_desktop_claude_app_send_text_has_execute_effects() -> None:
    """desktop.claude_app_send_text is registered with Effect.EXECUTE (floors Tier.CONFIRM)."""
    registry = build_default_registry()

    assert registry.get(DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID).effects == Effect.EXECUTE


def test_desktop_chatgpt_app_send_text_has_execute_effects() -> None:
    """desktop.chatgpt_app_send_text is registered with Effect.EXECUTE (floors Tier.CONFIRM)."""
    registry = build_default_registry()

    assert registry.get(DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID).effects == Effect.EXECUTE


def test_terminal_run_has_destructive_and_execute_effects() -> None:
    """terminal.run is registered with DESTRUCTIVE | EXECUTE -- floors Tier.MANUAL_ONLY.

    Unconditionally, per ADR-0046: this is the one capability this
    milestone registers whose real command execution is genuinely
    open-ended, and it must never be satisfiable below MANUAL_ONLY.
    """
    registry = build_default_registry()

    descriptor = registry.get(TERMINAL_RUN_CAPABILITY_ID)
    assert descriptor.effects == (Effect.DESTRUCTIVE | Effect.EXECUTE)
    assert descriptor.required_tier == Tier.MANUAL_ONLY


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
