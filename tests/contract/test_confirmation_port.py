"""Contract test: adapters must structurally satisfy jarvis.ports.confirmation.ConfirmationPort."""

from __future__ import annotations

from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.ports.confirmation import ConfirmationPort


def test_manual_confirmation_adapter_satisfies_confirmation_port() -> None:
    """ManualConfirmationAdapter is structurally a ConfirmationPort."""
    adapter = ManualConfirmationAdapter(
        physical_confirmation_available=True,
        remote_confirmation_available=False,
    )

    assert isinstance(adapter, ConfirmationPort)


def test_an_object_missing_get_context_does_not_satisfy_confirmation_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAConfirmationSource:
        """Deliberately lacks get_context()."""

    assert isinstance(NotAConfirmationSource(), ConfirmationPort) is False
