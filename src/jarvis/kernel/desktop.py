"""The composition root for M3's desktop-control capability family.

Mirrors ``jarvis.kernel.music``'s ``authorize_and_run_music_command``
pattern exactly (WP-46's own "registry/orchestration shell" folded
into this work package, its first real user, rather than built empty
and speculative ahead of any capability needing it -- see
``docs/architecture/m3-desktop-control.md``'s package layout proposal
for ``kernel/desktop.py``'s intended role).

Each ``authorize_and_*`` function wires the same
registry/storage/confirmation/orchestrator pieces together, plus
whichever port that specific capability needs, and follows the exact
same enforcement ordering and audit-save guarantee ``kernel/music.py``
established: ``orchestrator.authorize_by_id()`` always runs first, the
real side effect only ever happens inside ``if decision.granted:``,
and ``storage.save(chain)`` runs in a ``finally`` block so a granted
decision is never lost from disk even if the subsequent real-world
action raises.

Terminal's real multi-step flow (WP-52) is expected to need
``application/desktop/`` orchestration beyond this module's simple
authorize-then-call-one-port-method shape -- not built here, since
nothing in this module yet needs it (the same "don't build ahead of a
real need" reasoning WP-46's own consolidation into this work package
already applied once).
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.brave import BraveCliAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.vscode import VsCodeCliAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import (
    DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
    DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID,
    DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID,
    DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID,
    build_default_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.capability import CapabilityId
    from jarvis.domain.policy import Decision
    from jarvis.ports.brave import BravePort
    from jarvis.ports.desktop_window import DesktopWindowPort
    from jarvis.ports.vscode import VsCodePort


class ChatApp(Enum):
    """One of the two consumer chat desktop apps M3 controls -- ordinary control only.

    No vendor names appear in ``domain``/``application``/``ports`` per
    ADR-0021 -- this enum lives in ``kernel``, which is exempt, exactly
    like ``jarvis.kernel.music``'s own ``MusicCommand``.
    """

    CLAUDE = auto()
    CHATGPT = auto()


CHAT_APP_CAPABILITY_IDS: dict[ChatApp, CapabilityId] = {
    ChatApp.CLAUDE: DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID,
    ChatApp.CHATGPT: DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID,
}
"""Maps this module's own dispatch enum to the ids build_default_registry() registers.

Mirrors ``kernel.music``'s ``MUSIC_CAPABILITY_IDS`` precedent exactly.
"""

_CHAT_APP_WINDOW_IDS: dict[ChatApp, str] = {
    ChatApp.CLAUDE: "claude",
    ChatApp.CHATGPT: "chatgpt",
}
"""The app_id each ChatApp is matched against in DesktopWindowPort.find_or_launch.

