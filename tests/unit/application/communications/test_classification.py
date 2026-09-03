"""Unit tests for jarvis.application.communications.classification."""

from __future__ import annotations

from jarvis.application.communications.classification import (
    calendar_effect_for,
    egress_effect_for,
)
from jarvis.domain.capability import Effect
from jarvis.domain.provenance import Classification

_MANUAL_ONLY_EFFECT = Effect.DESTRUCTIVE | Effect.IRREVERSIBLE


def test_secret_maps_to_egress_secret() -> None:
    assert egress_effect_for(Classification.SECRET) is Effect.EGRESS_SECRET


def test_sensitive_maps_to_destructive_irreversible() -> None:
    """ADR-0059: never-remote-satisfiable, mirroring git.force_push/memory.forget."""
    assert egress_effect_for(Classification.SENSITIVE) == _MANUAL_ONLY_EFFECT


def test_personal_maps_to_destructive_irreversible() -> None:
    assert egress_effect_for(Classification.PERSONAL) == _MANUAL_ONLY_EFFECT


def test_public_maps_to_destructive_irreversible() -> None:
    assert egress_effect_for(Classification.PUBLIC) == _MANUAL_ONLY_EFFECT


def test_attendee_less_event_is_always_write_local_regardless_of_classification() -> None:
    """git.push's own precedent: an attendee-less event never floors at an egress effect."""
    for classification in Classification:
        assert calendar_effect_for(classification, has_attendees=False) is Effect.WRITE_LOCAL, (
            classification
        )


def test_attendee_bearing_secret_event_maps_to_egress_secret() -> None:
    assert calendar_effect_for(Classification.SECRET, has_attendees=True) is Effect.EGRESS_SECRET


def test_attendee_bearing_non_secret_event_maps_to_destructive_irreversible() -> None:
    """ADR-0059: an attendee-bearing event can only be authorized by physical confirmation."""
    non_secret = (Classification.PUBLIC, Classification.PERSONAL, Classification.SENSITIVE)
    for classification in non_secret:
        assert calendar_effect_for(classification, has_attendees=True) == _MANUAL_ONLY_EFFECT, (
            classification
        )
