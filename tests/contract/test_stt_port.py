"""Contract test: adapters must structurally satisfy jarvis.ports.stt.SttPort."""

from __future__ import annotations

from jarvis.adapters.stt import FasterWhisperAdapter
from jarvis.ports.stt import SttPort


def test_faster_whisper_adapter_satisfies_stt_port() -> None:
    """FasterWhisperAdapter is structurally an SttPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores configuration), so this needs no real GPU.
    """
    adapter = FasterWhisperAdapter()

    assert isinstance(adapter, SttPort)


def test_an_object_missing_transcribe_does_not_satisfy_stt_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAnSttSource:
        """Deliberately lacks transcribe()."""

    assert isinstance(NotAnSttSource(), SttPort) is False
