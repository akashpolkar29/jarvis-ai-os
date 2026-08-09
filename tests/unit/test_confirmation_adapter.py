"""Unit tests for jarvis.adapters.confirmation.ManualConfirmationAdapter."""

from __future__ import annotations

from jarvis.adapters.confirmation import ManualConfirmationAdapter


def test_get_context_returns_the_constructor_supplied_booleans() -> None:
    """get_context() carries exactly the booleans passed to the constructor."""
    adapter = ManualConfirmationAdapter(
        physical_confirmation_available=True,
        remote_confirmation_available=False,
    )

    context = adapter.get_context()

    assert context.physical_confirmation_available is True
    assert context.remote_confirmation_available is False


def test_get_context_returns_the_constructor_supplied_booleans_inverted() -> None:
    """The other boolean combination is also carried through faithfully, not hardcoded."""
    adapter = ManualConfirmationAdapter(
        physical_confirmation_available=False,
        remote_confirmation_available=True,
    )

    context = adapter.get_context()

    assert context.physical_confirmation_available is False
    assert context.remote_confirmation_available is True
