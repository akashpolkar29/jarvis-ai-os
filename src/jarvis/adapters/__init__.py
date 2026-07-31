"""Adapters ring: concrete implementations of the ports.

Every integration with the outside world — a specific reasoning
provider, a specific storage engine, a specific audio backend — lives
here as an implementation of a ``jarvis.ports`` Protocol. This is the
only ring allowed to name a vendor or a specific technology.

Constraints:

* May depend on ``jarvis.domain``, ``jarvis.ports``, and
  ``jarvis.application`` (to raise/catch application-level exceptions),
  but never on ``jarvis.kernel``, ``jarvis.ipc``, or ``jarvis.cli``.
"""
