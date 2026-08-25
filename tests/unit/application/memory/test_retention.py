"""Unit tests for jarvis.application.memory.retention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jarvis.application.memory.retention import (
    DEFAULT_RETENTION,
    compute_write_timestamps,
    exclude_expired_records,
)
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.provenance import Tainted

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _record(identifier: str, expires_at: datetime | None) -> MemoryRecord:
    return MemoryRecord(
        identifier=identifier,
        value=Tainted.user("x"),
        written_at=_NOW,
        expires_at=expires_at,
    )


def test_default_retention_is_90_days() -> None:
    assert timedelta(days=90) == DEFAULT_RETENTION


def test_compute_write_timestamps_reads_the_clock_exactly_once_for_both_fields() -> None:
    clock = _FakeClock(_NOW)

    written_at, expires_at = compute_write_timestamps(clock)

    assert written_at == _NOW
    assert expires_at == _NOW + DEFAULT_RETENTION


def test_exclude_expired_records_removes_a_record_past_its_expiry() -> None:
    expired = _record("mem:1", _NOW - timedelta(seconds=1))
    fresh = _record("mem:2", _NOW + timedelta(days=1))

    result = exclude_expired_records((expired, fresh), _NOW)

    assert result == (fresh,)


def test_exclude_expired_records_never_removes_a_pinned_record() -> None:
    pinned = _record("mem:1", None)

    result = exclude_expired_records((pinned,), _NOW + timedelta(days=36500))

    assert result == (pinned,)


def test_exclude_expired_records_keeps_a_record_expiring_at_exactly_at() -> None:
    """A record's expires_at is exclusive-past, matching MemoryRecord.is_expired()'s own '<=' rule.

    is_expired(at) is True when expires_at <= at, so a record with
    expires_at == at is already considered expired -- this test pins
    down that boundary is inherited correctly, not reinvented here.
    """
    boundary = _record("mem:1", _NOW)

    result = exclude_expired_records((boundary,), _NOW)

    assert result == ()


def test_exclude_expired_records_preserves_order() -> None:
    first = _record("mem:1", _NOW + timedelta(days=1))
    second = _record("mem:2", None)
    third = _record("mem:3", _NOW + timedelta(days=2))

    result = exclude_expired_records((first, second, third), _NOW)

    assert [record.identifier for record in result] == ["mem:1", "mem:2", "mem:3"]
