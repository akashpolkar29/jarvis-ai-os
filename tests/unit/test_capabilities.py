"""Unit tests for jarvis.kernel.capabilities.build_default_registry."""

from __future__ import annotations

from jarvis.domain.capability import Effect, Tier
from jarvis.kernel.capabilities import (
    BROWSER_CLOSE_PAGE_CAPABILITY_ID,
    BROWSER_INSPECT_DOM_CAPABILITY_ID,
    BROWSER_OPEN_PAGE_CAPABILITY_ID,
    BROWSER_SCREENSHOT_CAPABILITY_ID,
    CALENDAR_LIST_EVENTS_CAPABILITY_ID,
    CODING_RUN_TASK_CAPABILITY_ID,
    DELETE_FILE_CAPABILITY_ID,
    DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
    DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID,
    DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID,
    DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID,
    DOCKER_BUILD_IMAGE_CAPABILITY_ID,
    DOCKER_LIST_CONTAINERS_CAPABILITY_ID,
    DOCKER_RUN_CONTAINER_CAPABILITY_ID,
    DOCKER_STOP_CONTAINER_CAPABILITY_ID,
    EMAIL_LIST_MESSAGES_CAPABILITY_ID,
    EMAIL_READ_MESSAGE_CAPABILITY_ID,
    GIT_COMMIT_CAPABILITY_ID,
    GIT_CREATE_BRANCH_CAPABILITY_ID,
    GIT_FORCE_PUSH_CAPABILITY_ID,
    GIT_PUSH_CAPABILITY_ID,
    GIT_STATUS_CAPABILITY_ID,
    LIST_DIR_CAPABILITY_ID,
    MEMORY_BACKUP_CAPABILITY_ID,
    MEMORY_FORGET_CAPABILITY_ID,
    MEMORY_PIN_CAPABILITY_ID,
    MEMORY_RESTORE_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    MOVE_FILE_CAPABILITY_ID,
    MUSIC_NEXT_CAPABILITY_ID,
    MUSIC_PAUSE_CAPABILITY_ID,
    MUSIC_PLAY_CAPABILITY_ID,
    MUSIC_PREVIOUS_CAPABILITY_ID,
    PING_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
    TERMINAL_RUN_CAPABILITY_ID,
    build_default_registry,
)

_EXPECTED_CAPABILITY_COUNT = 36


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
        LIST_DIR_CAPABILITY_ID,
        MOVE_FILE_CAPABILITY_ID,
        DELETE_FILE_CAPABILITY_ID,
        DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
        DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID,
        DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID,
        DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID,
        TERMINAL_RUN_CAPABILITY_ID,
        DOCKER_LIST_CONTAINERS_CAPABILITY_ID,
        DOCKER_RUN_CONTAINER_CAPABILITY_ID,
        DOCKER_STOP_CONTAINER_CAPABILITY_ID,
        DOCKER_BUILD_IMAGE_CAPABILITY_ID,
        GIT_STATUS_CAPABILITY_ID,
        GIT_CREATE_BRANCH_CAPABILITY_ID,
        GIT_COMMIT_CAPABILITY_ID,
        GIT_PUSH_CAPABILITY_ID,
        GIT_FORCE_PUSH_CAPABILITY_ID,
        MEMORY_RETRIEVE_CAPABILITY_ID,
        MEMORY_PIN_CAPABILITY_ID,
        MEMORY_FORGET_CAPABILITY_ID,
        MEMORY_BACKUP_CAPABILITY_ID,
        MEMORY_RESTORE_CAPABILITY_ID,
        BROWSER_OPEN_PAGE_CAPABILITY_ID,
        BROWSER_SCREENSHOT_CAPABILITY_ID,
        BROWSER_INSPECT_DOM_CAPABILITY_ID,
        BROWSER_CLOSE_PAGE_CAPABILITY_ID,
        CODING_RUN_TASK_CAPABILITY_ID,
        EMAIL_LIST_MESSAGES_CAPABILITY_ID,
        EMAIL_READ_MESSAGE_CAPABILITY_ID,
        CALENDAR_LIST_EVENTS_CAPABILITY_ID,
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


def test_docker_list_containers_has_read_local_effects() -> None:
    """docker.list_containers is registered with Effect.READ_LOCAL -- always Tier.ALLOW."""
    registry = build_default_registry()

    descriptor = registry.get(DOCKER_LIST_CONTAINERS_CAPABILITY_ID)
    assert descriptor.effects == Effect.READ_LOCAL
    assert descriptor.required_tier == Tier.ALLOW


