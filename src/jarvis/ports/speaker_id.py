"""The speaker-identification port: audio in, an audit/UX signal out -- never authorization.

:class:`SpeakerIdPort` is the one abstract boundary between "some real
(or stubbed) speaker-verification model" and the rest of the system.

Per ADR-0012, its output is an audit/UX signal only, never an
authorization input -- see ``tests/meta/test_speaker_id_isolation.py``
for the mechanical guarantee this cannot be violated by accident: no
module under ``src/jarvis`` may ever reference both
:class:`~jarvis.domain.policy.PolicyContext`-related code and
:class:`~jarvis.domain.speaker_id.SpeakerScore`/``SpeakerIdPort``
together.

This module contains no logic -- a ``Protocol`` describes a role, it
does not implement one. See ``jarvis.adapters.speaker_id`` for the
concrete stub adapter that satisfies this port (WP-23 deliberately
stubs this rather than building a real speaker-embedding model -- see
that module's docstring for why).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jarvis.domain.audio import Segment
    from jarvis.domain.speaker_id import SpeakerScore


@runtime_checkable
class SpeakerIdPort(Protocol):
    """A speaker-verification signal source. Audit/UX only -- never an authorization input."""

    def score(self, audio: Segment) -> SpeakerScore:
        """Return a speaker-verification result for ``audio``. Audit/UX signal only (ADR-0012)."""
        ...
