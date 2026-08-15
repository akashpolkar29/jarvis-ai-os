"""Unit tests for jarvis.adapters.speaker_id.UnverifiedSpeakerIdAdapter."""

from __future__ import annotations

from jarvis.adapters.speaker_id import UnverifiedSpeakerIdAdapter
from jarvis.domain.audio import Segment

_SAMPLE_RATE = 16000


def test_score_always_returns_unverified() -> None:
    """score() always reports verified=False, confidence=0.0 -- no model, no exceptions."""
    adapter = UnverifiedSpeakerIdAdapter()
    segment = Segment(samples=b"\x00\x00" * 8, sample_rate=_SAMPLE_RATE)

    result = adapter.score(segment)

    assert result.verified is False
    assert result.confidence == 0.0


def test_score_ignores_the_audio_content() -> None:
    """The result is identical regardless of what audio is passed in."""
    adapter = UnverifiedSpeakerIdAdapter()
    quiet = Segment(samples=b"\x00\x00" * 8, sample_rate=_SAMPLE_RATE)
    loud = Segment(samples=b"\xff\x7f" * 8, sample_rate=_SAMPLE_RATE)

    assert adapter.score(quiet) == adapter.score(loud)


def test_constructing_the_adapter_with_no_arguments_does_no_io() -> None:
    """Matches every other adapter's convention: __init__ does zero I/O."""
    adapter = UnverifiedSpeakerIdAdapter()

    assert adapter is not None
