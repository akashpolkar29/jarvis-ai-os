"""Ports ring: the abstract boundaries the domain and application depend on.

A port is a ``typing.Protocol`` describing a capability the outside world
must provide (a clock, an id generator, a reasoning provider, storage,
audio capture, and so on) without naming which concrete implementation
supplies it. Concrete implementations live in ``jarvis.adapters``.

Constraints:

* No vendor names (ADR-0021). A port describes a role, never a
  specific integration.
* May depend on ``jarvis.domain`` only.

``ConfirmationPort`` is the seam between a real confirmation source
and :class:`~jarvis.domain.policy.PolicyContext`. ``AuditStoragePort``
is the seam between an :class:`~jarvis.domain.audit.AuditChain` and
durable storage. ``MediaPlayerPort`` is the seam between an authorized
playback command and a real, currently-running media player.
``FileSystemPort`` is the seam between an authorized read and a real
file on disk. ``WakeWordPort`` is the seam between a real audio source
and a stream of confirmed wake-word detection events. ``VadPort`` is
the seam between raw audio and confirmed-speech segments. ``SttPort``
is the seam between a confirmed-speech segment and recognized text.
``TtsPort`` is the seam between recognized text and synthesized,
playable audio. ``SpeakerIdPort`` is the seam between a confirmed-
speech segment and a speaker-verification signal -- audit/UX only,
never an authorization input (ADR-0012). ``PhysicalConfirmationPort``
is the seam between a specific, in-flight request and a genuine
physical approval or denial of it -- the Finding 2 closure
(docs/threat-model/v0.md); distinct from ``ConfirmationPort``, see
that module's own docstring for why. ``ReasoningPort`` is the seam
between a task description and a reasoning provider's proposed
Candidate (M2). ``ValidationPort`` is the seam between a Candidate and
ground-truth judgement of it -- a build, a test run, a static
analyzer, or any other real check (M2).
"""

from __future__ import annotations

from .audit_storage import AuditStoragePort
from .confirmation import ConfirmationPort
from .file_system import FileSystemPort
from .media_player import MediaPlayerCommandFailedError, MediaPlayerPort, NoMediaPlayerRunningError
from .physical_confirmation import PhysicalConfirmationPort
from .reasoning import ReasoningPort
from .speaker_id import SpeakerIdPort
from .stt import SttPort
from .tts import TtsPort
from .vad import VadPort
from .validation import ValidationPort
from .wake_word import WakeWordPort

__all__ = [
    "AuditStoragePort",
    "ConfirmationPort",
    "FileSystemPort",
    "MediaPlayerCommandFailedError",
    "MediaPlayerPort",
    "NoMediaPlayerRunningError",
    "PhysicalConfirmationPort",
    "ReasoningPort",
    "SpeakerIdPort",
    "SttPort",
    "TtsPort",
    "VadPort",
    "ValidationPort",
    "WakeWordPort",
]
