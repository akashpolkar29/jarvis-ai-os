"""The speech-to-text port: the seam between a confirmed-speech segment and recognized text.

:class:`SttPort` is the one abstract boundary between "some real
speech-to-text model" and the rest of the system. Nothing outside an
adapter implementing this port knows or cares which STT model or
inference backend actually produces the transcript.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.stt`` for the concrete
faster-whisper-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.audio import Segment
    from jarvis.domain.provenance import Tainted
    from jarvis.domain.transcript import Transcript


@runtime_checkable
class SttPort(Protocol):
    """A speech-to-text engine that transcribes a confirmed-speech segment."""

    async def transcribe(self, audio: Segment) -> Tainted[Transcript]:
        """Transcribe ``audio`` and return the result tagged with its provenance.

        Per the M1 architecture doc section 4: a spoken command is
        ``Provenance.user()`` (USER_DIRECT trust) -- the same level M0
        already gives typed CLI input, no more and no less. Every
        implementation of this port must tag its result that way, not
        invent a different trust level.
        """
        ...
