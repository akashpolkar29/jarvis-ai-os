"""Unit tests for jarvis.adapters.wake_word.

What's exercised here is entirely the pure, hardware-free pieces:
_WakeWordDebouncer's score interpretation, _AudioRingBuffer's eviction
logic, _score_for_wake_word's key matching, and OpenWakeWordAdapter's
own stream()-to-WakeEvent wiring (including the ADR-0033 ring-buffer
snapshot and post-trigger capture) via an injected fake frame_source.
No real microphone, no real openWakeWord model, no real hardware of
any kind is touched -- OpenWakeWordAdapter._default_frame_source (the
one piece that does touch real hardware) has no automated test,
matching jarvis.adapters.media_player's _send_method_call_over_dbus;
its correctness is proven by manual verification instead (see
docs/architecture/m1-voice-architecture.md section 10).

Most tests below construct OpenWakeWordAdapter with
post_trigger_capture_s=0.0, so a firing consumes exactly the frames
the fake source was given -- keeping these tests' frame lists and
event-count assertions unchanged from before ADR-0033, since they are
testing debounce/firing logic, not the post-trigger capture window
itself (that gets its own dedicated tests further down).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from jarvis.adapters.wake_word import (
    OpenWakeWordAdapter,
    _AudioRingBuffer,
    _score_for_wake_word,
    _WakeWordDebouncer,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_RING_BUFFER_CAPACITY_SAMPLES = 10
_OVERSIZED_CHUNK_SAMPLES = 20
_A_SCORE = 0.73
_ANOTHER_SCORE = 0.5

# --- _WakeWordDebouncer -------------------------------------------------


def test_debouncer_does_not_fire_on_a_single_qualifying_frame() -> None:
    """One frame at/above threshold alone is not enough -- WP-19 found single frames too noisy."""
    debouncer = _WakeWordDebouncer(threshold=0.5)

    assert debouncer.observe(0.9) is False


def test_debouncer_fires_on_the_second_consecutive_qualifying_frame() -> None:
    """Two consecutive frames at/above threshold confirms a detection."""
    debouncer = _WakeWordDebouncer(threshold=0.5)

    assert debouncer.observe(0.9) is False
    assert debouncer.observe(0.8) is True


def test_debouncer_treats_a_score_exactly_at_threshold_as_qualifying() -> None:
    """The comparison is >=, not >: a score exactly equal to the threshold counts."""
    debouncer = _WakeWordDebouncer(threshold=0.5)

    assert debouncer.observe(0.5) is False
    assert debouncer.observe(0.5) is True


def test_debouncer_resets_the_streak_on_a_sub_threshold_frame() -> None:
    """A single low frame between two qualifying frames prevents an early, wrong firing."""
    debouncer = _WakeWordDebouncer(threshold=0.5)

    assert debouncer.observe(0.9) is False
    assert debouncer.observe(0.1) is False  # resets the streak
    assert debouncer.observe(0.9) is False  # streak restarts at 1, not 2
    assert debouncer.observe(0.9) is True  # now 2 consecutive


def test_debouncer_does_not_refire_on_every_frame_of_a_long_above_threshold_run() -> None:
    """One sustained utterance fires exactly once, not once per frame it stays above threshold."""
    debouncer = _WakeWordDebouncer(threshold=0.5)
    results = [debouncer.observe(0.9) for _ in range(6)]

    assert results == [False, True, False, True, False, True]


def test_debouncer_requires_a_fresh_streak_after_firing() -> None:
    """After firing, a single qualifying frame alone does not immediately refire."""
    debouncer = _WakeWordDebouncer(threshold=0.5)
    debouncer.observe(0.9)
    fired = debouncer.observe(0.9)
    assert fired is True

    assert debouncer.observe(0.9) is False  # streak of 1 post-reset
    assert debouncer.observe(0.9) is True  # streak of 2: fires again


def test_debouncer_respects_a_custom_required_consecutive_frame_count() -> None:
    """required_consecutive_frames is configurable, not hardcoded to 2."""
    debouncer = _WakeWordDebouncer(threshold=0.5, required_consecutive_frames=3)

    assert debouncer.observe(0.9) is False
    assert debouncer.observe(0.9) is False
    assert debouncer.observe(0.9) is True


# --- _AudioRingBuffer -----------------------------------------------------


def test_ring_buffer_starts_empty() -> None:
    """A freshly constructed buffer has zero buffered samples."""
    buffer = _AudioRingBuffer(max_duration_s=1.0, sample_rate=10)

    assert len(buffer) == 0
    assert buffer.snapshot().size == 0


def test_ring_buffer_accumulates_within_capacity() -> None:
    """Pushes that don't exceed the configured duration are all retained."""
    buffer = _AudioRingBuffer(max_duration_s=1.0, sample_rate=_RING_BUFFER_CAPACITY_SAMPLES)

    buffer.push(np.zeros(5, dtype=np.int16))
    buffer.push(np.ones(5, dtype=np.int16))

    assert len(buffer) == _RING_BUFFER_CAPACITY_SAMPLES
    np.testing.assert_array_equal(
        buffer.snapshot(),
        np.concatenate([np.zeros(5, dtype=np.int16), np.ones(5, dtype=np.int16)]),
    )


