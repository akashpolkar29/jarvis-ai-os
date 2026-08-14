"""Contract test: adapters must structurally satisfy jarvis.ports.wake_word.WakeWordPort."""

from __future__ import annotations

from jarvis.adapters.wake_word import OpenWakeWordAdapter
from jarvis.ports.wake_word import WakeWordPort


def test_open_wake_word_adapter_satisfies_wake_word_port() -> None:
    """OpenWakeWordAdapter is structurally a WakeWordPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores configuration), so this needs no real microphone.
    """
    adapter = OpenWakeWordAdapter()

    assert isinstance(adapter, WakeWordPort)


def test_an_object_missing_stream_does_not_satisfy_wake_word_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAWakeWordSource:
        """Deliberately lacks stream()."""

    assert isinstance(NotAWakeWordSource(), WakeWordPort) is False
