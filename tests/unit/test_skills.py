"""Unit tests for jarvis.kernel.skills.build_default_skill_registry."""

from __future__ import annotations

import pytest

from jarvis.domain.errors import SkillReferencesUnknownCapability
from jarvis.domain.registry import CapabilityRegistry
from jarvis.kernel.capabilities import (
    BROWSER_CLOSE_PAGE_CAPABILITY_ID,
    BROWSER_INSPECT_DOM_CAPABILITY_ID,
    BROWSER_OPEN_PAGE_CAPABILITY_ID,
    BROWSER_SCREENSHOT_CAPABILITY_ID,
    CALENDAR_LIST_EVENTS_CAPABILITY_ID,
    CODING_RUN_TASK_CAPABILITY_ID,
    DELETE_FILE_CAPABILITY_ID,
    EMAIL_LIST_MESSAGES_CAPABILITY_ID,
    EMAIL_READ_MESSAGE_CAPABILITY_ID,
    FIND_FILES_CAPABILITY_ID,
    GIT_STATUS_CAPABILITY_ID,
    LIST_DIR_CAPABILITY_ID,
    MEMORY_BACKUP_CAPABILITY_ID,
    MEMORY_FORGET_CAPABILITY_ID,
    MEMORY_GET_CAPABILITY_ID,
    MEMORY_PIN_CAPABILITY_ID,
    MEMORY_RESTORE_CAPABILITY_ID,
    MEMORY_RETRIEVE_CAPABILITY_ID,
    MEMORY_WIPE_CAPABILITY_ID,
    MOVE_FILE_CAPABILITY_ID,
    PLANNING_RUN_PLAN_CAPABILITY_ID,
    READ_FILE_CAPABILITY_ID,
    RECENT_FILES_CAPABILITY_ID,
    SEARCH_CONTENT_CAPABILITY_ID,
    build_default_registry,
)
from jarvis.kernel.skills import (
    BROWSER_SKILL_ID,
    CALENDAR_SKILL_ID,
    CODING_SKILL_ID,
    EMAIL_SKILL_ID,
    FILESYSTEM_SKILL_ID,
    MEMORY_SKILL_ID,
    RESEARCH_SKILL_ID,
    TASKS_SKILL_ID,
    build_default_skill_registry,
)

_EXPECTED_SKILL_COUNT = 8


def test_build_default_skill_registry_does_not_raise() -> None:
    """build_default_skill_registry() completes without raising.

    The real proof this is looking for: every skill's capability_ids
    validate cleanly against a real, fully-built capability registry
    (SkillReferencesUnknownCapability would fire otherwise), and no
    two skills declared here share an id (SkillAlreadyRegistered would
    fire otherwise).
    """
    build_default_skill_registry()


def test_build_default_skill_registry_registers_exactly_the_expected_ids() -> None:
    """The skill registry contains exactly the six named built-in skills, no more, no fewer."""
    registry = build_default_skill_registry()

    ids = {descriptor.id for descriptor in registry}

    assert ids == {
        FILESYSTEM_SKILL_ID,
        TASKS_SKILL_ID,
        MEMORY_SKILL_ID,
        CALENDAR_SKILL_ID,
        EMAIL_SKILL_ID,
        BROWSER_SKILL_ID,
        RESEARCH_SKILL_ID,
        CODING_SKILL_ID,
    }
    assert len(registry) == _EXPECTED_SKILL_COUNT


def test_filesystem_skill_groups_the_real_fs_capabilities() -> None:
    """The Filesystem skill names exactly the seven real fs.* capability ids."""
    registry = build_default_skill_registry()
    skill = registry.get(FILESYSTEM_SKILL_ID)

    assert skill.domain == "filesystem"
    assert set(skill.capability_ids) == {
        READ_FILE_CAPABILITY_ID,
        LIST_DIR_CAPABILITY_ID,
        MOVE_FILE_CAPABILITY_ID,
        DELETE_FILE_CAPABILITY_ID,
        FIND_FILES_CAPABILITY_ID,
        SEARCH_CONTENT_CAPABILITY_ID,
        RECENT_FILES_CAPABILITY_ID,
    }


def test_tasks_skill_groups_the_real_underlying_capabilities() -> None:
    """The Tasks skill names memory.get/memory.retrieve/planning.run_plan, not a fake task.* id."""
    registry = build_default_skill_registry()
    skill = registry.get(TASKS_SKILL_ID)

    assert skill.domain == "tasks"
    assert set(skill.capability_ids) == {
        MEMORY_GET_CAPABILITY_ID,
        MEMORY_RETRIEVE_CAPABILITY_ID,
        PLANNING_RUN_PLAN_CAPABILITY_ID,
    }


