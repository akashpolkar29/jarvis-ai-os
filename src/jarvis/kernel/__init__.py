"""Kernel ring: the composition root.

The kernel is where concrete adapters, ports, and application use cases
are wired together into a running system. It is the one place allowed
to know about every other ring at once; nothing outside the kernel
performs this wiring.

Constraints:

* May depend on ``jarvis.domain``, ``jarvis.ports``,
  ``jarvis.application``, and ``jarvis.adapters``.
* Never imports ``jarvis.ipc`` or ``jarvis.cli`` (those depend on the
  kernel, not the reverse).
"""
