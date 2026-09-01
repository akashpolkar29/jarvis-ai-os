"""The real, minimal Console UI mechanism (WP-74, `m5-browser-coding.md` deliverable 6).

See ``jarvis.ui.console.window`` for the implementation and the real
reasoning behind launching a fresh, detached GTK4 subprocess per line.
"""

from __future__ import annotations

from .window import show_console_line

__all__ = [
    "show_console_line",
]
