"""Unit tests for jarvis.adapters.identifier.UuidIdAdapter.

Unlike most real-hardware adapters in this repo, this one needs no
fake: `uuid.uuid4()` has no live-bus/live-hardware dependency CI
cannot rely on, so its own real behavior is tested directly.
"""

from __future__ import annotations

from jarvis.adapters.identifier import UuidIdAdapter

_GENERATED_ID_COUNT = 100


def test_new_id_returns_a_non_empty_string() -> None:
    """The real identifier is a real, non-empty string."""
    adapter = UuidIdAdapter()

    result = adapter.new_id()

    assert isinstance(result, str)
    assert result != ""


def test_new_id_returns_a_different_value_each_call() -> None:
    """Real, fresh identifiers are unique across many real calls -- not a fixed constant."""
    adapter = UuidIdAdapter()

    ids = {adapter.new_id() for _ in range(_GENERATED_ID_COUNT)}

    assert len(ids) == _GENERATED_ID_COUNT