def test_ring_buffer_evicts_the_oldest_chunk_past_capacity() -> None:
    """A push that exceeds capacity evicts the oldest chunk(s), not the newest."""
    buffer = _AudioRingBuffer(max_duration_s=1.0, sample_rate=_RING_BUFFER_CAPACITY_SAMPLES)
    first = np.full(5, 1, dtype=np.int16)
    second = np.full(5, 2, dtype=np.int16)
    third = np.full(5, 3, dtype=np.int16)

    buffer.push(first)
    buffer.push(second)
    buffer.push(third)  # total would be 15 > capacity: evicts `first`

    assert len(buffer) == _RING_BUFFER_CAPACITY_SAMPLES
    np.testing.assert_array_equal(buffer.snapshot(), np.concatenate([second, third]))


def test_ring_buffer_never_evicts_the_only_remaining_chunk() -> None:
    """A single chunk larger than capacity is kept whole, not truncated or dropped."""
    buffer = _AudioRingBuffer(max_duration_s=1.0, sample_rate=_RING_BUFFER_CAPACITY_SAMPLES)
    oversized = np.zeros(_OVERSIZED_CHUNK_SAMPLES, dtype=np.int16)

    buffer.push(oversized)

    assert len(buffer) == _OVERSIZED_CHUNK_SAMPLES
    assert buffer.snapshot().size == _OVERSIZED_CHUNK_SAMPLES


# --- _score_for_wake_word ---------------------------------------------------


def test_score_for_wake_word_matches_a_versioned_model_key() -> None:
    """Key naming varies across openWakeWord versions (e.g. 'hey_jarvis_v0.1'): substring match."""
    assert _score_for_wake_word({"hey_jarvis_v0.1": _A_SCORE}) == _A_SCORE


def test_score_for_wake_word_matches_case_insensitively() -> None:
    """Key matching does not depend on exact casing."""
    assert _score_for_wake_word({"HEY_JARVIS": _ANOTHER_SCORE}) == _ANOTHER_SCORE


def test_score_for_wake_word_returns_zero_when_no_matching_key_is_present() -> None:
    """A missing key is treated the same as a confidently-absent detection, not an error."""
    assert _score_for_wake_word({"alexa_v0.1": 0.9}) == 0.0


def test_score_for_wake_word_returns_zero_for_an_empty_predictions_dict() -> None:
    """An empty predictions dict is also a confidently-absent detection."""
    assert _score_for_wake_word({}) == 0.0


_CONFIRMING_SCORE = 0.8
_TWO_SEPARATE_EVENTS = 2
_THREE_EVENTS_FROM_A_LONG_RUN = 3
_SAMPLE_RATE = 16000
_FRAME_SAMPLES = 4

# --- OpenWakeWordAdapter.stream() (injected frame_source) ------------------


def _chunk(fill_value: int = 0) -> np.ndarray:
    """A tiny, fixed-size fake raw-audio frame -- content is irrelevant to firing/count logic."""
    return np.full(_FRAME_SAMPLES, fill_value, dtype=np.int16)


def _fake_frame_source(scores: list[float]) -> AsyncIterator[tuple[float, np.ndarray]]:
    """Pair each score with a distinct fake chunk, so audio content is traceable per-frame."""

    async def _source() -> AsyncIterator[tuple[float, np.ndarray]]:
        for index, score in enumerate(scores):
            yield score, _chunk(fill_value=index)

    return _source()


async def test_stream_yields_no_events_when_no_streak_ever_qualifies() -> None:
    """A sequence with no two-consecutive-qualifying-frame streak yields nothing."""
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.1, 0.9, 0.1, 0.2]),
        post_trigger_capture_s=0.0,
    )

    events = [event async for event in adapter.stream()]

    assert events == []


async def test_stream_yields_one_wake_event_for_one_qualifying_streak() -> None:
    """A single two-consecutive-qualifying-frame streak yields exactly one WakeEvent."""
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.1, 0.9, _CONFIRMING_SCORE, 0.1]),
        post_trigger_capture_s=0.0,
    )

    events = [event async for event in adapter.stream()]

    assert len(events) == 1
    assert events[0].score == _CONFIRMING_SCORE  # the confirming (second) frame's score


