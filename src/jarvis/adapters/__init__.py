"""Adapters ring: concrete implementations of the ports.

Every integration with the outside world — a specific reasoning
provider, a specific storage engine, a specific audio backend — lives
here as an implementation of a ``jarvis.ports`` Protocol. This is the
only ring allowed to name a vendor or a specific technology.

Constraints:

* May depend on ``jarvis.domain``, ``jarvis.ports``, and
  ``jarvis.application`` (to raise/catch application-level exceptions),
  but never on ``jarvis.kernel``, ``jarvis.ipc``, or ``jarvis.cli``.

``ManualConfirmationAdapter`` is the simplest possible implementation
of :class:`~jarvis.ports.confirmation.ConfirmationPort`, reporting
fixed, constructor-supplied confirmation availability rather than any
real presence signal (that's future work).
``JsonFileAuditStorageAdapter`` implements
:class:`~jarvis.ports.audit_storage.AuditStoragePort` as a single
JSON file. ``MprisMediaPlayerAdapter`` implements
:class:`~jarvis.ports.media_player.MediaPlayerPort` by talking MPRIS
over D-Bus to whichever media player is currently running.
``LocalFileSystemAdapter`` implements
:class:`~jarvis.ports.file_system.FileSystemPort` via ``pathlib``.
``OpenWakeWordAdapter`` implements
:class:`~jarvis.ports.wake_word.WakeWordPort` via openWakeWord's tflite
inference path. None of these adapters depend on each other.
"""

from __future__ import annotations

from .audit_storage import JsonFileAuditStorageAdapter
from .confirmation import ManualConfirmationAdapter
from .file_system import LocalFileSystemAdapter
from .media_player import MprisMediaPlayerAdapter
from .wake_word import OpenWakeWordAdapter

__all__ = [
    "JsonFileAuditStorageAdapter",
    "LocalFileSystemAdapter",
    "ManualConfirmationAdapter",
    "MprisMediaPlayerAdapter",
    "OpenWakeWordAdapter",
]
