"""The voice-activity-detection port: the seam between raw audio and confirmed speech.

:class:`VadPort` is the one abstract boundary between "some real
voice-activity-detection model" and the rest of the system. Nothing
outside an adapter implementing this port knows or cares which VAD
model or inference backend actually decides where speech starts and
stops.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.vad`` for the concrete
Silero-VAD-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from jarvis.domain.audio import AudioChunk, Segment


@runtime_checkable
class VadPort(Protocol):
    """A voice-activity detector that splits raw audio into confirmed-speech segments."""

    def segment(self, audio: AudioChunk) -> AsyncIterator[Segment]:
        """Return an async iterator yielding each confirmed-speech segment found in ``audio``.

        ``audio`` is a single, already-captured buffer (e.g. the
        ring-buffered audio following a wake-word trigger), not a live
        stream fed incrementally -- yielding is progressive because
        per-window inference is real work worth not blocking on all at
        once, not because more audio arrives after the call starts.
        Zero, one, or multiple segments may be yielded, depending on
        how many distinct spans of speech (versus silence/noise)
        ``audio`` actually contains. What counts as "confirmed" --
        thresholding, minimum-duration filtering, padding -- is
        entirely the implementing adapter's concern.
        """
        ...
