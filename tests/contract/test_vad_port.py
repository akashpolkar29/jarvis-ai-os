"""Contract test: adapters must structurally satisfy jarvis.ports.vad.VadPort."""

from __future__ import annotations

from jarvis.adapters.vad import SileroVadAdapter
from jarvis.ports.vad import VadPort


def test_silero_vad_adapter_satisfies_vad_port() -> None:
    """SileroVadAdapter is structurally a VadPort.

    Safe to construct with no arguments here: __init__ does zero I/O
    (it only stores configuration), so this needs no real model file.
    """
    adapter = SileroVadAdapter()

    assert isinstance(adapter, VadPort)


def test_an_object_missing_segment_does_not_satisfy_vad_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAVadSource:
        """Deliberately lacks segment()."""

    assert isinstance(NotAVadSource(), VadPort) is False
