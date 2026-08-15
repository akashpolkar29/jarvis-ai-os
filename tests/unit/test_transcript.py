"""Unit tests for jarvis.domain.transcript.Transcript."""

from __future__ import annotations

import dataclasses

import pytest

from jarvis.domain.transcript import Transcript


def test_transcript_holds_recognized_text() -> None:
    """The text field round-trips as given."""
    assert Transcript(text="hey jarvis play music").text == "hey jarvis play music"


def test_transcript_accepts_empty_text() -> None:
    """Empty text is valid: a Segment VAD judged speech-containing may yield no recognized words."""
    assert Transcript(text="").text == ""


def test_transcript_is_frozen() -> None:
    """Transcript is immutable, matching every other domain value object."""
    transcript = Transcript(text="hello")
    with pytest.raises(dataclasses.FrozenInstanceError):
        transcript.text = "goodbye"  # type: ignore[misc]
