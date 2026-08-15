"""The physical confirmation port: the Finding 2 closure (docs/threat-model/v0.md).

M0's threat model ended with an honest admission: CONFIRM and
MANUAL_ONLY provided identical real-world protection, because the only
:class:`~jarvis.ports.confirmation.ConfirmationPort` adapter that
existed (``ManualConfirmationAdapter``) just echoed back a
constructor-supplied boolean -- anyone who could run the process could
claim physical presence and have it accepted at face value.

:class:`PhysicalConfirmationPort` is deliberately a *different* port
from :class:`~jarvis.ports.confirmation.ConfirmationPort`, not a new
adapter for it, because the two answer different questions:

* ``ConfirmationPort.get_context()`` is a cheap, synchronous query --
  "what confirmation channels are available right now" -- and its
  result is what :class:`~jarvis.domain.policy.PolicyContext` is built
  from.
* ``PhysicalConfirmationPort.await_physical_confirmation()`` is an
  async, blocking, per-action prompt -- "does a real human, right now,
  physically approve *this specific* request" -- backed by a genuine
  keypress or click on a screen (ADR-0013: physical interaction, not
  voice, is the real authorization boundary; ADR-0041).

A caller (``kernel/voice_loop.py``, WP-25) uses this port's answer to
construct the ``PolicyContext`` it then passes to
``AuthorizationOrchestrator.authorize_by_id()``, exactly as it would
from any other ``ConfirmationPort``-backed source.
:class:`~jarvis.application.policy.orchestrator.AuthorizationOrchestrator`
itself is not changed to know this port exists -- it stays exactly
what M0 built, taking a ``PolicyContext`` it did not construct.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PhysicalConfirmationPort(Protocol):
    """A source of a genuine, per-action physical approval or denial."""

    async def await_physical_confirmation(self, prompt: str, timeout_s: float) -> bool:
        """Block until a human physically approves or denies ``prompt``, or ``timeout_s`` elapses.

        Args:
            prompt: A human-readable description of the action being
                confirmed, shown to the user.
            timeout_s: How long to wait for a response before treating
                the request as denied.

        Returns:
            ``True`` only if a genuine physical action -- a keypress or
            click from a real input device -- approved the request
            before the timeout. ``False`` on denial, timeout, or
            dialog dismissal: denial is always the fail-closed default.
        """
        ...
