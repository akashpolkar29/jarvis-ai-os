"""Unit tests for jarvis.application.memory.classification.memory_effect_for."""

from __future__ import annotations

from jarvis.application.memory.classification import memory_effect_for
from jarvis.domain.capability import Effect
from jarvis.domain.provenance import Classification


def test_secret_maps_to_memory_write() -> None:
    assert memory_effect_for(Classification.SECRET) is Effect.MEMORY_WRITE


def test_sensitive_maps_to_write_local() -> None:
    assert memory_effect_for(Classification.SENSITIVE) is Effect.WRITE_LOCAL


def test_personal_maps_to_write_local() -> None:
    assert memory_effect_for(Classification.PERSONAL) is Effect.WRITE_LOCAL


def test_public_maps_to_write_local() -> None:
    assert memory_effect_for(Classification.PUBLIC) is Effect.WRITE_LOCAL
