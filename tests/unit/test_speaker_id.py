"""Unit tests for jarvis.domain.speaker_id.SpeakerScore."""

from __future__ import annotations

import dataclasses

import pytest

from jarvis.domain.speaker_id import SpeakerScore

_MID_RANGE_CONFIDENCE = 0.732


def test_speaker_score_accepts_a_confidence_of_zero() -> None:
    """0.0, the lower boundary, is a valid confidence."""
    assert SpeakerScore(verified=False, confidence=0.0).confidence == 0.0


def test_speaker_score_accepts_a_confidence_of_one() -> None:
    """1.0, the upper boundary, is a valid confidence."""
    assert SpeakerScore(verified=True, confidence=1.0).confidence == 1.0


def test_speaker_score_accepts_a_mid_range_confidence() -> None:
    """A typical, non-boundary confidence is valid."""
    score = SpeakerScore(verified=True, confidence=_MID_RANGE_CONFIDENCE)
    assert score.confidence == _MID_RANGE_CONFIDENCE


def test_speaker_score_rejects_a_negative_confidence() -> None:
    """A confidence below 0.0 is not a valid value."""
    with pytest.raises(ValueError, match=r"SpeakerScore\.confidence"):
        SpeakerScore(verified=False, confidence=-0.01)


def test_speaker_score_rejects_a_confidence_above_one() -> None:
    """A confidence above 1.0 is not a valid value."""
    with pytest.raises(ValueError, match=r"SpeakerScore\.confidence"):
        SpeakerScore(verified=False, confidence=1.01)


def test_speaker_score_preserves_the_verified_flag() -> None:
    """verified is stored as given, independent of confidence."""
    assert SpeakerScore(verified=True, confidence=0.0).verified is True
    assert SpeakerScore(verified=False, confidence=1.0).verified is False


def test_speaker_score_is_frozen() -> None:
    """SpeakerScore is immutable, matching every other domain value object."""
    score = SpeakerScore(verified=False, confidence=0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        score.confidence = 0.5  # type: ignore[misc]
