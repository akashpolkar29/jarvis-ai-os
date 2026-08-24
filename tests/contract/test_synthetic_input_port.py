"""Contract test: adapters must structurally satisfy jarvis.ports.synthetic_input's port."""

from __future__ import annotations

from jarvis.adapters.synthetic_input import PortalSyntheticInputAdapter
from jarvis.ports.synthetic_input import SyntheticInputPort


def test_portal_synthetic_input_adapter_satisfies_synthetic_input_port() -> None:
    """PortalSyntheticInputAdapter is structurally a SyntheticInputPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores callables), so this needs no D-Bus connection.
    """
    adapter = PortalSyntheticInputAdapter()

    assert isinstance(adapter, SyntheticInputPort)


def test_an_object_missing_the_two_methods_does_not_satisfy_synthetic_input_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotASyntheticInputSource:
        """Deliberately lacks start_session()/send_keysym()."""

    assert isinstance(NotASyntheticInputSource(), SyntheticInputPort) is False
