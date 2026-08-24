"""Contract test: adapters must structurally satisfy jarvis.ports.desktop_window's port."""

from __future__ import annotations

from jarvis.adapters.desktop_window import AtspiDesktopWindowAdapter
from jarvis.ports.desktop_window import DesktopWindowPort


def test_atspi_desktop_window_adapter_satisfies_desktop_window_port() -> None:
    """AtspiDesktopWindowAdapter is structurally a DesktopWindowPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores callables and an empty dict), so this needs no
    live accessibility bus.
    """
    adapter = AtspiDesktopWindowAdapter()

    assert isinstance(adapter, DesktopWindowPort)


def test_an_object_missing_the_four_methods_does_not_satisfy_desktop_window_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotADesktopWindowSource:
        """Deliberately lacks find_or_launch()/focus()/type_text()/read_visible_text()."""

    assert isinstance(NotADesktopWindowSource(), DesktopWindowPort) is False
