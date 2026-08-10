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

``authorize_ping`` was this ring's first real content: a one-shot
composition of the registry, storage, confirmation, and orchestrator
pieces built so far, proving they wire together end-to-end.
``authorize_and_run_music_command`` is the first composition whose
authorization decision gates a real, observable side effect (an MPRIS
playback command) rather than a no-op.
"""

from __future__ import annotations

from .music import MusicCommand, authorize_and_run_music_command
from .ping import authorize_ping

__all__ = [
    "MusicCommand",
    "authorize_and_run_music_command",
    "authorize_ping",
]
