"""Adapters implementing jarvis.ports.speaker_id.SpeakerIdPort.

:class:`UnverifiedSpeakerIdAdapter` is a deliberate stub, not a
placeholder standing in for unfinished work: per the M1 architecture
doc's own recommendation (section 11, open question 4), building a
real speaker-embedding/enrollment model is explicitly deferred, since
``SpeakerIdPort``'s output is non-authoritative by design (ADR-0012)
-- it only ever affects audit logging and UX tone, never a security
decision. Anyone saying the wake phrase wakes the system; this is not
a gap to close later, it is the correct behavior this port's contract
already promises (see also ADR-0013: physical interaction, not voice,
is the real authorization boundary).

Always returns ``SpeakerScore(verified=False, confidence=0.0)`` -- no
model, no enrollment, no I/O of any kind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.domain.speaker_id import SpeakerScore

if TYPE_CHECKING:
    from jarvis.domain.audio import Segment

_UNVERIFIED = SpeakerScore(verified=False, confidence=0.0)


class UnverifiedSpeakerIdAdapter:
    """Always reports an unverified speaker -- no real model, per WP-23's deliberate scope."""

    def score(self, audio: Segment) -> SpeakerScore:
        """Return SpeakerScore(verified=False, confidence=0.0), ignoring ``audio`` entirely."""
        del audio  # deliberately unused -- see module docstring
        return _UNVERIFIED
