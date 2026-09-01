"""Adapters implementing jarvis.ports.console.ConsolePort.

:class:`GtkConsoleAdapter` is WP-74's own real implementation --
mirroring :class:`~jarvis.adapters.physical_confirmation.Gtk4PhysicalConfirmationAdapter`'s
own testability seam exactly: the real window-showing call lives
entirely in ``jarvis.ui.console``'s ``show_console_line``, injected
here as ``show_line_fn`` and defaulted to the real one. Unit tests
inject a fake to prove the pure wiring (the exact text passed through,
unchanged) without a display or a real GTK4 subprocess.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    ShowLineFn = Callable[[str], None]


def _default_show_line_fn(text: str) -> None:
    from jarvis.ui.console import show_console_line  # noqa: PLC0415 -- see module docstring

    show_console_line(text)


class GtkConsoleAdapter:
    """A real, on-screen console line, shown via a real, detached GTK4 subprocess."""

    def __init__(self, show_line_fn: ShowLineFn | None = None) -> None:
        """Store the function to use for actually showing a line. No I/O at construction time.

        Args:
            show_line_fn: The function :meth:`show_line` delegates to,
                defaulting to the real GTK4 subprocess launcher. Tests
                inject a fake here to prove the wiring without a
                display.
        """
        self._show_line_fn: ShowLineFn = show_line_fn or _default_show_line_fn

    def show_line(self, text: str) -> None:
        """Relay `text` to the injected show-line function, unchanged. Never blocks."""
        self._show_line_fn(text)
