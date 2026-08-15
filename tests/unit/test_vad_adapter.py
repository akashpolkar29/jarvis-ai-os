"""Unit tests for jarvis.adapters.vad.

What's exercised here is entirely the pure, hardware-free pieces:
_VadSegmenter's hysteresis segmentation logic (fed synthetic per-window
probability sequences) and SileroVadAdapter.segment()'s windowing/
Segment-construction wiring, via an injected fake predict_fn. No real
model, no real hardware of any kind is touched -- the real ONNX
inference path (_SileroVadModel, _ensure_model_loaded) has no
automated test, matching jarvis.adapters.wake_word's
_default_score_source; its correctness is proven by manual
verification instead (see docs/architecture/m1-voice-architecture.md
section 10).
"""

from __future__ import annotations

import numpy as np
import pytest

from jarvis.adapters.vad import SileroVadAdapter, _VadSegmenter
from jarvis.domain.audio import AudioChunk

# Small, readable custom durations for fast, exact-window-count tests --
# not the real defaults, which would need many more windows to reach.
_THRESHOLD = 0.5
_NEG_THRESHOLD = 0.3
_MIN_SPEECH_MS = 64  # 1024 samples = 2 windows at 16kHz/512-sample windows
_MIN_SILENCE_MS = 32  # 512 samples = 1 window
_SAMPLE_RATE = 16000
_WINDOW_SAMPLES = 512


def _segmenter(speech_pad_ms: int = 0) -> _VadSegmenter:
    return _VadSegmenter(
        threshold=_THRESHOLD,
        neg_threshold=_NEG_THRESHOLD,
        min_speech_duration_ms=_MIN_SPEECH_MS,
        min_silence_duration_ms=_MIN_SILENCE_MS,
        speech_pad_ms=speech_pad_ms,
        sample_rate=_SAMPLE_RATE,
        window_size_samples=_WINDOW_SAMPLES,
    )


# --- _VadSegmenter ----------------------------------------------------------


def test_segmenter_emits_nothing_for_silence_only() -> None:
    """A stream of consistently low probabilities never triggers a segment."""
    segmenter = _segmenter()
    results = [segmenter.observe(i, 0.05) for i in range(10)]

    assert results == [None] * 10
    assert segmenter.finalize(total_samples=10 * _WINDOW_SAMPLES) is None


def test_segmenter_emits_one_segment_for_a_clean_speech_run() -> None:
    """Speech long enough, followed by silence long enough, emits exactly one bounded segment."""
    segmenter = _segmenter()
    results = [segmenter.observe(i, 0.9) for i in range(3)]  # windows 0,1,2: speech
    results.append(segmenter.observe(3, 0.1))  # silence starts (temp_end set)
    results.append(segmenter.observe(4, 0.1))  # silence confirmed (>= min_silence_samples)

    assert results[:4] == [None, None, None, None]
    assert results[4] == (0, 1536)  # start=0, end=window index 3 * 512 = 1536, no padding


def test_segmenter_discards_speech_shorter_than_min_speech_duration() -> None:
    """A brief blip below min_speech_duration_ms is discarded, not emitted as a segment."""
    segmenter = _segmenter()
    results = [
        segmenter.observe(0, 0.9),  # start
        segmenter.observe(1, 0.1),  # silence starts (temp_end=512)
        segmenter.observe(2, 0.1),  # silence confirmed: end=512, start=0, duration=512 < 1024
    ]

    assert results == [None, None, None]


def test_segmenter_does_not_fragment_on_a_brief_sub_silence_dip() -> None:
    """A dip that doesn't reach min_silence_duration_ms doesn't split one utterance into two.

    This is the actual point of the hysteresis design: real speech has
    brief pauses that must not fragment a single utterance into
    multiple segments.
    """
    segmenter = _segmenter()
    results = [
        segmenter.observe(0, 0.9),  # start
        segmenter.observe(1, 0.1),  # brief dip: temp_end=512
        segmenter.observe(2, 0.9),  # speech resumes before min_silence elapses: temp_end reset
        segmenter.observe(3, 0.9),
        segmenter.observe(4, 0.1),  # real silence starts: temp_end=2048
        segmenter.observe(5, 0.1),  # confirmed: duration=512-0... see below
    ]

    assert results[:5] == [None, None, None, None, None]
    # One segment spanning the whole run, including the dip -- not two fragments.
    assert results[5] == (0, 2048)


def test_segmenter_ignores_a_probability_between_neg_threshold_and_threshold() -> None:
    """A score in the asymmetric hysteresis gap (neg_threshold <= p < threshold) does nothing.

    Neither confirms continued speech-start behavior nor starts a
    silence countdown -- this is the actual asymmetric-threshold
    behavior the design relies on.
    """
    segmenter = _segmenter()
    segmenter.observe(0, 0.9)  # triggered
    result = segmenter.observe(1, 0.4)  # between neg_threshold (0.3) and threshold (0.5)

    assert result is None
    # Still triggered, no silence countdown started -- confirm via a subsequent real silence
    # needing the full min_silence_samples from scratch.
    assert segmenter.observe(2, 0.1) is None  # temp_end starts now, not at window 1
    assert segmenter.observe(3, 0.1) is not None  # confirmed one window later


