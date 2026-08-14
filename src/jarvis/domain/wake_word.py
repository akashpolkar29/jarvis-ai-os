"""The wake-word domain event: a signal that a wake phrase was detected.

:class:`WakeEvent` is deliberately not a :class:`~.provenance.Tainted`
value. Tainted exists to track values whose *content* a policy decision
might need to weigh (see ADR-0010) -- a transcript's words, a file's
bytes. A WakeEvent carries no such content: it is a system-generated
"start listening for a command" trigger, not user-supplied data, and
per ADR-0012/ADR-0013 it can never itself satisfy an authorization tier
above what voice already cannot reach. Nothing about wrapping it in
Provenance would change how it is allowed to be used.
"""

from __future__ import annotations

from dataclasses import dataclass

_MIN_SCORE = 0.0
_MAX_SCORE = 1.0


@dataclass(frozen=True)
class WakeEvent:
    """A confirmed wake-word detection.

    Attributes:
        score: The detection score of the frame that confirmed the
            event, in ``[0.0, 1.0]``. Deliberately the only field for
            now: with exactly one supported wake phrase, there is
            nothing else to distinguish one WakeEvent from another.
            A phrase/label field belongs here once multi-wake-phrase
            support is actually needed, not speculatively now.
    """

    score: float

    def __post_init__(self) -> None:
        """Validate ``score`` is a real, in-range detection confidence."""
        if not _MIN_SCORE <= self.score <= _MAX_SCORE:
            msg = f"WakeEvent.score must be in [{_MIN_SCORE}, {_MAX_SCORE}]: {self.score!r}"
            raise ValueError(msg)
