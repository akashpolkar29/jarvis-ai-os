"""Contract test: adapters must structurally satisfy ConsolePort."""

from __future__ import annotations

from jarvis.adapters.console import GtkConsoleAdapter
from jarvis.ports.console import ConsolePort


def test_gtk_console_adapter_satisfies_the_port() -> None:
    """GtkConsoleAdapter is structurally a ConsolePort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores the show-line function), so this needs no real
    display.
    """
    adapter = GtkConsoleAdapter()

    assert isinstance(adapter, ConsolePort)


def test_an_object_missing_show_line_does_not_satisfy_the_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAConsole:
        """Deliberately lacks show_line()."""

    assert isinstance(NotAConsole(), ConsolePort) is False
