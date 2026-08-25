"""Unit tests for jarvis.domain.memory.MemoryRecord."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from jarvis.domain.memory import MemoryRecord
from jarvis.domain.provenance import Tainted

_WRITTEN_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _record(expires_at: datetime | None) -> MemoryRecord:
    return MemoryRecord(
        identifier="mem:1",
        value=Tainted.user("prefers tabs"),
        written_at=_WRITTEN_AT,
        expires_at=expires_at,
    )


def test_memory_record_stores_all_fields_unchanged() -> None:
    """A valid MemoryRecord stores every field exactly as given."""
    expires_at = _WRITTEN_AT + timedelta(days=90)
    record = _record(expires_at)

    assert record.identifier == "mem:1"
    assert record.value.value == "prefers tabs"
    assert record.written_at == _WRITTEN_AT
    assert record.expires_at == expires_at


def test_memory_record_rejects_an_empty_identifier() -> None:
    """An empty identifier is rejected at construction time, matching WindowHandle's own rule."""
    with pytest.raises(ValueError, match="identifier must not be empty"):
        MemoryRecord(
            identifier="", value=Tainted.user("x"), written_at=_WRITTEN_AT, expires_at=None
        )


def test_is_expired_is_false_before_expires_at() -> None:
    """A record is not expired strictly before its own expires_at."""
    record = _record(_WRITTEN_AT + timedelta(days=90))

    assert record.is_expired(_WRITTEN_AT + timedelta(days=89)) is False


def test_is_expired_is_true_at_or_after_expires_at() -> None:
    """A record is expired at, or any time after, its own expires_at."""
    expires_at = _WRITTEN_AT + timedelta(days=90)
    record = _record(expires_at)

    assert record.is_expired(expires_at) is True
    assert record.is_expired(expires_at + timedelta(seconds=1)) is True


def test_is_expired_is_always_false_when_pinned() -> None:
    """A pinned record (expires_at=None) is never expired, no matter how far in the future."""
    record = _record(None)

    assert record.is_expired(_WRITTEN_AT + timedelta(days=36500)) is False
