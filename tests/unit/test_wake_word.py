"""Unit tests for jarvis.domain.wake_word.WakeEvent."""

from __future__ import annotations

import dataclasses

import pytest

from jarvis.domain.wake_word import WakeEvent

_MID_RANGE_SCORE = 0.814


def test_wake_event_accepts_a_score_of_zero() -> None:
    """0.0, the lower boundary, is a valid score."""
    assert WakeEvent(score=0.0).score == 0.0


def test_wake_event_accepts_a_score_of_one() -> None:
    """1.0, the upper boundary, is a valid score."""
    assert WakeEvent(score=1.0).score == 1.0


def test_wake_event_accepts_a_mid_range_score() -> None:
    """A typical, non-boundary score is valid."""
    assert WakeEvent(score=_MID_RANGE_SCORE).score == _MID_RANGE_SCORE


def test_wake_event_rejects_a_negative_score() -> None:
    """A score below 0.0 is not a valid detection confidence."""
    with pytest.raises(ValueError, match=r"WakeEvent\.score"):
        WakeEvent(score=-0.01)


def test_wake_event_rejects_a_score_above_one() -> None:
    """A score above 1.0 is not a valid detection confidence."""
    with pytest.raises(ValueError, match=r"WakeEvent\.score"):
        WakeEvent(score=1.01)


def test_wake_event_is_frozen() -> None:
    """WakeEvent is immutable, matching every other domain value object."""
    event = WakeEvent(score=0.9)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.score = 0.1  # type: ignore[misc]
