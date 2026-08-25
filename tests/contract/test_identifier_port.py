"""Contract test: adapters must structurally satisfy jarvis.ports.identifier.IdPort."""

from __future__ import annotations

from jarvis.adapters.identifier import UuidIdAdapter
from jarvis.ports.identifier import IdPort


def test_uuid_id_adapter_satisfies_id_port() -> None:
    """UuidIdAdapter is structurally an IdPort.

    Safe to construct with no arguments here: __init__ does zero I/O.
    """
    adapter = UuidIdAdapter()

    assert isinstance(adapter, IdPort)


def test_an_object_missing_new_id_does_not_satisfy_id_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAnIdSource:
        """Deliberately lacks new_id()."""

    assert isinstance(NotAnIdSource(), IdPort) is False
