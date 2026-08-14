"""Ports ring: the abstract boundaries the domain and application depend on.

A port is a ``typing.Protocol`` describing a capability the outside world
must provide (a clock, an id generator, a reasoning provider, storage,
audio capture, and so on) without naming which concrete implementation
supplies it. Concrete implementations live in ``jarvis.adapters``.

Constraints:

* No vendor names (no "openai", "anthropic", "chatgpt", "claude", "gpt").
  A port describes a role, never a specific integration.
* May depend on ``jarvis.domain`` only.

``ConfirmationPort`` is the seam between a real confirmation source
and :class:`~jarvis.domain.policy.PolicyContext`. ``AuditStoragePort``
is the seam between an :class:`~jarvis.domain.audit.AuditChain` and
durable storage. ``MediaPlayerPort`` is the seam between an authorized
playback command and a real, currently-running media player.
``FileSystemPort`` is the seam between an authorized read and a real
file on disk. ``WakeWordPort`` is the seam between a real audio source
and a stream of confirmed wake-word detection events.
"""

from __future__ import annotations

from .audit_storage import AuditStoragePort
from .confirmation import ConfirmationPort
from .file_system import FileSystemPort
from .media_player import MediaPlayerCommandFailedError, MediaPlayerPort, NoMediaPlayerRunningError
from .wake_word import WakeWordPort

__all__ = [
    "AuditStoragePort",
    "ConfirmationPort",
    "FileSystemPort",
    "MediaPlayerCommandFailedError",
    "MediaPlayerPort",
    "NoMediaPlayerRunningError",
    "WakeWordPort",
]
