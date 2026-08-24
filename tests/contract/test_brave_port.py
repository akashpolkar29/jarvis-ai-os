"""Contract test: adapters must structurally satisfy jarvis.ports.brave's BravePort."""

from __future__ import annotations

from jarvis.adapters.brave import BraveCliAdapter
from jarvis.ports.brave import BravePort


def test_brave_cli_adapter_satisfies_brave_port() -> None:
    """BraveCliAdapter is structurally a BravePort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores a callable), so this needs no real browser.
    """
    adapter = BraveCliAdapter()

    assert isinstance(adapter, BravePort)


def test_an_object_missing_open_url_does_not_satisfy_brave_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotABraveSource:
        """Deliberately lacks open_url()."""

    assert isinstance(NotABraveSource(), BravePort) is False
