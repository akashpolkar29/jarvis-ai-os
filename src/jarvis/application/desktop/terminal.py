"""Terminal orchestration: launch a sandboxed terminal, type a command, best-effort read output.

:func:`run_in_sandboxed_terminal` is the real, multi-step flow
ADR-0046/ADR-0047 require: :meth:`~jarvis.ports.sandbox.SandboxPort.launch`
starts a real, contained terminal emulator process -- never keystroke
injection into an arbitrary, already-running terminal window;
:meth:`~jarvis.ports.desktop_window.DesktopWindowPort.find_or_launch`
locates the window that process just created; the real-time indicator
fires and is precondition-checked; :class:`~jarvis.ports.synthetic_input.SyntheticInputPort`
types the command into it, per-character, focus-verified before every
keystroke; ``read_visible_text()`` best-effort captures the result
afterward, tagged ``Trust.UNTRUSTED_EXTERNAL`` by ``kernel.desktop`` per
ADR-0011.

**ADR-0047 replaces ``DesktopWindowPort.type_text()`` as this
function's typing mechanism, for Terminal specifically** -- VTE (the
widget ``gnome-terminal-server`` uses) never exposed AT-SPI2's
``EditableText`` interface ``type_text()`` needs, a real, structural
gap ADR-0047's own Context section documents in full. ``type_text()``'s
own contract is unchanged for every other caller (the two consumer
chat desktop apps, ``kernel.desktop``'s
``authorize_and_send_text_to_chat_app``) -- this module simply stops
being one of its callers.

**Structural guarantee (ADR-0046's acceptance criterion #4), not
merely documented:** this function's own body calls
``sandbox.launch()`` as its very first statement, strictly before any
``SyntheticInputPort.send_keysym()`` call -- there is no branch, no
early return, no alternate path that reaches ``send_keysym()`` without
first executing ``launch()``. ``tests/meta/test_terminal_sandboxed_launch_only.py``
verifies this AST-structurally (the ``launch`` call's statement index
precedes ``send_keysym``'s in this function's flat body), and
separately verifies :func:`_find_the_sandboxed_terminal_window` never
passes a ``launch_command`` to ``DesktopWindowPort.find_or_launch`` --
that port's own launch path (``adapters/desktop_window.py``'s
``_launch_subprocess``) is a plain, **unsandboxed** subprocess call,
and reaching it from this module even as a retry fallback would
silently defeat ADR-0046's whole guarantee. Window discovery here
polls by retrying a bare ``find_or_launch(app_id)`` (no launch
argument at all) instead.

**Fail-closed, never fire blind (ADR-0047):** the real-time indicator's
hard-abort precondition (window visible/showing, announcement spoken)
is checked before ``SyntheticInputPort.start_session()`` is even
called -- no keystroke is ever sent without both. Focus is re-verified
before every single character, and every remaining character is
aborted the instant a check fails -- this function never partially
recovers from a failed verification.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from jarvis.ports.desktop_window import WindowNotFoundError
from jarvis.ports.secret import SecretNotFoundError
from jarvis.ports.synthetic_input import SyntheticInputUnavailableError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from jarvis.domain.audio import AudioStream
    from jarvis.domain.desktop import WindowHandle
    from jarvis.ports.desktop_window import DesktopWindowPort
    from jarvis.ports.sandbox import SandboxPort
    from jarvis.ports.secret import SecretPort
    from jarvis.ports.synthetic_input import SyntheticInputPort
    from jarvis.ports.tts import TtsPort

    SleepFn = Callable[[float], None]
    EnsureProfileFn = Callable[[], str]
    PlayFn = Callable[[AudioStream], None]

_TERMINAL_APP_ID = "gnome-terminal"
"""Confirmed a real, native (non-snap) binary during WP-43's spike
(/usr/bin/gnome-terminal) -- chosen over Brave/VS Code's own
snap-confined AT-SPI2 access issues, per ADR-0046's own reasoning."""

_TERMINAL_LAUNCH_COMMAND: tuple[str, ...] = ("gnome-terminal",)

