"""The wake-word domain event: a signal that a wake phrase was detected.

:class:`WakeEvent` is deliberately not a :class:`~.provenance.Tainted`
value. Tainted exists to track values whose *content* a policy decision
might need to weigh (see ADR-0010) -- a transcript's words, a file's
bytes. A WakeEvent carries no such content of its own: it is a system-
generated "start listening for a command" trigger, not user-supplied
data, and per ADR-0012/ADR-0013 it can never itself satisfy an
authorization tier above what voice already cannot reach. Nothing
about wrapping it in Provenance would change how it is allowed to be
used. Its ``audio`` field is likewise system-captured raw audio, not
yet anything a policy decision weighs -- that only happens once
``SttPort.transcribe()`` produces a ``Tainted[Transcript]`` downstream.

``audio`` was added in ADR-0033: ``VadPort.segment()`` needs real
captured audio to operate on, and ``WakeEvent`` -- not a new port -- is
where that audio is carried from the wake-word adapter to the rest of
the pipeline. See that ADR for why.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .audio import AudioChunk

_MIN_SCORE = 0.0
_MAX_SCORE = 1.0


@dataclass(frozen=True)
class WakeEvent:
    """A confirmed wake-word detection.

    Attributes:
        score: The detection score of the frame that confirmed the
            event, in ``[0.0, 1.0]``. With exactly one supported wake
            phrase, there is nothing else to distinguish one WakeEvent
            from another beyond this and ``audio``. A phrase/label
            field belongs here once multi-wake-phrase support is
            actually needed, not speculatively now.
        audio: The captured audio around the trigger -- pre-trigger
            ring-buffer context plus a brief post-trigger continuation
            (ADR-0033) -- ready to hand to ``VadPort.segment()``.
    """

    score: float
    audio: AudioChunk

    def __post_init__(self) -> None:
        """Validate ``score`` is a real, in-range detection confidence."""
        if not _MIN_SCORE <= self.score <= _MAX_SCORE:
            msg = f"WakeEvent.score must be in [{_MIN_SCORE}, {_MAX_SCORE}]: {self.score!r}"
            raise ValueError(msg)