def test_docker_run_container_has_destructive_and_execute_effects() -> None:
    """docker.run_container is DESTRUCTIVE | EXECUTE -- floors Tier.MANUAL_ONLY unconditionally."""
    registry = build_default_registry()

    descriptor = registry.get(DOCKER_RUN_CONTAINER_CAPABILITY_ID)
    assert descriptor.effects == (Effect.DESTRUCTIVE | Effect.EXECUTE)
    assert descriptor.required_tier == Tier.MANUAL_ONLY


def test_docker_stop_container_has_execute_effects_only() -> None:
    """docker.stop_container is EXECUTE only -- floors Tier.CONFIRM, not MANUAL_ONLY.

    Judgment call (see kernel/desktop.py's own docstring): stopping is
    recoverable via docker start and cannot itself consume unbounded
    new resources, unlike run/build.
    """
    registry = build_default_registry()

    descriptor = registry.get(DOCKER_STOP_CONTAINER_CAPABILITY_ID)
    assert descriptor.effects == Effect.EXECUTE
    assert descriptor.required_tier == Tier.CONFIRM


def test_docker_build_image_has_destructive_and_execute_effects() -> None:
    """docker.build_image is DESTRUCTIVE | EXECUTE -- floors Tier.MANUAL_ONLY unconditionally."""
    registry = build_default_registry()

    descriptor = registry.get(DOCKER_BUILD_IMAGE_CAPABILITY_ID)
    assert descriptor.effects == (Effect.DESTRUCTIVE | Effect.EXECUTE)
    assert descriptor.required_tier == Tier.MANUAL_ONLY


def test_git_status_has_read_local_effects() -> None:
    """git.status is registered with Effect.READ_LOCAL -- always Tier.ALLOW."""
    registry = build_default_registry()

    descriptor = registry.get(GIT_STATUS_CAPABILITY_ID)
    assert descriptor.effects == Effect.READ_LOCAL
    assert descriptor.required_tier == Tier.ALLOW


def test_git_create_branch_and_commit_and_push_have_write_local_effects() -> None:
    """git.create_branch/commit/push are all WRITE_LOCAL -- floor Tier.CONFIRM."""
    registry = build_default_registry()

    for capability_id in (
        GIT_CREATE_BRANCH_CAPABILITY_ID,
        GIT_COMMIT_CAPABILITY_ID,
        GIT_PUSH_CAPABILITY_ID,
    ):
        descriptor = registry.get(capability_id)
        assert descriptor.effects == Effect.WRITE_LOCAL
        assert descriptor.required_tier == Tier.CONFIRM


def test_git_force_push_has_destructive_and_irreversible_effects() -> None:
    """git.force_push is DESTRUCTIVE | IRREVERSIBLE -- floors Tier.MANUAL_ONLY unconditionally.

    Its own capability id, deliberately never a flag on git.push (see
    kernel/desktop.py's own docstring for the full reasoning).
    """
    registry = build_default_registry()

    descriptor = registry.get(GIT_FORCE_PUSH_CAPABILITY_ID)
    assert descriptor.effects == (Effect.DESTRUCTIVE | Effect.IRREVERSIBLE)
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


def test_list_dir_has_egress_local_effects() -> None:
    """fs.list_dir mirrors fs.read_file's own EGRESS_LOCAL/ALLOW floor exactly (ADR-0060)."""
    registry = build_default_registry()

    assert registry.get(LIST_DIR_CAPABILITY_ID).effects == Effect.EGRESS_LOCAL


def test_move_file_has_write_local_effects() -> None:
    """fs.move_file floors WRITE_LOCAL/CONFIRM, the ordinary local-write floor (ADR-0060)."""
    registry = build_default_registry()

    assert registry.get(MOVE_FILE_CAPABILITY_ID).effects == Effect.WRITE_LOCAL


def test_delete_file_has_destructive_irreversible_effects() -> None:
    """fs.delete_file always floors MANUAL_ONLY, mirroring git.force_push/memory.forget (ADR-0060)."""  # noqa: E501
    registry = build_default_registry()

    assert (
        registry.get(DELETE_FILE_CAPABILITY_ID).effects == Effect.DESTRUCTIVE | Effect.IRREVERSIBLE
    )


