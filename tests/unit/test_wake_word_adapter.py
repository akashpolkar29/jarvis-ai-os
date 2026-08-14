"""Unit tests for jarvis.adapters.wake_word.

What's exercised here is entirely the pure, hardware-free pieces:
_WakeWordDebouncer's score interpretation, _AudioRingBuffer's eviction
logic, _score_for_wake_word's key matching, and OpenWakeWordAdapter's
own stream()-to-WakeEvent wiring via an injected fake score_source. No
real microphone, no real openWakeWord model, no real hardware of any
kind is touched -- OpenWakeWordAdapter._default_score_source (the one
piece that does touch real hardware) has no automated test, matching
jarvis.adapters.media_player's _send_method_call_over_dbus; its
correctness is proven by manual verification instead (see
docs/architecture/m1-voice-architecture.md section 10).
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

# --- OpenWakeWordAdapter.stream() (injected score_source) ------------------


def _fake_score_source(scores: list[float]) -> AsyncIterator[float]:
    async def _source() -> AsyncIterator[float]:
        for score in scores:
            yield score

    return _source()


async def test_stream_yields_no_events_when_no_streak_ever_qualifies() -> None:
    """A sequence with no two-consecutive-qualifying-frame streak yields nothing."""
    adapter = OpenWakeWordAdapter(score_source=lambda: _fake_score_source([0.1, 0.9, 0.1, 0.2]))

    events = [event async for event in adapter.stream()]

    assert events == []


async def test_stream_yields_one_wake_event_for_one_qualifying_streak() -> None:
    """A single two-consecutive-qualifying-frame streak yields exactly one WakeEvent."""
    adapter = OpenWakeWordAdapter(
        score_source=lambda: _fake_score_source([0.1, 0.9, _CONFIRMING_SCORE, 0.1])
    )

    events = [event async for event in adapter.stream()]

    assert len(events) == 1
    assert events[0].score == _CONFIRMING_SCORE  # the confirming (second) frame's score


async def test_stream_yields_one_wake_event_per_separated_streak() -> None:
    """Two separate qualifying streaks, with a gap between them, yield two WakeEvents."""
    adapter = OpenWakeWordAdapter(
        score_source=lambda: _fake_score_source([0.9, 0.9, 0.1, 0.9, 0.9])
    )

    events = [event async for event in adapter.stream()]

    assert len(events) == _TWO_SEPARATE_EVENTS


async def test_stream_does_not_flood_events_during_one_long_above_threshold_run() -> None:
    """A long above-threshold run fires roughly one WakeEvent per pair of frames, not per frame."""
    adapter = OpenWakeWordAdapter(score_source=lambda: _fake_score_source([0.9] * 6))

    events = [event async for event in adapter.stream()]

    # Fires on frames 2, 4, 6 -- see _WakeWordDebouncer's own tests.
    assert len(events) == _THREE_EVENTS_FROM_A_LONG_RUN


async def test_stream_respects_a_custom_threshold() -> None:
    """A score below the configured (non-default) threshold never fires."""
    adapter = OpenWakeWordAdapter(
        score_source=lambda: _fake_score_source([0.6, 0.6]), threshold=0.7
    )

    events = [event async for event in adapter.stream()]

    assert events == []


def test_constructing_the_adapter_with_no_arguments_does_no_io() -> None:
    """Matches MprisMediaPlayerAdapter's convention: __init__ does zero I/O.

    Safe to construct with no arguments -- the real score_source
    (_default_score_source) is only ever invoked when stream() is
    actually iterated, never at construction time.
    """
    adapter = OpenWakeWordAdapter()

    assert adapter is not None
