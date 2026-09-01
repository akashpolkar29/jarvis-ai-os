"""The real, minimal on-screen console line -- a fresh GTK4 subprocess per line.

WP-74's own deliverable: a real, minimal mechanism, not a designed UI
(`m5-browser-coding.md`'s own recovered-fragment instruction). One
real, visible window per call, showing one line of text, auto-closing
after a bounded timeout -- no history, no layout, no notion of a
"view" beyond that.

**Real, launched in a genuinely separate subprocess, not in-process**
-- unlike ``jarvis.ui.confirm.dialog``'s own ``Gtk.Application``,
which deliberately blocks the calling thread waiting for a real
keypress. A console line is the opposite: a fire-and-forget legibility
signal (:class:`~jarvis.ports.console.ConsolePort`'s own contract)
that must never block whatever real action it is reporting on. This
project has no persistent, already-running GTK main loop anywhere to
show a non-blocking window inside; every other real, non-blocking
GUI/desktop action in this codebase (``BwrapSandboxAdapter.launch``,
``adapters/desktop_window.py``/``brave.py``/``vscode.py``'s own
``_launch_subprocess`` functions) already solves the identical
"show something real, don't block" problem the same way -- a real,
detached subprocess. Applied here for the first time to GTK4 itself,
not a new pattern for this codebase.

``text``/``timeout_s`` are passed as real subprocess *arguments*
(``sys.argv``), never interpolated into the launched script's own
source text -- the same "argv is caller-supplied config, never
shell/script-formatted content" discipline every other subprocess
call in this project already follows (``git apply -``, ``bwrap``'s own
argv). ``_CONSOLE_SCRIPT`` below is a fixed, literal string; nothing
about ``text``'s own content can change what code the subprocess runs.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    LaunchFn = Callable[[tuple[str, ...]], None]

_DEFAULT_TIMEOUT_S = 4.0

_CONSOLE_SCRIPT = """
import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

text = sys.argv[1]
timeout_s = float(sys.argv[2])

app = Gtk.Application(application_id="ai.jarvis.console")


def _on_activate(application):
    window = Gtk.ApplicationWindow(application=application, title="JARVIS")
    window.set_default_size(420, 80)
    label = Gtk.Label(label=text, wrap=True)
    label.set_margin_top(16)
    label.set_margin_bottom(16)
    label.set_margin_start(16)
    label.set_margin_end(16)
    window.set_child(label)
    window.present()

    def _on_timeout():
        window.close()
        application.quit()
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(int(timeout_s * 1000), _on_timeout)


app.connect("activate", _on_activate)
app.run(None)
"""


def _build_console_argv(text: str, timeout_s: float) -> tuple[str, ...]:
    """Return the real argv for a subprocess that shows `text` as a real, on-screen line.

    Pure, no I/O -- directly unit-tested, mirroring
    ``adapters/sandbox.py``'s own ``_build_bwrap_argv``.
    """
    return (sys.executable, "-c", _CONSOLE_SCRIPT, text, str(timeout_s))


def _default_launch(argv: tuple[str, ...]) -> None:
    """Launch `argv` as a real, detached subprocess. Never waits for it to finish.

    The one real, untested-by-design piece of this module: it requires
    a real display and a real GTK4/PyGObject install, matching
    ``jarvis.ui.confirm.dialog``'s own "needs a real display, proven by
    manual verification, not the automated suite" precedent.
    """
    subprocess.Popen(  # noqa: S603 -- argv is a fixed script plus typed, caller-supplied
        # text/timeout values, never shell text (see module docstring).
        argv,
        start_new_session=True,
    )


def show_console_line(
    text: str, *, timeout_s: float = _DEFAULT_TIMEOUT_S, launch: LaunchFn | None = None
) -> None:
    """Show `text` as a real, visible, auto-dismissing on-screen line. Never blocks the caller.

    Args:
        text: The real line to show.
        timeout_s: How long the window stays visible before it
            auto-closes. Defaults to `_DEFAULT_TIMEOUT_S`.
        launch: Launches the built argv. Defaults to a real, detached
            subprocess launch. Overridable for tests -- injected here,
            not read from a module-level default at call time, so a
            test can prove the real argv without ever spawning a real
            process or needing a real display.
    """
    argv = _build_console_argv(text, timeout_s)
    (launch or _default_launch)(argv)
