"""A speaker-verification result as a domain value object.

:class:`SpeakerScore` is an audit/UX signal ONLY -- per ADR-0012, voice
and speaker verification are a convenience filter, never an
authorization boundary. Nothing in this project may ever use a
SpeakerScore to satisfy a :class:`~.policy.PolicyContext` field; see
``tests/meta/test_speaker_id_isolation.py`` for the mechanical
guarantee that no module under ``src/jarvis`` ever references both
PolicyContext-related code and SpeakerScore/SpeakerIdPort together --
this is not just a comment, it's an enforced trip-wire.
"""

from __future__ import annotations

from dataclasses import dataclass

_MIN_CONFIDENCE = 0.0
_MAX_CONFIDENCE = 1.0


@dataclass(frozen=True)
class SpeakerScore:
    """A speaker-verification result. Audit/UX signal only -- see ADR-0012.

    Attributes:
        verified: Whether the speaker was recognized as the enrolled
            user. Always ``False`` from WP-23's stub adapter -- no
            real speaker-embedding/enrollment model exists yet, per
            the M1 architecture doc's own recommendation (section 11,
            open question 4): since this output is explicitly
            non-authoritative, building a real model isn't justified
            until a real consumer needs it.
        confidence: A confidence value in ``[0.0, 1.0]``. Always
            ``0.0`` from WP-23's stub adapter.
    """

    verified: bool
    confidence: float

    def __post_init__(self) -> None:
        """Validate ``confidence`` is a real, in-range value."""
        if not _MIN_CONFIDENCE <= self.confidence <= _MAX_CONFIDENCE:
            msg = (
                f"SpeakerScore.confidence must be in [{_MIN_CONFIDENCE}, {_MAX_CONFIDENCE}]: "
                f"{self.confidence!r}"
            )
            raise ValueError(msg)
