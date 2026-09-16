"""The first, real, built-in skills: named groupings over already-existing capabilities.

Mirrors `kernel/capabilities.py::build_default_registry()` exactly, on
purpose: one function, `build_default_skill_registry()`, registers
every skill JARVIS currently knows about, in one place. Each skill is
pure `SkillDescriptor` metadata (`jarvis.domain.skill`) -- it groups
real, already-registered `CapabilityId` values under one discoverable
name; it never introduces a new capability, a new `Effect`/`Tier`, or
any way to invoke anything outside the exact, unmodified authorization
choke point those capabilities already go through.

**Deliberately scoped to WP-173's own six named domains, not all 44
registered capabilities**: filesystem, tasks, memory, calendar, email,
browser -- the domains the work package names as "already implemented
and stable." Desktop control, coding, job search/application, and
audit history are real, equally-stable domains too, but adding a skill
for every registered capability in one pass would be scope creep this
work package's own instruction explicitly warns against ("do not
create new capabilities merely to make the skills look complete" --
padding out unrelated domains here would be the descriptive-metadata
equivalent of that). Extending coverage later is purely additive, one
more `registry.register(SkillDescriptor(...))` call, matching how
`build_default_registry()` itself has grown one capability at a time.

**Tasks, a real, honest choice explained**: there is no statically-
registered `task.*` `CapabilityId` anywhere in this codebase --
`kernel/tasks.py`'s own lifecycle is built entirely on
`memory.write`/`memory.update` (both dynamic-effect, deliberately never
statically registered, ADR-0049/ADR-0063) plus `memory.get`/
`memory.retrieve` (registered) and `planning.run_plan` (registered,
the real outer gate `authorize_and_run_plan` sits behind). The
"Tasks" skill below names exactly the real, registered capabilities a
task workflow is actually built from -- `memory.get`/`memory.retrieve`/
`planning.run_plan` -- rather than inventing a `task.create`/
`task.run` capability id that does not exist merely to make this
skill look more direct; doing so would violate the hard rule against
introducing a new `CapabilityId` without a real architectural need,
and would also register something `validate_skill_registry` could
never actually confirm is real.

**Calendar/email are read-only skills**, for the identical, real
reason: `communications.send_email`/`communications.create_calendar_event`
are dynamic-effect capabilities (their own real `Effect` varies with
the outgoing content's classification, ADR-0057/ADR-0059) and are
deliberately never statically registered either -- see
`kernel/communications.py`'s own module docstring. A skill can only
ever name what the real `CapabilityRegistry` actually contains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.domain.skill import SkillDescriptor, SkillId
from jarvis.domain.skill_registry import SkillRegistry, validate_skill_registry
from jarvis.kernel.capabilities import (
    BROWSER_CLOSE_PAGE_CAPABILITY_ID,
    BROWSER_INSPECT_DOM_CAPABILITY_ID,
    BROWSER_OPEN_PAGE_CAPABILITY_ID,
    BROWSER_SCREENSHOT_CAPABILITY_ID,
    CALENDAR_LIST_EVENTS_CAPABILITY_ID,
    DELETE_FILE_CAPABILITY_ID,
    EMAIL_LIST_MESSAGES_CAPABILITY_ID,
    EMAIL_READ_MESSAGE_CAPABILITY_ID,
    FIND_FILES_CAPABILITY_ID,
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

if TYPE_CHECKING:
    from jarvis.domain.registry import CapabilityRegistry

FILESYSTEM_SKILL_ID = SkillId("filesystem")
TASKS_SKILL_ID = SkillId("tasks")
MEMORY_SKILL_ID = SkillId("memory")
CALENDAR_SKILL_ID = SkillId("calendar")
EMAIL_SKILL_ID = SkillId("email")
BROWSER_SKILL_ID = SkillId("browser")


def build_default_skill_registry(capabilities: CapabilityRegistry | None = None) -> SkillRegistry:
    """Register every built-in skill jarvis currently knows about, in one place.

    Args:
        capabilities: The real capability registry to validate every
            skill's ``capability_ids`` against. Defaults to a fresh
            ``build_default_registry()`` -- overridable only so tests
            can prove ``validate_skill_registry`` actually fires
            against a deliberately incomplete registry.

    Returns:
        A fresh ``SkillRegistry`` with every built-in skill registered
        and validated against real, registered capabilities.

    Raises:
        jarvis.domain.errors.SkillReferencesUnknownCapability: If any
            skill below names a capability id that ``capabilities``
            does not contain -- this function completing without
            raising is itself the proof that every skill here only
            ever points at real, existing capabilities, exercised
            directly by ``tests/unit/test_skills.py``, not left as an
            assumption (mirrors ``build_default_registry()``'s own,
            identical self-proving reasoning for duplicate ids).
    """
    registry = SkillRegistry()

    registry.register(
        SkillDescriptor(
            id=FILESYSTEM_SKILL_ID,
            name="Filesystem",
            description=(
                "Read, list, search, move, and delete local files, all scoped to an allowed root."
            ),
            domain="filesystem",
            capability_ids=(
                READ_FILE_CAPABILITY_ID,
                LIST_DIR_CAPABILITY_ID,
                MOVE_FILE_CAPABILITY_ID,
                DELETE_FILE_CAPABILITY_ID,
                FIND_FILES_CAPABILITY_ID,
                SEARCH_CONTENT_CAPABILITY_ID,
                RECENT_FILES_CAPABILITY_ID,
            ),
            instructions=(
                "Prefer fs.read_file for a single, already-known path; fs.find/"
                "fs.search_content for locating files by name or content; fs.move_file/"
                "fs.delete_file are destructive-adjacent writes and always require "
                "confirmation (fs.delete_file always requires physical, in-person "
                "confirmation and can never be approved remotely)."
            ),
            tags=("files", "local", "search"),
        )
    )

    registry.register(
        SkillDescriptor(
            id=TASKS_SKILL_ID,
            name="Tasks",
            description=(
                "Look up and list durable, persisted tasks, and run a planned, "
                "multi-step goal one authorized step at a time."
            ),
            domain="tasks",
            capability_ids=(
                MEMORY_GET_CAPABILITY_ID,
                MEMORY_RETRIEVE_CAPABILITY_ID,
                PLANNING_RUN_PLAN_CAPABILITY_ID,
            ),
            instructions=(
                "Task creation/status/list/cancel/retry/schedule are real, dedicated "
                "'jarvis task ...' CLI subcommands and typed 'task status <id>'/'list "
                "tasks' router commands, built on top of memory.get/memory.retrieve "
                "for lookup and planning.run_plan for execution -- there is no "
                "separate, standalone task.* capability id; every real plan step "
                "planning.run_plan executes is still separately, individually "
                "authorized (ADR-0062, no batch pre-approval)."
            ),
            tags=("planning", "background", "goals"),
        )
    )

    registry.register(
        SkillDescriptor(
            id=MEMORY_SKILL_ID,
            name="Memory",
            description=(
                "Search, look up, pin, forget, back up, and restore previously memorized content."
            ),
            domain="memory",
            capability_ids=(
                MEMORY_RETRIEVE_CAPABILITY_ID,
                MEMORY_GET_CAPABILITY_ID,
                MEMORY_PIN_CAPABILITY_ID,
                MEMORY_FORGET_CAPABILITY_ID,
                MEMORY_BACKUP_CAPABILITY_ID,
                MEMORY_RESTORE_CAPABILITY_ID,
                MEMORY_WIPE_CAPABILITY_ID,
            ),
            instructions=(
                "memory.write itself is a dynamic-effect capability (its real Effect "
                "depends on the value's own classification, ADR-0049) and is "
                "deliberately not listed here since it is never statically "
                "registered -- writing new memories goes through 'jarvis memory "
                "write'/'remember <text>' directly, unaffected by this skill's own "
                "discoverability metadata. memory.forget/memory.restore/memory.wipe "
                "are all MANUAL_ONLY, no undo."
            ),
            tags=("recall", "storage", "retention"),
        )
    )

    registry.register(
        SkillDescriptor(
            id=CALENDAR_SKILL_ID,
            name="Calendar",
            description="List real events in a date range from a configured CalDAV calendar.",
            domain="calendar",
            capability_ids=(CALENDAR_LIST_EVENTS_CAPABILITY_ID,),
            instructions=(
                "Read-only. communications.create_calendar_event exists ('jarvis "
                "create-calendar-event') but is a dynamic-effect capability, never "
                "statically registered, and is always floored at Tier.MANUAL_ONLY "
                "(ADR-0059) -- it is deliberately not listed here."
            ),
            tags=("events", "schedule"),
        )
    )

    registry.register(
        SkillDescriptor(
            id=EMAIL_SKILL_ID,
            name="Email",
            description="List and read messages from a configured IMAP mailbox.",
            domain="email",
            capability_ids=(EMAIL_LIST_MESSAGES_CAPABILITY_ID, EMAIL_READ_MESSAGE_CAPABILITY_ID),
            instructions=(
                "Read-only. communications.send_email exists ('jarvis send-email') but "
                "is a dynamic-effect capability, never statically registered, and is "
                "always floored at Tier.MANUAL_ONLY (ADR-0059) -- it is deliberately "
                "not listed here."
            ),
            tags=("messages", "inbox"),
        )
    )

    registry.register(
        SkillDescriptor(
            id=BROWSER_SKILL_ID,
            name="Browser",
            description=(
                "Open a real, headless, CDP-controlled browser page and capture a "
                "screenshot or query its live DOM."
            ),
            domain="browser",
            capability_ids=(
                BROWSER_OPEN_PAGE_CAPABILITY_ID,
                BROWSER_SCREENSHOT_CAPABILITY_ID,
                BROWSER_INSPECT_DOM_CAPABILITY_ID,
                BROWSER_CLOSE_PAGE_CAPABILITY_ID,
            ),
            instructions=(
                "Each real invocation ('jarvis browser open/screenshot/inspect-dom/"
                "close') needs the prior call's own printed PageHandle fields -- there "
                "is no shared, in-memory browser state across separate CLI "
                "invocations."
            ),
            tags=("web", "automation", "screenshot"),
        )
    )

    real_capabilities = capabilities if capabilities is not None else build_default_registry()
    validate_skill_registry(registry, real_capabilities)
    return registry
