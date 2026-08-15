"""Contract test: adapters must structurally satisfy PhysicalConfirmationPort."""

from __future__ import annotations

from jarvis.adapters.physical_confirmation import Gtk4PhysicalConfirmationAdapter
from jarvis.ports.physical_confirmation import PhysicalConfirmationPort


def test_gtk4_physical_confirmation_adapter_satisfies_the_port() -> None:
    """Gtk4PhysicalConfirmationAdapter is structurally a PhysicalConfirmationPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores the dialog function), so this needs no real display.
    """
    adapter = Gtk4PhysicalConfirmationAdapter()

    assert isinstance(adapter, PhysicalConfirmationPort)


def test_an_object_missing_await_physical_confirmation_does_not_satisfy_the_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAPhysicalConfirmationSource:
        """Deliberately lacks await_physical_confirmation()."""

    assert isinstance(NotAPhysicalConfirmationSource(), PhysicalConfirmationPort) is False
