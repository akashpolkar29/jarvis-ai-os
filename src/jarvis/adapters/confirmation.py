"""Adapters implementing jarvis.ports.confirmation.ConfirmationPort.

:class:`ManualConfirmationAdapter` is the simplest possible
implementation: the two booleans a ``PolicyContext`` needs are supplied
directly at construction time (e.g. from a CLI flag) rather than
discovered from any real presence signal. Real presence/hardware
detection is future work -- this adapter exists so the port has at
least one concrete implementation, and so tests and a future CLI have
something real to construct a ``PolicyContext`` from instead of
building one directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.domain.policy import PolicyContext


@dataclass(frozen=True)
class ManualConfirmationAdapter:
    """Reports fixed, constructor-supplied confirmation-channel availability.

    Attributes:
        physical_confirmation_available: Whether a human is physically
            present to confirm a MANUAL_ONLY action.
        remote_confirmation_available: Whether a CONFIRM-tier action
            can be confirmed remotely.
    """

    physical_confirmation_available: bool
    remote_confirmation_available: bool

    def get_context(self) -> PolicyContext:
        """Return a PolicyContext built from the constructor-supplied booleans."""
        return PolicyContext(
            physical_confirmation_available=self.physical_confirmation_available,
            remote_confirmation_available=self.remote_confirmation_available,
        )
