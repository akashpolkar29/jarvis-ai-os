"""The confirmation port: the seam between a real confirmation source and PolicyContext.

:class:`ConfirmationPort` is the one abstract boundary between "some real
source of confirmation-channel availability" (a future presence sensor, a
CLI flag, a notification-ack webhook) and
:class:`~jarvis.domain.policy.PolicyContext`, the value the policy engine
actually consumes. Nothing in ``domain`` or ``application`` constructs a
``PolicyContext`` from anything other than a ``ConfirmationPort`` (or, in
tests, a literal fixture standing in for one).

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.confirmation`` for the
concrete adapters that satisfy this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.policy import PolicyContext


@runtime_checkable
class ConfirmationPort(Protocol):
    """A source of the environment facts a policy Decision is made under."""

    def get_context(self) -> PolicyContext:
        """Return the current confirmation-channel availability as a PolicyContext."""
        ...
