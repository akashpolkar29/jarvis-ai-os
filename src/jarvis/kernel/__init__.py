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
``authorize_and_read_file`` is the first composition whose danger
scales with its argument (the path) rather than only its capability's
Effect type -- see its own module docstring for the resulting
pre-authorization scope check and the audit-trail gap it creates.

``build_default_registry`` is the single place every capability jarvis
knows about is declared -- ``authorize_ping``,
``authorize_and_run_music_command``, and ``authorize_and_read_file``
each call it internally rather than constructing their own
descriptors inline. See ``kernel.capabilities`` for why it takes no
injectable registry parameter.
"""

from __future__ import annotations

from .capabilities import build_default_registry
from .files import FileReadOutcome, PathOutsideAllowedScopeError, authorize_and_read_file
from .music import MusicCommand, authorize_and_run_music_command
from .ping import authorize_ping

__all__ = [
    "FileReadOutcome",
    "MusicCommand",
    "PathOutsideAllowedScopeError",
    "authorize_and_read_file",
    "authorize_and_run_music_command",
    "authorize_ping",
    "build_default_registry",
]
