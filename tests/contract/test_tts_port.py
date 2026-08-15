"""Contract test: adapters must structurally satisfy jarvis.ports.tts.TtsPort."""

from __future__ import annotations

from jarvis.adapters.tts import PiperTtsAdapter
from jarvis.ports.tts import TtsPort


def test_piper_tts_adapter_satisfies_tts_port() -> None:
    """PiperTtsAdapter is structurally a TtsPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores configuration), so this needs no real model file.
    """
    adapter = PiperTtsAdapter()

    assert isinstance(adapter, TtsPort)


def test_an_object_missing_speak_does_not_satisfy_tts_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotATtsSource:
        """Deliberately lacks speak()."""

    assert isinstance(NotATtsSource(), TtsPort) is False
