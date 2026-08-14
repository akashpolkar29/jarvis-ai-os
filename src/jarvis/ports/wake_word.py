"""The wake-word port: the seam between a real audio source and a WakeEvent stream.

:class:`WakeWordPort` is the one abstract boundary between "some real
source of continuous wake-word detection" (a specific model, a specific
microphone backend) and the rest of the system. Nothing outside an
adapter implementing this port knows or cares which wake-word engine,
inference backend, or audio library actually produces the events.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.wake_word`` for the
concrete openWakeWord-backed adapter that satisfies this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from jarvis.domain.wake_word import WakeEvent


@runtime_checkable
class WakeWordPort(Protocol):
    """A continuous source of wake-word detection events."""

    def stream(self) -> AsyncIterator[WakeEvent]:
        """Return an async iterator yielding one WakeEvent per confirmed detection.

        Runs until the consumer stops iterating (there is no
        fixed-length notion of "done"). What counts as "confirmed" --
        debouncing, thresholding -- is entirely the implementing
        adapter's concern; this port makes no promise about it beyond
        "each yielded WakeEvent is a real detection, not a raw
        per-frame score."
        """
        ...
