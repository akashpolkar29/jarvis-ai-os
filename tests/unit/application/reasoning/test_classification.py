"""Unit tests for jarvis.application.reasoning.classification.egress_effect_for."""

from __future__ import annotations

from jarvis.application.reasoning.classification import egress_effect_for
from jarvis.domain.capability import Effect
from jarvis.domain.provenance import Classification


def test_secret_maps_to_egress_secret() -> None:
    assert egress_effect_for(Classification.SECRET) is Effect.EGRESS_SECRET


def test_sensitive_maps_to_egress_sensitive() -> None:
    assert egress_effect_for(Classification.SENSITIVE) is Effect.EGRESS_SENSITIVE


def test_personal_maps_to_egress_sensitive() -> None:
    """No ALLOW-tier external-egress effect exists -- fails closed to CONFIRM (ADR-0016)."""
    assert egress_effect_for(Classification.PERSONAL) is Effect.EGRESS_SENSITIVE


def test_public_maps_to_egress_sensitive() -> None:
    """Even PUBLIC data floors at CONFIRM for real cloud egress -- no lower option exists."""
    assert egress_effect_for(Classification.PUBLIC) is Effect.EGRESS_SENSITIVE
