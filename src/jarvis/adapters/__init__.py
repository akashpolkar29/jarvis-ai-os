"""Adapters ring: concrete implementations of the ports.

Every integration with the outside world — a specific reasoning
provider, a specific storage engine, a specific audio backend — lives
here as an implementation of a ``jarvis.ports`` Protocol. This is the
only ring allowed to name a vendor or a specific technology.

Constraints:

* May depend on ``jarvis.domain``, ``jarvis.ports``, and
  ``jarvis.application`` (to raise/catch application-level exceptions),
  but never on ``jarvis.kernel``, ``jarvis.ipc``, or ``jarvis.cli``.

``ManualConfirmationAdapter`` is this ring's first real content: the
simplest possible implementation of
:class:`~jarvis.ports.confirmation.ConfirmationPort`, reporting fixed,
constructor-supplied confirmation availability rather than any real
presence signal (that's future work).
"""

from __future__ import annotations

from .confirmation import ManualConfirmationAdapter

__all__ = [
    "ManualConfirmationAdapter",
]
