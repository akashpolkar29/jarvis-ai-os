"""A speech-to-text result as a domain value object.

:class:`Transcript` is deliberately just recognized text -- no
confidence score, no per-word timing. Those belong here once a real
consumer needs them, not speculatively now. What matters for this
project is that :class:`~jarvis.ports.stt.SttPort` never returns a bare
``str``: every transcript is wrapped in
:class:`~.provenance.Tainted` with ``Provenance.user()``, per the M1
architecture doc section 4 -- a spoken command is USER_DIRECT trust,
the same level M0 already gives typed CLI input, no more and no less.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transcript:
    """Recognized text from a speech-to-text result.

    Attributes:
        text: The recognized text. May be empty (a Segment VAD judged
            speech-containing does not guarantee STT recognized any
            words in it).
    """

    text: str
