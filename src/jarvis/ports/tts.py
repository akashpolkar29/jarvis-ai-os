"""The text-to-speech port: the seam between recognized text and spoken audio.

:class:`TtsPort` is the one abstract boundary between "some real
text-to-speech model" and the rest of the system. Nothing outside an
adapter implementing this port knows or cares which TTS model or
inference backend actually produces the audio.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.tts`` for the concrete
piper-tts-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.audio import AudioStream


@runtime_checkable
class TtsPort(Protocol):
    """A text-to-speech engine that synthesizes spoken audio from text."""

    async def speak(self, text: str) -> AudioStream:
        """Synthesize ``text`` and return the resulting audio, ready for playback."""
        ...
