"""Unit tests for jarvis.application.job_assistance.classification.draft_effect_for.

Satisfies m6b-job-assistance.md's own acceptance criterion 1: a real
test proves the drafting capability's own real Effect classification.
"""

from __future__ import annotations

from jarvis.application.job_assistance.classification import draft_effect_for
from jarvis.domain.capability import Effect
from jarvis.domain.provenance import Classification


def test_secret_maps_to_memory_write() -> None:
    """A real, conservative implementation default -- see this module's own docstring."""
    assert draft_effect_for(Classification.SECRET) is Effect.MEMORY_WRITE


def test_sensitive_maps_to_write_local() -> None:
    assert draft_effect_for(Classification.SENSITIVE) is Effect.WRITE_LOCAL


def test_personal_maps_to_write_local() -> None:
    assert draft_effect_for(Classification.PERSONAL) is Effect.WRITE_LOCAL


def test_public_maps_to_write_local() -> None:
    assert draft_effect_for(Classification.PUBLIC) is Effect.WRITE_LOCAL