def test_segmenter_applies_symmetric_padding_and_clamps_start_to_zero() -> None:
    """speech_pad_ms is applied to both ends; start is clamped to >= 0, never negative."""
    segmenter = _segmenter(speech_pad_ms=100)  # 1600 samples of padding
    segmenter.observe(0, 0.9)
    segmenter.observe(1, 0.9)
    segmenter.observe(2, 0.1)
    result = segmenter.observe(3, 0.1)

    assert result is not None
    start, end = result
    assert start == 0  # 0 - 1600 clamped to 0, not negative
    # temp_end was set at window 2 (2 * 512 = 1024), not when it was confirmed at window 3.
    assert end == 1024 + 1600  # unpadded end (where silence started) + padding


def test_segmenter_finalize_flushes_a_still_open_speech_run() -> None:
    """A speech run still active at end-of-buffer is flushed by finalize(), not lost."""
    segmenter = _segmenter()
    segmenter.observe(0, 0.9)
    segmenter.observe(1, 0.9)

    result = segmenter.finalize(total_samples=1200)

    assert result == (0, 1200)  # no padding configured in this test's segmenter


def test_segmenter_finalize_discards_a_too_short_trailing_run() -> None:
    """A trailing run shorter than min_speech_duration_ms is discarded by finalize() too."""
    segmenter = _segmenter()
    segmenter.observe(0, 0.9)

    assert segmenter.finalize(total_samples=500) is None  # 500 < 1024 min_speech_samples


def test_segmenter_finalize_returns_none_when_nothing_was_ever_triggered() -> None:
    """finalize() on a segmenter that never saw speech returns None, not a spurious segment."""
    segmenter = _segmenter()
    segmenter.observe(0, 0.05)

    assert segmenter.finalize(total_samples=512) is None


# --- SileroVadAdapter.segment() (injected predict_fn) -----------------------


def _int16_silence(num_samples: int) -> bytes:
    return np.zeros(num_samples, dtype=np.int16).tobytes()


async def test_segment_yields_nothing_when_predict_fn_always_returns_low_scores() -> None:
    """An AudioChunk with no detected speech yields no Segments."""
    audio = AudioChunk(samples=_int16_silence(_WINDOW_SAMPLES * 4), sample_rate=_SAMPLE_RATE)
    adapter = SileroVadAdapter(predict_fn=lambda _window: 0.0)

    segments = [seg async for seg in adapter.segment(audio)]

    assert segments == []


async def test_segment_yields_one_segment_for_a_clean_speech_run() -> None:
    """A run of high scores long enough, then low scores, yields exactly one Segment.

    SileroVadAdapter.segment() uses _VadSegmenter's real defaults (not
    this test module's small custom durations above) for everything
    except threshold: DEFAULT_MIN_SPEECH_DURATION_MS=250ms needs >= 8
    windows of speech (4000 samples / 512), and
    DEFAULT_MIN_SILENCE_DURATION_MS=100ms needs >= 4 windows of
    silence after it starts (1600 samples / 512) to confirm the end.
    10 speech + 5 silence windows comfortably clears both floors.
    """
    scores = iter([0.9] * 10 + [0.1] * 5)
    audio = AudioChunk(samples=_int16_silence(_WINDOW_SAMPLES * 15), sample_rate=_SAMPLE_RATE)
    adapter = SileroVadAdapter(predict_fn=lambda _window: next(scores))

    segments = [seg async for seg in adapter.segment(audio)]

    assert len(segments) == 1
    assert segments[0].sample_rate == _SAMPLE_RATE
    # Segment bytes are a real slice of the original audio, PCM16 (even length).
    assert len(segments[0].samples) % 2 == 0
    assert len(segments[0].samples) > 0


async def test_segment_rejects_a_sample_rate_other_than_16khz() -> None:
    """SileroVadAdapter only supports the project's fixed 16kHz throughout."""
    audio = AudioChunk(samples=_int16_silence(_WINDOW_SAMPLES), sample_rate=8000)
    adapter = SileroVadAdapter(predict_fn=lambda _window: 0.0)

    with pytest.raises(ValueError, match="16000"):
        _ = [seg async for seg in adapter.segment(audio)]


def test_constructing_the_adapter_with_no_arguments_does_no_io() -> None:
    """Matches OpenWakeWordAdapter's convention: __init__ does zero I/O."""
    adapter = SileroVadAdapter()

    assert adapter is not None
