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

Terminal's own composition function, ``authorize_and_run_terminal_command``,
delegates its real multi-step flow to
``jarvis.application.desktop.run_in_sandboxed_terminal`` rather than
inlining it here, for a second, real reason beyond "genuinely more
complex than one port call": that function's own body is the one place
``DesktopWindowPort.read_visible_text`` is legitimately called, and
this module must never reference that identifier at all (ADR-0045,
``tests/meta/test_no_response_scraping.py``, an AST scan of this whole
file). Calling a differently-named function that itself calls
``read_visible_text`` satisfies that guarantee; importing the
identifier directly into this module would not.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.brave import BraveCliAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.adapters.vscode import VsCodeCliAdapter
from jarvis.application.desktop import run_in_sandboxed_terminal
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.capabilities import (
    DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
    DESKTOP_CHATGPT_APP_SEND_TEXT_CAPABILITY_ID,
    DESKTOP_CLAUDE_APP_SEND_TEXT_CAPABILITY_ID,
    DESKTOP_VSCODE_OPEN_FILE_CAPABILITY_ID,
    TERMINAL_RUN_CAPABILITY_ID,
    build_default_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.capability import CapabilityId
    from jarvis.domain.policy import Decision
    from jarvis.ports.brave import BravePort
    from jarvis.ports.desktop_window import DesktopWindowPort
    from jarvis.ports.sandbox import SandboxPort
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


@dataclass(frozen=True)
class TerminalRunOutcome:
    """The result of one authorize_and_run_terminal_command() call.

    Mirrors ``kernel.files``'s ``FileReadOutcome`` precedent exactly:
    a capability whose real value is data it produced, not just a
    grant/deny, returns both the ``Decision`` and that data together.

    Attributes:
        decision: The Decision for this call -- durably appended to
            the chain regardless of outcome.
        output: The sandboxed terminal's visible output after the
            command ran, tagged ``Trust.UNTRUSTED_EXTERNAL`` per
            ADR-0011 (this process did not generate it and must not
            implicitly trust it, regardless of how trustworthy the
            command itself seemed). ``None`` if denied, or if granted
            but the terminal emulator's output could not be read back
            (best-effort, per ``DesktopWindowPort.read_visible_text``'s
            own contract) -- these two ``None`` cases are not
            distinguished by this type; ``decision.granted`` tells them
            apart.
    """

    decision: Decision
    output: Tainted[str] | None


# Nine keyword-mostly arguments: matches this module's other authorize_and_*
# functions' shape, plus the sandbox/bind_paths seams this, the highest-risk
# capability in this milestone, genuinely needs -- not accidental bloat.
def authorize_and_run_terminal_command(  # noqa: PLR0913
    command_text: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    sandbox: SandboxPort,
    desktop_window: DesktopWindowPort,
    bind_paths: tuple[Path, ...] = (),
) -> TerminalRunOutcome:
    """Wire up the stack, authorize ``command_text``, and run it in a sandboxed terminal if granted.

    ``terminal.run`` floors ``Tier.MANUAL_ONLY`` unconditionally
    (``Effect.DESTRUCTIVE | Effect.EXECUTE``) -- unlike every other
    function in this module, ``remote_confirmation_available`` alone
    can never grant this call; only ``physical_confirmation_available``
    can (ADR-0013, ``domain/policy.py``'s own ``evaluate()``).

    Both ``sandbox`` and ``desktop_window`` are **required, with no
    default** -- unlike ``browser``/``editor`` above. Partly the same
    GLib/C6 reason ``desktop_window`` already has no default on
    ``authorize_and_send_text_to_chat_app`` (importing
    ``AtspiDesktopWindowAdapter`` into ``jarvis.kernel`` would break
    C6), and partly a deliberate, proportional choice for this
    milestone's single riskiest capability: no implicit default
    construction at all for the one capability where getting the
    sandbox wrong has the highest real consequence, requiring an
    explicit, visible wiring decision at every call site instead.

    Args:
        command_text: The text typed into the sandboxed terminal's
            shell, passed straight through to
            ``run_in_sandboxed_terminal`` if granted.
        physical_confirmation_available: Whether a human is physically
            present. The only channel that can grant this call.
        remote_confirmation_available: Threaded through for interface
            consistency with every other function here, but cannot by
            itself grant a MANUAL_ONLY capability -- see above.
        chain_path: Where the audit chain is persisted. Loaded before
            the call and saved again after, unconditionally -- see the
            module docstring's audit-save guarantee.
        sandbox: Launches the real, contained terminal emulator
            process. No default -- see above.
        desktop_window: Finds/focuses/types into/reads the launched
            terminal's window. No default -- see above.
        bind_paths: Host directories the sandboxed terminal can
            access. Empty by default -- a fully isolated shell with
            nothing granted, per ``SandboxPort``'s own default
            (ADR-0044).

    Returns:
        A ``TerminalRunOutcome`` -- see its own docstring.
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
        TERMINAL_RUN_CAPABILITY_ID,
        Tainted({"command_text": command_text}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    output: Tainted[str] | None = None
    try:
        if decision.granted:
            raw_output = run_in_sandboxed_terminal(
                command_text,
                sandbox=sandbox,
                desktop_window=desktop_window,
                bind_paths=bind_paths,
            )
            if raw_output is not None:
                output = Tainted.external(
                    raw_output,
                    source="sandboxed terminal",
                    classification=Classification.SENSITIVE,
                )
    finally:
        storage.save(chain)

    return TerminalRunOutcome(decision=decision, output=output)
