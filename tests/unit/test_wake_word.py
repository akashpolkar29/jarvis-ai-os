"""Unit tests for jarvis.domain.wake_word.WakeEvent."""

from __future__ import annotations

import dataclasses

import pytest

from jarvis.domain.audio import AudioChunk
from jarvis.domain.wake_word import WakeEvent

_MID_RANGE_SCORE = 0.814
_SAMPLE_RATE = 16000

_SOME_AUDIO = AudioChunk(samples=b"\x00\x00\x01\x00", sample_rate=_SAMPLE_RATE)


def test_wake_event_accepts_a_score_of_zero() -> None:
    """0.0, the lower boundary, is a valid score."""
    assert WakeEvent(score=0.0, audio=_SOME_AUDIO).score == 0.0


def test_wake_event_accepts_a_score_of_one() -> None:
    """1.0, the upper boundary, is a valid score."""
    assert WakeEvent(score=1.0, audio=_SOME_AUDIO).score == 1.0


def test_wake_event_accepts_a_mid_range_score() -> None:
    """A typical, non-boundary score is valid."""
    assert WakeEvent(score=_MID_RANGE_SCORE, audio=_SOME_AUDIO).score == _MID_RANGE_SCORE


def test_wake_event_rejects_a_negative_score() -> None:
    """A score below 0.0 is not a valid detection confidence."""
    with pytest.raises(ValueError, match=r"WakeEvent\.score"):
        WakeEvent(score=-0.01, audio=_SOME_AUDIO)


def test_wake_event_rejects_a_score_above_one() -> None:
    """A score above 1.0 is not a valid detection confidence."""
    with pytest.raises(ValueError, match=r"WakeEvent\.score"):
        WakeEvent(score=1.01, audio=_SOME_AUDIO)


def test_wake_event_preserves_the_audio_it_was_given() -> None:
    """The audio field is stored as given, not re-derived or dropped."""
    assert WakeEvent(score=0.9, audio=_SOME_AUDIO).audio == _SOME_AUDIO


def test_wake_event_is_frozen() -> None:
    """WakeEvent is immutable, matching every other domain value object."""
    event = WakeEvent(score=0.9, audio=_SOME_AUDIO)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.score = 0.1  # type: ignore[misc]
