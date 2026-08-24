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

    return registry