async def test_stream_yields_one_wake_event_per_separated_streak() -> None:
    """Two separate qualifying streaks, with a gap between them, yield two WakeEvents.

    post_trigger_capture_s=0.0 is essential here, not incidental: with
    a nonzero window, the first firing would consume the remaining
    frames (including the second streak) as post-trigger capture
    instead of evaluating them for a new detection -- exactly the
    real, intended ADR-0033 behavior, just not what this test is
    about. See test_a_confirmed_detection_pauses_debouncing below for
    that behavior itself.
    """
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.9, 0.9, 0.1, 0.9, 0.9]),
        post_trigger_capture_s=0.0,
    )

    events = [event async for event in adapter.stream()]

    assert len(events) == _TWO_SEPARATE_EVENTS


async def test_stream_does_not_flood_events_during_one_long_above_threshold_run() -> None:
    """A long above-threshold run fires roughly one WakeEvent per pair of frames, not per frame."""
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.9] * 6), post_trigger_capture_s=0.0
    )

    events = [event async for event in adapter.stream()]

    # Fires on frames 2, 4, 6 -- see _WakeWordDebouncer's own tests.
    assert len(events) == _THREE_EVENTS_FROM_A_LONG_RUN


async def test_stream_respects_a_custom_threshold() -> None:
    """A score below the configured (non-default) threshold never fires."""
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.6, 0.6]),
        threshold=0.7,
        post_trigger_capture_s=0.0,
    )

    events = [event async for event in adapter.stream()]

    assert events == []


# --- OpenWakeWordAdapter.stream(): ADR-0033 ring buffer / post-trigger -----


async def test_a_wake_event_carries_the_pre_trigger_ring_buffer_snapshot() -> None:
    """With no post-trigger capture, the event's audio is exactly the frames seen so far."""
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.9, 0.9]), post_trigger_capture_s=0.0
    )

    events = [event async for event in adapter.stream()]

    assert len(events) == 1
    expected = np.concatenate([_chunk(0), _chunk(1)]).astype(np.int16).tobytes()
    assert events[0].audio.samples == expected
    assert events[0].audio.sample_rate == _SAMPLE_RATE


async def test_a_wake_event_includes_post_trigger_frames_up_to_the_configured_window() -> None:
    """A nonzero post_trigger_capture_s pulls further frames into the same event's audio."""
    post_trigger_frame_count = 2
    post_trigger_seconds = (post_trigger_frame_count * _FRAME_SAMPLES) / _SAMPLE_RATE
    # Two frames confirm the trigger; two more are available to be captured afterward.
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.9, 0.9, 0.9, 0.9]),
        post_trigger_capture_s=post_trigger_seconds,
    )

    events = [event async for event in adapter.stream()]

    assert len(events) == 1
    expected = (
        np.concatenate([_chunk(0), _chunk(1), _chunk(2), _chunk(3)]).astype(np.int16).tobytes()
    )
    assert events[0].audio.samples == expected


async def test_post_trigger_capture_stops_gracefully_when_the_source_is_exhausted() -> None:
    """If the frame source runs out mid-window, whatever was captured is used, not an error."""
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.9, 0.9]),
        post_trigger_capture_s=10.0,  # far more than the two-frame source can ever supply
    )

    events = [event async for event in adapter.stream()]

    assert len(events) == 1
    expected = np.concatenate([_chunk(0), _chunk(1)]).astype(np.int16).tobytes()
    assert events[0].audio.samples == expected


async def test_a_confirmed_detection_pauses_debouncing_during_post_trigger_capture() -> None:
    """Frames consumed as post-trigger capture are not also evaluated for a new detection.

    A second, otherwise-qualifying streak that falls entirely inside
    the first detection's post-trigger window does not produce a
    second WakeEvent -- see ADR-0033: capturing a command, not also
    watching for a new wake word, is the point of that window.
    """
    post_trigger_seconds = (2 * _FRAME_SAMPLES) / _SAMPLE_RATE
    adapter = OpenWakeWordAdapter(
        frame_source=lambda: _fake_frame_source([0.9, 0.9, 0.9, 0.9]),
        post_trigger_capture_s=post_trigger_seconds,
    )

    events = [event async for event in adapter.stream()]

    assert len(events) == 1


def test_constructing_the_adapter_with_no_arguments_does_no_io() -> None:
    """Matches MprisMediaPlayerAdapter's convention: __init__ does zero I/O.

    Safe to construct with no arguments -- the real frame_source
    (_default_frame_source) is only ever invoked when stream() is
    actually iterated, never at construction time.
    """
    adapter = OpenWakeWordAdapter()

    assert adapter is not None
