"""Unit tests for jarvis.domain.audio.AudioChunk, Segment, and AudioStream."""

from __future__ import annotations

import dataclasses

import pytest

from jarvis.domain.audio import AudioChunk, AudioStream, Segment

_VALID_SAMPLES = b"\x00\x01\x02\x03"  # 4 bytes = 2 int16 samples
_SAMPLE_RATE = 16000


def test_audio_chunk_accepts_well_formed_pcm16() -> None:
    """An even number of bytes and a positive sample rate is valid."""
    chunk = AudioChunk(samples=_VALID_SAMPLES, sample_rate=_SAMPLE_RATE)
    assert chunk.samples == _VALID_SAMPLES
    assert chunk.sample_rate == _SAMPLE_RATE


def test_audio_chunk_accepts_empty_samples() -> None:
    """Zero bytes is a valid (empty) buffer -- even, not odd."""
    assert AudioChunk(samples=b"", sample_rate=_SAMPLE_RATE).samples == b""


def test_audio_chunk_rejects_an_odd_number_of_bytes() -> None:
    """16-bit PCM must be an even number of bytes -- a lone trailing byte is malformed."""
    with pytest.raises(ValueError, match="AudioChunk"):
        AudioChunk(samples=b"\x00\x01\x02", sample_rate=_SAMPLE_RATE)


def test_audio_chunk_rejects_a_zero_sample_rate() -> None:
    """A sample rate of zero is not meaningful."""
    with pytest.raises(ValueError, match="AudioChunk"):
        AudioChunk(samples=_VALID_SAMPLES, sample_rate=0)


def test_audio_chunk_rejects_a_negative_sample_rate() -> None:
    """A negative sample rate is not meaningful."""
    with pytest.raises(ValueError, match="AudioChunk"):
        AudioChunk(samples=_VALID_SAMPLES, sample_rate=-1)


def test_audio_chunk_is_frozen() -> None:
    """AudioChunk is immutable, matching every other domain value object."""
    chunk = AudioChunk(samples=_VALID_SAMPLES, sample_rate=_SAMPLE_RATE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        chunk.sample_rate = 8000  # type: ignore[misc]


def test_segment_accepts_well_formed_pcm16() -> None:
    """Same validation as AudioChunk, on the distinct Segment type."""
    segment = Segment(samples=_VALID_SAMPLES, sample_rate=_SAMPLE_RATE)
    assert segment.samples == _VALID_SAMPLES
    assert segment.sample_rate == _SAMPLE_RATE


def test_segment_rejects_an_odd_number_of_bytes() -> None:
    """Same PCM16 validation applies to Segment, independently of AudioChunk."""
    with pytest.raises(ValueError, match="Segment"):
        Segment(samples=b"\x00\x01\x02", sample_rate=_SAMPLE_RATE)


def test_segment_rejects_a_non_positive_sample_rate() -> None:
    """Same sample-rate validation applies to Segment, independently of AudioChunk."""
    with pytest.raises(ValueError, match="Segment"):
        Segment(samples=_VALID_SAMPLES, sample_rate=0)


def test_segment_is_frozen() -> None:
    """Segment is immutable, matching every other domain value object."""
    segment = Segment(samples=_VALID_SAMPLES, sample_rate=_SAMPLE_RATE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        segment.sample_rate = 8000  # type: ignore[misc]


def test_audio_chunk_and_segment_are_distinct_types() -> None:
    """AudioChunk and Segment are deliberately not the same type, or interchangeable."""
    chunk = AudioChunk(samples=_VALID_SAMPLES, sample_rate=_SAMPLE_RATE)
    assert not isinstance(chunk, Segment)


def test_audio_stream_accepts_well_formed_pcm16() -> None:
    """Same validation as AudioChunk/Segment, on the distinct AudioStream type."""
    stream = AudioStream(samples=_VALID_SAMPLES, sample_rate=_SAMPLE_RATE)
    assert stream.samples == _VALID_SAMPLES
    assert stream.sample_rate == _SAMPLE_RATE


def test_audio_stream_accepts_empty_samples_with_a_valid_sample_rate() -> None:
    """Empty text synthesized to empty audio is still a valid, well-formed AudioStream."""
    assert AudioStream(samples=b"", sample_rate=_SAMPLE_RATE).samples == b""


def test_audio_stream_rejects_an_odd_number_of_bytes() -> None:
    """Same PCM16 validation applies to AudioStream, independently of AudioChunk/Segment."""
    with pytest.raises(ValueError, match="AudioStream"):
        AudioStream(samples=b"\x00\x01\x02", sample_rate=_SAMPLE_RATE)


def test_audio_stream_rejects_a_non_positive_sample_rate() -> None:
    """Same sample-rate validation applies to AudioStream, independently of AudioChunk/Segment."""
    with pytest.raises(ValueError, match="AudioStream"):
        AudioStream(samples=_VALID_SAMPLES, sample_rate=0)


def test_audio_stream_is_frozen() -> None:
    """AudioStream is immutable, matching every other domain value object."""
    stream = AudioStream(samples=_VALID_SAMPLES, sample_rate=_SAMPLE_RATE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        stream.sample_rate = 8000  # type: ignore[misc]


def test_audio_stream_is_distinct_from_audio_chunk_and_segment() -> None:
    """AudioStream is deliberately not the same type as AudioChunk or Segment."""
    stream = AudioStream(samples=_VALID_SAMPLES, sample_rate=_SAMPLE_RATE)
    assert not isinstance(stream, AudioChunk)
    assert not isinstance(stream, Segment)