_WINDOW_DISCOVERY_ATTEMPTS = 10
_WINDOW_DISCOVERY_INTERVAL_SECONDS = 0.5

_TYPING_ANNOUNCEMENT = "Typing into the sandboxed terminal now."
"""ADR-0047's real-time indicator, audible half -- exact phrasing not
load-bearing per that ADR, kept here as the one real string used."""

_RESTORE_TOKEN_REFERENCE = "desktop.synthetic_input.restore_token"  # noqa: S105
"""ADR-0047's own named SecretPort *reference* string (not a secret
value itself) for the RemoteDesktop portal's persisted restore_token."""

_KEYSYM_RETURN = 0xFF0D
_KEYSYM_TAB = 0xFF09
_LATIN1_KEYSYM_MIN = 0x20
_LATIN1_KEYSYM_MAX = 0xFF
_UNICODE_KEYSYM_OFFSET = 0x01000000


def _char_to_keysym(character: str) -> int:
    r"""Map one character to its X11 keysym, per ADR-0047's own researched convention.

    Pure and I/O-free. ``\n``/``\t`` map to their real, named X11
    keysyms (``Return``/``Tab``) -- terminals interpret these specially,
    and neither has a meaningful keysym at its own raw codepoint.
    Printable Latin-1 (0x20-0xFF) keysyms equal their codepoint
    directly, a real, standard X11 fact, not this module's own
    invention. Everything else uses the X11 Unicode keysym convention
    (``0x01000000 + codepoint``), per ADR-0047's own Context section.
    """
    if character == "\n":
        return _KEYSYM_RETURN
    if character == "\t":
        return _KEYSYM_TAB
    codepoint = ord(character)
    if _LATIN1_KEYSYM_MIN <= codepoint <= _LATIN1_KEYSYM_MAX:
        return codepoint
    return _UNICODE_KEYSYM_OFFSET + codepoint


def _find_the_sandboxed_terminal_window(
    desktop_window: DesktopWindowPort, sleep_fn: SleepFn
) -> WindowHandle:
    """Poll for the just-launched terminal's window. Never launches anything itself.

    See the module docstring's structural-guarantee note: deliberately
    never passes ``launch_command`` to ``find_or_launch``, on the
    initial attempt or any retry, so this module structurally cannot
    reach ``DesktopWindowPort``'s own (unsandboxed) launch path.

    Raises:
        WindowNotFoundError: If the window never appears within
            ``_WINDOW_DISCOVERY_ATTEMPTS`` polls.
    """
    last_error: WindowNotFoundError | None = None
    for _ in range(_WINDOW_DISCOVERY_ATTEMPTS):
        try:
            return desktop_window.find_or_launch(_TERMINAL_APP_ID)
        except WindowNotFoundError as exc:
            last_error = exc
            sleep_fn(_WINDOW_DISCOVERY_INTERVAL_SECONDS)
    if last_error is None:  # pragma: no cover -- loop always runs >=1 time
        msg = f"No window found for {_TERMINAL_APP_ID!r}."
        raise WindowNotFoundError(msg)
    raise last_error


