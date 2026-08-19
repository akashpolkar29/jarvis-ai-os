"""Contract test: adapters must structurally satisfy CandidatePresentationPort."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.candidate_presentation import TtsTextCandidatePresentationAdapter
from jarvis.ports.candidate_presentation import CandidatePresentationPort

if TYPE_CHECKING:
    from jarvis.domain.audio import AudioStream


class _FakeTts:
    """A minimal stand-in TtsPort, satisfying the Protocol's shape only."""

    async def speak(self, text: str) -> AudioStream:
        """Not exercised here -- __init__ does zero I/O, this just needs to type-satisfy TtsPort."""
        raise NotImplementedError


def test_tts_text_candidate_presentation_adapter_satisfies_candidate_presentation_port() -> None:
    """TtsTextCandidatePresentationAdapter is structurally a CandidatePresentationPort.

    Safe to construct here: __init__ does zero I/O (it only stores its
    dependencies), so no real TTS model or audio device is required.
    """
    adapter = TtsTextCandidatePresentationAdapter(_FakeTts())

    assert isinstance(adapter, CandidatePresentationPort)


def test_an_object_missing_present_and_select_does_not_satisfy_the_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAPresenter:
        """Deliberately lacks present_and_select()."""

    assert isinstance(NotAPresenter(), CandidatePresentationPort) is False
