"""The single place every capability jarvis knows about is declared.

Before this module, ``kernel/ping.py``, ``kernel/music.py``, and
``kernel/files.py`` each independently constructed their own
:class:`~jarvis.domain.registry.CapabilityRegistry`, hand-building a
:class:`~jarvis.domain.capability.CapabilityDescriptor` inline for
whichever capability that module happened to own. Adding a capability
meant editing kernel wiring code in the module that would use it.
:func:`build_default_registry` replaces that: it is the one function
that registers every known capability, so adding one later means
adding a registration entry here, not touching an ``authorize_*``
function's internals.

Each ``authorize_*`` function (``authorize_ping``,
``authorize_and_run_music_command``, ``authorize_and_read_file``)
calls this function internally to build its registry -- there is no
injectable ``registry`` parameter. This was a deliberate choice, not
an oversight: an injectable parameter would only matter for a
long-lived process reusing one registry across multiple calls, and
nothing today is long-lived -- every CLI invocation is already a
fresh, separate process that calls exactly one ``authorize_*``
function once before exiting (see ``kernel/ping.py``'s own docstring).
Building a fresh registry per call is cheap (a handful of dataclass
constructions and dict insertions, dwarfed by the cost of process
startup or an actual D-Bus round-trip) and costs nothing observable.
Adding an injectable parameter later, the moment something actually
needs it, is a non-breaking, purely additive change -- identical in
shape to how ``confirmation``/``media_player``/``file_system`` were
each added as optional parameters when their own work packages needed
them. No test today depends on registry contents, so nothing is lost
by deferring this.

No dynamic discovery from disk, no manifest files, no external plugin
loading -- this module only knows about capabilities hardcoded in this
same source tree. That is real future work, not built speculatively
here.
"""

from __future__ import annotations

from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, Effect
from jarvis.domain.registry import CapabilityRegistry

PING_CAPABILITY_ID = CapabilityId("ping")
MUSIC_PLAY_CAPABILITY_ID = CapabilityId("music.play")
MUSIC_PAUSE_CAPABILITY_ID = CapabilityId("music.pause")
MUSIC_NEXT_CAPABILITY_ID = CapabilityId("music.next")
MUSIC_PREVIOUS_CAPABILITY_ID = CapabilityId("music.previous")
READ_FILE_CAPABILITY_ID = CapabilityId("fs.read_file")
DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID = CapabilityId("desktop.brave_open_url")
DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID = CapabilityId("desktop.vscode_open_file")
DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID = CapabilityId("desktop.claude_app_send_text")
DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID = CapabilityId("desktop.chatgpt_app_send_text")
TERMINAL_RUN_CAPABILITY_ID = CapabilityId("terminal.run")
DOCKER_LIST_CONTAINERS_CAPABILITY_ID = CapabilityId("docker.list_containers")
DOCKER_RUN_CONTAINER_CAPABILITY_ID = CapabilityId("docker.run_container")
DOCKER_STOP_CONTAINER_CAPABILITY_ID = CapabilityId("docker.stop_container")
DOCKER_BUILD_IMAGE_CAPABILITY_ID = CapabilityId("docker.build_image")
GIT_STATUS_CAPABILITY_ID = CapabilityId("git.status")
GIT_CREATE_BRANCH_CAPABILITY_ID = CapabilityId("git.create_branch")
GIT_COMMIT_CAPABILITY_ID = CapabilityId("git.commit")
GIT_PUSH_CAPABILITY_ID = CapabilityId("git.push")
GIT_FORCE_PUSH_CAPABILITY_ID = CapabilityId("git.force_push")
MEMORY_RETRIEVE_CAPABILITY_ID = CapabilityId("memory.retrieve")
MEMORY_PIN_CAPABILITY_ID = CapabilityId("memory.pin")
MEMORY_FORGET_CAPABILITY_ID = CapabilityId("memory.forget")
BROWSER_OPEN_PAGE_CAPABILITY_ID = CapabilityId("browser.open_page")
BROWSER_SCREENSHOT_CAPABILITY_ID = CapabilityId("browser.screenshot")
BROWSER_INSPECT_DOM_CAPABILITY_ID = CapabilityId("browser.inspect_dom")
BROWSER_CLOSE_PAGE_CAPABILITY_ID = CapabilityId("browser.close_page")
CODING_RUN_TASK_CAPABILITY_ID = CapabilityId("coding.run_task")
EMAIL_LIST_MESSAGES_CAPABILITY_ID = CapabilityId("communications.list_email")
EMAIL_READ_MESSAGE_CAPABILITY_ID = CapabilityId("communications.read_email")
CALENDAR_LIST_EVENTS_CAPABILITY_ID = CapabilityId("communications.list_calendar_events")