# One argument per real, injectable dependency this milestone's single
# riskiest capability needs -- matching this module's own established
# "no implicit defaults, explicit wiring only" precedent (see kernel.desktop's
# authorize_and_run_terminal_command docstring), not accidental bloat.
async def run_in_sandboxed_terminal(  # noqa: PLR0913
    command_text: str,
    *,
    sandbox: SandboxPort,
    desktop_window: DesktopWindowPort,
    synthetic_input: SyntheticInputPort,
    secret: SecretPort,
    tts: TtsPort,
    play_fn: PlayFn,
    ensure_profile: EnsureProfileFn,
    bind_paths: tuple[Path, ...] = (),
    sleep_fn: SleepFn | None = None,
) -> str | None:
    r"""Launch a sandboxed terminal, type ``command_text`` into it, and best-effort read output.

    ``async`` because ADR-0047's real-time indicator requires a real,
    spoken announcement (``TtsPort.speak``, already an async port
    throughout this codebase -- see ``kernel/voice_loop.py``'s own
    ``_speak``) before any keystroke is sent.

    Args:
        command_text: The text typed into the sandboxed terminal's
            shell, exactly as given -- the caller is responsible for
            including a trailing newline to actually submit a command
            (e.g. ``"pytest\n"``), matching real keyboard behavior.
        sandbox: Launches the real, contained terminal emulator
            process. No default -- see the module-level comment above.
        desktop_window: Finds/focuses/verifies-focus-of/reads the
            window the sandbox just launched. No default, same reason.
        synthetic_input: Opens the real RemoteDesktop portal session
            and fires the real keystrokes (ADR-0047). No default, same
            reason.
        secret: Persists/replays the portal's ``restore_token``
            (ADR-0047's own lifecycle). No default, same reason.
        tts: Synthesizes the real-time indicator's spoken announcement.
            No default, same reason.
        play_fn: Plays the synthesized announcement audio for real.
            No default, same reason -- matching ``kernel/voice_loop.py``'s
            own ``PlayFn`` shape exactly (real playback is deliberately
            a direct call, not a port, in that module; this one takes
            it injected rather than importing real hardware I/O itself,
            since ``application`` sits below ``kernel`` in this
            project's layering).
        ensure_profile: Ensures the real-time indicator's dedicated
            terminal profile exists and returns its UUID. No default,
            same reason.
        bind_paths: Host directories the sandboxed terminal can
            access. Empty by default -- a fully isolated shell with
            nothing granted, per ``SandboxPort``'s own default
            (ADR-0044).
        sleep_fn: Called between window-discovery poll attempts.
            Defaults to real ``time.sleep``. Tests inject a no-op to
            avoid a real, multi-second wait.

    Returns:
        The terminal's visible text after the command runs,
        best-effort -- ``None`` if the terminal emulator doesn't expose
        a usable AT-SPI2 ``Text`` interface.

    Raises:
        SyntheticInputUnavailableError: If the real-time indicator's
            hard-abort precondition fails (window not visible/showing,
            or the announcement could not be spoken), if the portal
            session cannot be opened (including the human denying the
            permission dialog), or if focus is lost before or during
            typing -- fail-closed, per ADR-0047: no keystroke is ever
            sent without both indicator checks passing first, and every
            remaining keystroke is aborted the instant a focus check
            fails.
    """
    profile_uuid = ensure_profile()
    sandbox.launch(
        (*_TERMINAL_LAUNCH_COMMAND, f"--profile={profile_uuid}"),
        bind_paths=bind_paths,
        allow_display=True,
    )
    handle = _find_the_sandboxed_terminal_window(desktop_window, sleep_fn or time.sleep)
    desktop_window.focus(handle)

    if not desktop_window.is_visible_and_showing(handle):
        msg = "Cannot type into the sandboxed terminal: its window is not visible/showing."
        raise SyntheticInputUnavailableError(msg)
    audio = await tts.speak(_TYPING_ANNOUNCEMENT)
    play_fn(audio)

    try:
        restore_token = secret.get_secret(_RESTORE_TOKEN_REFERENCE)
    except SecretNotFoundError:
        restore_token = None
    session = synthetic_input.start_session(restore_token)
    if session.new_restore_token is not None:
        secret.set_secret(_RESTORE_TOKEN_REFERENCE, session.new_restore_token)

    for character in command_text:
        keysym = _char_to_keysym(character)
        if not desktop_window.is_focused(handle):
            msg = "Focus was lost mid-command -- aborting remaining keystrokes."
            raise SyntheticInputUnavailableError(msg)
        synthetic_input.send_keysym(session, keysym, press=True)
        synthetic_input.send_keysym(session, keysym, press=False)
    if not desktop_window.is_focused(handle):
        msg = "Focus was lost after the last keystroke."
        raise SyntheticInputUnavailableError(msg)

    return desktop_window.read_visible_text(handle)
