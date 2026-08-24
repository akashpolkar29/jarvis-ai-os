"""Terminal orchestration: launch a sandboxed terminal, type a command, best-effort read output.

:func:`run_in_sandboxed_terminal` is the real, multi-step flow
ADR-0046 requires: :meth:`~jarvis.ports.sandbox.SandboxPort.launch`
starts a real, contained terminal emulator process -- never keystroke
injection into an arbitrary, already-running terminal window;
:meth:`~jarvis.ports.desktop_window.DesktopWindowPort.find_or_launch`
locates the window that process just created; ``focus()``/
``type_text()`` run the command inside it;
``read_visible_text()`` best-effort captures the result afterward,
tagged ``Trust.UNTRUSTED_EXTERNAL`` by ``kernel.desktop`` per ADR-0011.

**Structural guarantee (ADR-0046's acceptance criterion #4), not
merely documented:** this function's own body calls
``sandbox.launch()`` as its very first statement, strictly before any
``DesktopWindowPort.type_text()`` call -- there is no branch, no early
return, no alternate path that reaches ``type_text()`` without first
executing ``launch()``. ``tests/meta/test_terminal_sandboxed_launch_only.py``
verifies this AST-structurally (the ``launch`` call's statement index
precedes ``type_text``'s in this function's flat body), and separately
verifies :func:`_find_the_sandboxed_terminal_window` never passes a
``launch_command`` to ``DesktopWindowPort.find_or_launch`` -- that
port's own launch path (``adapters/desktop_window.py``'s
``_launch_subprocess``) is a plain, **unsandboxed** subprocess call,
and reaching it from this module even as a retry fallback would
silently defeat ADR-0046's whole guarantee. Window discovery here
polls by retrying a bare ``find_or_launch(app_id)`` (no launch
argument at all) instead.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from jarvis.ports.desktop_window import WindowNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from jarvis.domain.desktop import WindowHandle
    from jarvis.ports.desktop_window import DesktopWindowPort
    from jarvis.ports.sandbox import SandboxPort

    SleepFn = Callable[[float], None]

_TERMINAL_APP_ID = "gnome-terminal"
"""Confirmed a real, native (non-snap) binary during WP-43's spike
(/usr/bin/gnome-terminal) -- chosen over Brave/VS Code's own
snap-confined AT-SPI2 access issues, per ADR-0046's own reasoning."""

_TERMINAL_LAUNCH_COMMAND: tuple[str, ...] = ("gnome-terminal",)

_WINDOW_DISCOVERY_ATTEMPTS = 10
_WINDOW_DISCOVERY_INTERVAL_SECONDS = 0.5


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


def run_in_sandboxed_terminal(
    command_text: str,
    *,
    sandbox: SandboxPort,
    desktop_window: DesktopWindowPort,
    bind_paths: tuple[Path, ...] = (),
    sleep_fn: SleepFn | None = None,
) -> str | None:
    r"""Launch a sandboxed terminal, type ``command_text`` into it, and best-effort read output.

    Args:
        command_text: The text typed into the sandboxed terminal's
            shell, exactly as given -- the caller is responsible for
            including a trailing newline to actually submit a command
            (e.g. ``"pytest\n"``), matching real keyboard behavior.
        sandbox: Launches the real, contained terminal emulator
            process. No default -- callers construct a real
            ``BwrapSandboxAdapter`` themselves, mirroring
            ``kernel.desktop``'s own no-default precedent for
            GLib-touching ports.
        desktop_window: Finds/focuses/types into/reads the window the
            sandbox just launched. No default, for the same reason.
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
        a usable AT-SPI2 ``Text`` interface (a real, expected outcome
        for some terminal emulators, not an error; genuinely
        unconfirmed for ``gnome-terminal`` specifically until this
        function runs for real -- see WP-43's own honesty note on this
        in ``adapters/desktop_window.py``).
    """
    sandbox.launch(_TERMINAL_LAUNCH_COMMAND, bind_paths=bind_paths)
    handle = _find_the_sandboxed_terminal_window(desktop_window, sleep_fn or time.sleep)
    desktop_window.focus(handle)
    desktop_window.type_text(handle, command_text)
    return desktop_window.read_visible_text(handle)
