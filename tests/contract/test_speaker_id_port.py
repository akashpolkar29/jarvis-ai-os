"""Contract test: adapters must structurally satisfy jarvis.ports.speaker_id.SpeakerIdPort."""

from __future__ import annotations

from jarvis.adapters.speaker_id import UnverifiedSpeakerIdAdapter
from jarvis.ports.speaker_id import SpeakerIdPort


def test_unverified_speaker_id_adapter_satisfies_speaker_id_port() -> None:
    """UnverifiedSpeakerIdAdapter is structurally a SpeakerIdPort.

    Safe to construct with no arguments here: __init__ does zero I/O.
    """
    adapter = UnverifiedSpeakerIdAdapter()

    assert isinstance(adapter, SpeakerIdPort)


def test_an_object_missing_score_does_not_satisfy_speaker_id_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotASpeakerIdSource:
        """Deliberately lacks score()."""

    assert isinstance(NotASpeakerIdSource(), SpeakerIdPort) is False