def build_default_registry() -> CapabilityRegistry:
    """Register every capability jarvis currently knows about, in one place.

    Returns:
        A fresh ``CapabilityRegistry`` with every known capability
        registered. ``CapabilityRegistry.register()`` raises
        ``CapabilityAlreadyRegistered`` on a duplicate id (WP-07), so
        this function completing without raising is itself the proof
        that no two capabilities declared here collide -- exercised
        directly by ``tests/unit/test_capabilities.py``, not left as
        an assumption.
    """
    registry = CapabilityRegistry()

    registry.register(
        CapabilityDescriptor(
            id=PING_CAPABILITY_ID,
            effects=Effect.READ_LOCAL,
            description=(
                "A no-op capability that proves the authorization stack is wired end-to-end."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=MUSIC_PLAY_CAPABILITY_ID,
            effects=Effect.WRITE_LOCAL,
            description="Resume playback on the currently running MPRIS media player.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=MUSIC_PAUSE_CAPABILITY_ID,
            effects=Effect.WRITE_LOCAL,
            description="Pause playback on the currently running MPRIS media player.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=MUSIC_NEXT_CAPABILITY_ID,
            effects=Effect.WRITE_LOCAL,
            description="Skip to the next track on the currently running MPRIS media player.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=MUSIC_PREVIOUS_CAPABILITY_ID,
            effects=Effect.WRITE_LOCAL,
            description=(
                "Go back to the previous track on the currently running MPRIS media player."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=READ_FILE_CAPABILITY_ID,
            effects=Effect.EGRESS_LOCAL,
            description="Read a local file's contents, scoped to the allowed root.",
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
            effects=Effect.EXECUTE,
            description="Launch or focus Brave, navigated to a URL.",
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID,
            effects=Effect.EXECUTE,
            description="Launch or focus VS Code, opened to a file.",
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID,
            effects=Effect.EXECUTE,
            description=(
                "Launch or focus the Claude desktop app and type text into its input box. "
                "Ordinary control only -- never reads the app's response (ADR-0045)."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID,
            effects=Effect.EXECUTE,
            description=(
                "Launch or focus the ChatGPT desktop app and type text into its input box. "
                "Ordinary control only -- never reads the app's response (ADR-0045)."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=TERMINAL_RUN_CAPABILITY_ID,
            effects=Effect.DESTRUCTIVE | Effect.EXECUTE,
            description=(
                "Type a command into a freshly launched, sandboxed terminal emulator. "
                "A deliberate, narrow exception to this project's no-shell principle "
                "(ADR-0046) -- always MANUAL_ONLY, never a standing grant."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=DOCKER_LIST_CONTAINERS_CAPABILITY_ID,
            effects=Effect.READ_LOCAL,
            description="List every Docker container's name, read-only.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=DOCKER_RUN_CONTAINER_CAPABILITY_ID,
            effects=Effect.DESTRUCTIVE | Effect.EXECUTE,
            description=(
                "Run a new detached Docker container from an image. Unbounded host "
                "resource consumption and, depending on mount flags, host file access "
                "-- always MANUAL_ONLY, independent of what runs inside the container."
            ),
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=DOCKER_STOP_CONTAINER_CAPABILITY_ID,
            effects=Effect.EXECUTE,
            description="Stop a running Docker container -- recoverable via docker start.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=DOCKER_BUILD_IMAGE_CAPABILITY_ID,
            effects=Effect.DESTRUCTIVE | Effect.EXECUTE,
            description=(
                "Build a Docker image from a Dockerfile. Runs arbitrary build-time "
                "instructions from that Dockerfile -- always MANUAL_ONLY."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=GIT_STATUS_CAPABILITY_ID,
            effects=Effect.READ_LOCAL,
            description="Show a git repository's working-tree status, read-only.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=GIT_CREATE_BRANCH_CAPABILITY_ID,
            effects=Effect.WRITE_LOCAL,
            description="Create and switch to a new git branch. Cheap and reversible.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=GIT_COMMIT_CAPABILITY_ID,
            effects=Effect.WRITE_LOCAL,
            description=(
                "Commit already-tracked, modified files. Reversible via git reset/--amend "
                "as long as it is never shared."
            ),
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=GIT_PUSH_CAPABILITY_ID,
            effects=Effect.WRITE_LOCAL,
            description="An ordinary fast-forward push to a branch the user already owns.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=GIT_FORCE_PUSH_CAPABILITY_ID,
            effects=Effect.DESTRUCTIVE | Effect.IRREVERSIBLE,
            description=(
                "A force-push, which can discard a remote's history in a way nothing "
                "else in this registry can undo -- always MANUAL_ONLY, its own capability "
                "id rather than a flag on git.push."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=MEMORY_RETRIEVE_CAPABILITY_ID,
            effects=Effect.READ_LOCAL,
            description="Search previously-memorized content. The bare act of querying only.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=MEMORY_PIN_CAPABILITY_ID,
            effects=Effect.WRITE_LOCAL,
            description=(
                "Mark a memorized record as pinned -- retained indefinitely, "
                "never expires automatically (ADR-0051)."
            ),
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=MEMORY_FORGET_CAPABILITY_ID,
            effects=Effect.DESTRUCTIVE | Effect.IRREVERSIBLE,
            description=(
                "Permanently delete a memorized record by identifier. No undo -- "
                "once gone, the same 'no built-in recovery' finality as "
                "git.force_push -- always MANUAL_ONLY."
            ),
        )
    )
    # memory.write (application/memory/writer.py's MEMORY_WRITE_CAPABILITY_ID) is
    # deliberately NOT registered here -- see kernel/memory.py's own module
    # docstring for why: its real Effect varies per invocation with the
    # value's own classification (ADR-0049), the same reason
    # jarvis.application.reasoning.router.ModelRouter's capability is never
    # registered here either.

    registry.register(
        CapabilityDescriptor(
            id=BROWSER_OPEN_PAGE_CAPABILITY_ID,
            effects=Effect.EXECUTE,
            description=(
                "Launch a dedicated, headless, CDP-controlled browser page, "
                "navigated to a URL. Same tier as desktop.brave_open_url/"
                "desktop.vscode_open_file (M5's own deep counterpart to M3's "
                "shallow app-launch capabilities, m3-desktop-control.md's own "
                "'Relationship to M5' split)."
            ),
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=BROWSER_SCREENSHOT_CAPABILITY_ID,
            effects=Effect.EGRESS_LOCAL,
            description=(
                "Capture a real screenshot of an already-open browser page's "
                "current content. EGRESS_LOCAL, not READ_LOCAL, matching "
                "fs.read_file's own reasoning: this extracts real page content "
                "out to the caller, which is an egress even though it never "
                "leaves the machine."
            ),
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=BROWSER_INSPECT_DOM_CAPABILITY_ID,
            effects=Effect.EGRESS_LOCAL,
            description=(
                "Query an already-open browser page's live DOM for the outer "
                "HTML of the first element matching a CSS selector. Same "
                "EGRESS_LOCAL reasoning as browser.screenshot."
            ),
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=BROWSER_CLOSE_PAGE_CAPABILITY_ID,
            effects=Effect.EXECUTE,
            description=(
                "Terminate a browser page's real subprocess and remove its "
                "temporary profile. Same EXECUTE tier as docker.stop_container "
                "-- stopping something already started, real cleanup, not a "
                "new resource."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=CODING_RUN_TASK_CAPABILITY_ID,
            effects=Effect.EXECUTE,
            description=(
                "Run an autonomous coding-agent task (WP-71's coding-loop "
                "wrapper) against a real target repository. The outer gate "
                "on invoking the coding agent at all -- Effect.EXECUTE, same "
                "tier as docker.stop_container/browser.open_page, an "
                "ordinary 'ask first' action. Each real write the task may "
                "eventually make is separately, individually authorized "
                "through Effect.CODE_WRITE/Effect.PROTECTED_PATH_WRITE "
                "(ADR-0056) inside run_coding_task itself, unaffected by "
                "this outer gate's own tier."
            ),
        )
    )

    registry.register(
        CapabilityDescriptor(
            id=EMAIL_LIST_MESSAGES_CAPABILITY_ID,
            effects=Effect.EGRESS_LOCAL,
            description=(
                "List real message summaries from a real IMAP mailbox folder. "
                "EGRESS_LOCAL, not READ_LOCAL, matching fs.read_file's/"
                "browser.screenshot's own reasoning: extracting real content "
                "out to the caller is an egress even though it never leaves "
                "the machine (m6a-communications.md)."
            ),
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=EMAIL_READ_MESSAGE_CAPABILITY_ID,
            effects=Effect.EGRESS_LOCAL,
            description="Read one real message's full content from a real IMAP mailbox.",
        )
    )
    registry.register(
        CapabilityDescriptor(
            id=CALENDAR_LIST_EVENTS_CAPABILITY_ID,
            effects=Effect.EGRESS_LOCAL,
            description="List real events in a real date range from a real CalDAV calendar.",
        )
    )
    # communications.send_email/communications.create_calendar_event are
    # deliberately NOT registered here -- send_message/create_event are not
    # implemented by any real adapter yet (blocked on ADR-0057, Proposed,
    # not Accepted). Once implemented, their real Effect would vary per
    # invocation with the content's own classification anyway (the same
    # reason memory.write/job_assistance.draft are never registered here
    # either) -- see ports/email.py's/ports/calendar.py's own module
    # docstrings.

    return registry