def test_memory_retrieve_has_read_local_effects() -> None:
    """memory.retrieve is registered with Effect.READ_LOCAL -- always Tier.ALLOW.

    The bare act of querying, per ADR-0048's own worked example --
    distinct from what a caller does with a recalled record
    (ADR-0050's own separate concern, gated at the point of use, not
    registered here).
    """
    registry = build_default_registry()

    descriptor = registry.get(MEMORY_RETRIEVE_CAPABILITY_ID)
    assert descriptor.effects == Effect.READ_LOCAL
    assert descriptor.required_tier == Tier.ALLOW


def test_memory_pin_has_write_local_effects() -> None:
    """memory.pin is registered with Effect.WRITE_LOCAL -- Tier.CONFIRM, not dynamic."""
    registry = build_default_registry()

    descriptor = registry.get(MEMORY_PIN_CAPABILITY_ID)
    assert descriptor.effects == Effect.WRITE_LOCAL
    assert descriptor.required_tier == Tier.CONFIRM


def test_memory_forget_has_destructive_and_irreversible_effects() -> None:
    """memory.forget is DESTRUCTIVE | IRREVERSIBLE -- Tier.MANUAL_ONLY, same as git.force_push."""
    registry = build_default_registry()

    descriptor = registry.get(MEMORY_FORGET_CAPABILITY_ID)
    assert descriptor.effects == Effect.DESTRUCTIVE | Effect.IRREVERSIBLE
    assert descriptor.required_tier == Tier.MANUAL_ONLY


def test_memory_backup_has_write_local_effects() -> None:
    """memory.backup is WRITE_LOCAL -- Tier.CONFIRM, same shape as fs.move_file (ADR-0061)."""
    registry = build_default_registry()

    descriptor = registry.get(MEMORY_BACKUP_CAPABILITY_ID)
    assert descriptor.effects == Effect.WRITE_LOCAL
    assert descriptor.required_tier == Tier.CONFIRM


def test_memory_restore_has_destructive_and_irreversible_effects() -> None:
    """memory.restore is DESTRUCTIVE | IRREVERSIBLE -- Tier.MANUAL_ONLY, same as memory.forget (ADR-0061)."""  # noqa: E501
    registry = build_default_registry()

    descriptor = registry.get(MEMORY_RESTORE_CAPABILITY_ID)
    assert descriptor.effects == Effect.DESTRUCTIVE | Effect.IRREVERSIBLE
    assert descriptor.required_tier == Tier.MANUAL_ONLY


def test_browser_open_page_has_execute_effects() -> None:
    """browser.open_page is EXECUTE -- Tier.CONFIRM, same as desktop.brave_open_url."""
    registry = build_default_registry()

    descriptor = registry.get(BROWSER_OPEN_PAGE_CAPABILITY_ID)
    assert descriptor.effects == Effect.EXECUTE
    assert descriptor.required_tier == Tier.CONFIRM


def test_browser_screenshot_has_egress_local_effects() -> None:
    """browser.screenshot is EGRESS_LOCAL, same reasoning as fs.read_file."""
    registry = build_default_registry()

    descriptor = registry.get(BROWSER_SCREENSHOT_CAPABILITY_ID)
    assert descriptor.effects == Effect.EGRESS_LOCAL
    assert descriptor.required_tier == Tier.ALLOW


def test_browser_inspect_dom_has_egress_local_effects() -> None:
    """browser.inspect_dom is EGRESS_LOCAL, same reasoning as browser.screenshot."""
    registry = build_default_registry()

    descriptor = registry.get(BROWSER_INSPECT_DOM_CAPABILITY_ID)
    assert descriptor.effects == Effect.EGRESS_LOCAL
    assert descriptor.required_tier == Tier.ALLOW


def test_browser_close_page_has_execute_effects() -> None:
    """browser.close_page is EXECUTE -- Tier.CONFIRM, same as docker.stop_container."""
    registry = build_default_registry()

    descriptor = registry.get(BROWSER_CLOSE_PAGE_CAPABILITY_ID)
    assert descriptor.effects == Effect.EXECUTE
    assert descriptor.required_tier == Tier.CONFIRM


def test_coding_run_task_has_execute_effects() -> None:
    """coding.run_task is EXECUTE -- Tier.CONFIRM, the outer gate on invoking the coding agent."""
    registry = build_default_registry()

    descriptor = registry.get(CODING_RUN_TASK_CAPABILITY_ID)
    assert descriptor.effects == Effect.EXECUTE
    assert descriptor.required_tier == Tier.CONFIRM


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
