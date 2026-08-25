"""Unit tests for jarvis.adapters.clock.SystemClockAdapter.

Unlike most real-hardware adapters in this repo, this one needs no
fake: `datetime.now(UTC)` has no live-bus/live-hardware dependency CI
cannot rely on, so its own real behavior is tested directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jarvis.adapters.clock import SystemClockAdapter


def test_now_returns_a_timezone_aware_utc_datetime() -> None:
    """The real clock's result is timezone-aware, not a naive datetime."""
    adapter = SystemClockAdapter()

    result = adapter.now()

    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_now_is_close_to_the_real_current_time() -> None:
    """A real, sane sanity bound -- not exactly equal (that would be flaky), just close."""
    adapter = SystemClockAdapter()
    before = datetime.now(UTC)  # noqa: TID251 -- the test's own independent reference point

    result = adapter.now()

    after = datetime.now(UTC)  # noqa: TID251 -- the test's own independent reference point
    assert before <= result <= after
