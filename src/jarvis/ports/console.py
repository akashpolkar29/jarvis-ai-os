"""The console port: the seam between a real capability outcome and a real on-screen line.

:class:`ConsolePort` is WP-74's own minimal mechanism satisfying
`docs/ROADMAP.md`'s standing "always legible" principle's on-screen
half -- the spoken half already exists (M1's `TtsPort`, unmodified,
reused elsewhere in this codebase; this port is not a replacement for
it, only the on-screen counterpart that never existed until now).

Deliberately one method, deliberately no notion of a "view": per
`m5-browser-coding.md`'s own recovered-fragment instruction ("Console
UI views... interface frozen; views deliberately not [designed] --
you will know what you want after six months of using the HUD"), this
port fixes only the shape "some real text can be shown, on screen,
right now" -- not a windowing model, not a layout, not a history. A
real, minimal mechanism, not a designed UI.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.console`` for the
concrete GTK4-backed adapter that satisfies this port, and
``jarvis.ui.console`` for the real, subprocess-launched window itself.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ConsolePort(Protocol):
    """A real, on-screen surface that can show one line of text right now."""

    def show_line(self, text: str) -> None:
        """Show ``text`` as a real, visible on-screen line.

        Never blocks the caller -- unlike
        :class:`~jarvis.ports.physical_confirmation.PhysicalConfirmationPort`'s
        own deliberately-blocking ``await_physical_confirmation``, this
        is a fire-and-forget legibility signal, not a gate anything
        waits on. Real implementations may fail silently on a genuinely
        headless environment (no display available) -- see the real
        adapter's own docstring for what "silently" means precisely.

        Args:
            text: The real, human-readable line to show.
        """
        ...