"claude" is confirmed against a real, installed ``claude-desktop``
binary found during WP-43's spike (``/usr/bin/claude-desktop``).
"chatgpt" is **not** confirmed -- no ChatGPT desktop app was found
installed on the real development machine during that same spike (no
binary, no snap, no ``.desktop`` file). Kept as the best-effort,
most-likely name rather than blocking this capability's existence on
an app this pass could not install to verify; flagged honestly here
rather than silently assumed correct.
"""


def authorize_and_open_brave_url(
    url: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    browser: BravePort | None = None,
) -> Decision:
    """Wire up the stack, authorize opening ``url`` in Brave, and run it only if granted.

    Args:
        url: The URL to navigate to, passed straight through to
            ``browser.open_url`` if granted.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted. Loaded before
            the call and saved again after, unconditionally -- see the
            module docstring's audit-save guarantee.
        browser: The port ``url`` is sent to if granted. Defaults to a
            real ``BraveCliAdapter``. Overridable for tests, exactly as
            ``authorize_and_run_music_command``'s ``media_player`` is.

    Returns:
        The ``Decision`` for this call -- durably appended to the chain
        regardless of outcome. If granted, ``browser`` has already
        received ``open_url(url)`` by the time this returns (barring an
        exception it raised); if denied, it was never touched at all.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
        Tainted({"url": url}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            real_browser = browser if browser is not None else BraveCliAdapter()
            real_browser.open_url(url)
    finally:
        storage.save(chain)

    return decision


def authorize_and_open_vscode_file(
    path: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    editor: VsCodePort | None = None,
) -> Decision:
    """Wire up the stack, authorize opening ``path`` in VS Code, and run it only if granted.

    Args:
        path: The file path to open, passed straight through to
            ``editor.open_file`` if granted.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted. Loaded before
            the call and saved again after, unconditionally -- see the
            module docstring's audit-save guarantee.
        editor: The port ``path`` is sent to if granted. Defaults to a
            real ``VsCodeCliAdapter``. Overridable for tests, exactly
            as ``authorize_and_open_brave_url``'s ``browser`` is.

    Returns:
        The ``Decision`` for this call -- durably appended to the chain
        regardless of outcome. If granted, ``editor`` has already
        received ``open_file(path)`` by the time this returns (barring
        an exception it raised); if denied, it was never touched at all.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID,
        Tainted({"path": path}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            real_editor = editor if editor is not None else VsCodeCliAdapter()
            real_editor.open_file(path)
    finally:
        storage.save(chain)

    return decision


# Seven keyword-mostly arguments: matches this module's other authorize_and_*
# functions' shape, plus the two chat-app-specific launch_command/desktop_window
# seams -- not accidental bloat.
def authorize_and_send_text_to_chat_app(  # noqa: PLR0913
    app: ChatApp,
    text: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    desktop_window: DesktopWindowPort,
    launch_command: tuple[str, ...] | None = None,
) -> Decision:
    """Wire up the stack, authorize sending ``text`` to ``app``, and run it only if granted.

    Ordinary control only, per ADR-0045: finds or launches ``app``,
    focuses it, and types ``text`` into whatever currently has input
    focus. **Never calls ``DesktopWindowPort.read_visible_text``** --
    this function's own real code contains no reference to that
    identifier at all, mechanically enforced by
    ``tests/meta/test_no_response_scraping.py`` (an AST scan of this
    whole module, not just this function).

    One deliberate exception to this module's "port parameters default
    to the real adapter" convention: ``desktop_window`` has **no
    default and is a required parameter**, unlike ``browser``/
    ``editor`` above. Importing ``AtspiDesktopWindowAdapter`` directly
    into this module would transitively reach that adapter's lazy
    ``import gi`` calls -- a real edge ``lint-imports`` sees regardless
    of those imports being function-local, not module-level (confirmed
    directly: this was tried first, and ``lint-imports`` genuinely
    failed C6 with the exact chain ``jarvis.kernel.desktop ->
    jarvis.adapters.desktop_window -> gi``). ``jarvis.kernel`` is one
    of C6's protected source modules ("no GLib in the core"), so this
    module cannot import that adapter at all. This mirrors
    ``kernel/voice_loop.py``'s own, already-established precedent for
    exactly the same reason (its ``physical_confirmation`` parameter,
    guarding against ``Gtk4PhysicalConfirmationAdapter``) -- not a new
    pattern invented here. The real default belongs wherever this
    function is eventually wired into a CLI/voice entry point (not yet
    built for M3), which sits above both ``kernel`` and ``adapters`` in
    the C1 layering and is unrestricted by C6.

    Args:
        app: Which of the two consumer chat desktop apps to send
            ``text`` to.
        text: The text to type into the app's currently-focused input
            control, on explicit user command.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted. Loaded before
            the call and saved again after, unconditionally -- see the
            module docstring's audit-save guarantee.
        desktop_window: The port used to find/focus/type. No default --
            see above. A real caller constructs a real
            ``AtspiDesktopWindowAdapter`` itself; tests inject a fake.
        launch_command: Passed through to ``DesktopWindowPort.find_or_
            launch`` if ``app`` isn't already running. No default is
            hardcoded here (unlike Brave/VS Code's fixed CLI binaries):
            a confirmed real launch command exists for the Claude app
            on the real development machine (``claude-desktop``) but
            not for the ChatGPT app (never found installed during
            WP-43's spike) -- deliberately left for the caller to
            supply rather than silently guessed.

    Returns:
        The ``Decision`` for this call -- durably appended to the chain
        regardless of outcome. If granted, ``desktop_window`` has
        already been focused and sent ``text`` by the time this
        returns (barring an exception it raised); if denied, it was
        never touched at all.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        CHAT_APP_CAPABILITY_IDS[app],
        Tainted({"text": text}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            handle = desktop_window.find_or_launch(_CHAT_APP_WINDOW_IDS[app], launch_command)
            desktop_window.focus(handle)
            desktop_window.type_text(handle, text)
    finally:
        storage.save(chain)

    return decision