def test_memory_skill_groups_the_real_memory_capabilities() -> None:
    """The Memory skill names the real, statically-registered memory.* capabilities."""
    registry = build_default_skill_registry()
    skill = registry.get(MEMORY_SKILL_ID)

    assert skill.domain == "memory"
    assert set(skill.capability_ids) == {
        MEMORY_RETRIEVE_CAPABILITY_ID,
        MEMORY_GET_CAPABILITY_ID,
        MEMORY_PIN_CAPABILITY_ID,
        MEMORY_FORGET_CAPABILITY_ID,
        MEMORY_BACKUP_CAPABILITY_ID,
        MEMORY_RESTORE_CAPABILITY_ID,
        MEMORY_WIPE_CAPABILITY_ID,
    }


def test_calendar_skill_is_read_only() -> None:
    """The Calendar skill names only communications.list_calendar_events -- no write capability."""
    registry = build_default_skill_registry()
    skill = registry.get(CALENDAR_SKILL_ID)

    assert skill.domain == "calendar"
    assert skill.capability_ids == (CALENDAR_LIST_EVENTS_CAPABILITY_ID,)


def test_email_skill_is_read_only() -> None:
    """The Email skill names only the two real read capabilities -- no send capability."""
    registry = build_default_skill_registry()
    skill = registry.get(EMAIL_SKILL_ID)

    assert skill.domain == "email"
    assert set(skill.capability_ids) == {
        EMAIL_LIST_MESSAGES_CAPABILITY_ID,
        EMAIL_READ_MESSAGE_CAPABILITY_ID,
    }


def test_browser_skill_groups_the_real_browser_capabilities() -> None:
    """The Browser skill names the four real browser.* capabilities."""
    registry = build_default_skill_registry()
    skill = registry.get(BROWSER_SKILL_ID)

    assert skill.domain == "browser"
    assert set(skill.capability_ids) == {
        BROWSER_OPEN_PAGE_CAPABILITY_ID,
        BROWSER_SCREENSHOT_CAPABILITY_ID,
        BROWSER_INSPECT_DOM_CAPABILITY_ID,
        BROWSER_CLOSE_PAGE_CAPABILITY_ID,
    }


def test_research_skill_groups_real_capabilities_across_filesystem_browser_memory_planning() -> (
    None
):
    """The Research skill (WP-178) is real, cross-cutting -- not job_search.*, never invented."""
    registry = build_default_skill_registry()
    skill = registry.get(RESEARCH_SKILL_ID)

    assert skill.domain == "research"
    assert set(skill.capability_ids) == {
        FIND_FILES_CAPABILITY_ID,
        SEARCH_CONTENT_CAPABILITY_ID,
        RECENT_FILES_CAPABILITY_ID,
        READ_FILE_CAPABILITY_ID,
        BROWSER_OPEN_PAGE_CAPABILITY_ID,
        BROWSER_INSPECT_DOM_CAPABILITY_ID,
        BROWSER_SCREENSHOT_CAPABILITY_ID,
        BROWSER_CLOSE_PAGE_CAPABILITY_ID,
        MEMORY_RETRIEVE_CAPABILITY_ID,
        MEMORY_GET_CAPABILITY_ID,
        PLANNING_RUN_PLAN_CAPABILITY_ID,
    }
    assert skill.instructions is not None


def test_coding_skill_groups_the_real_dev_capabilities_and_excludes_git_writes() -> None:
    """The Coding skill (WP-179) is inspection/search/read/run-task only -- no git writes."""
    registry = build_default_skill_registry()
    skill = registry.get(CODING_SKILL_ID)

    assert skill.domain == "coding"
    assert set(skill.capability_ids) == {
        GIT_STATUS_CAPABILITY_ID,
        READ_FILE_CAPABILITY_ID,
        FIND_FILES_CAPABILITY_ID,
        SEARCH_CONTENT_CAPABILITY_ID,
        CODING_RUN_TASK_CAPABILITY_ID,
    }
    assert skill.instructions is not None


def test_every_skill_capability_id_is_registered_in_the_real_capability_registry() -> None:
    """Direct, redundant proof that every skill's capability_ids is a subset of what's real."""
    skills = build_default_skill_registry()
    capabilities = build_default_registry()

    for skill in skills:
        for capability_id in skill.capability_ids:
            assert capability_id in capabilities


def test_build_default_skill_registry_raises_when_a_capability_is_actually_missing() -> None:
    """validate_skill_registry genuinely fires -- proven against a deliberately empty registry.

    Confirms this is a real, load-bearing check, not dead code: passing
    an incomplete capability registry causes construction to fail
    loudly rather than silently registering a skill pointing at
    nothing real.
    """
    with pytest.raises(SkillReferencesUnknownCapability):
        build_default_skill_registry(CapabilityRegistry())
