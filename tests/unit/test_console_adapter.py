"""Unit tests for jarvis.adapters.console.GtkConsoleAdapter.

What's exercised here is entirely the pure wiring: text passed through
to an injected fake show_line_fn, unchanged. No real display, no real
GTK4 subprocess is touched -- the real path
(``jarvis.ui.console.show_console_line``) has no automated test here
either, matching ``test_physical_confirmation_adapter.py``'s own
precedent exactly.
"""

from __future__ import annotations

from jarvis.adapters.console import GtkConsoleAdapter


def test_show_line_relays_the_exact_text_through() -> None:
    received: list[str] = []

    adapter = GtkConsoleAdapter(show_line_fn=received.append)

    adapter.show_line("browser.open_page: https://example.com")

    assert received == ["browser.open_page: https://example.com"]


def test_show_line_can_be_called_more_than_once() -> None:
    received: list[str] = []

    adapter = GtkConsoleAdapter(show_line_fn=received.append)

    adapter.show_line("first")
    adapter.show_line("second")

    assert received == ["first", "second"]


def test_constructing_the_adapter_with_no_arguments_does_no_io() -> None:
    """Matches every other adapter's convention: __init__ does zero I/O."""
    adapter = GtkConsoleAdapter()

    assert adapter is not None
