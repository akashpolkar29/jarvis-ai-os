"""Memory domain types: kept minimal, reusing existing provenance vocabulary.

:class:`MemoryRecord` is the one new domain type M4 needs -- a
provenance-tagged, persistable unit of memory (ADR-0048). No new
``Trust``/``Classification`` vocabulary is introduced here:
``jarvis.domain.provenance``'s existing types are reused exactly,
matching ``jarvis.domain.desktop``'s own precedent for
``WindowHandle``/``SyntheticInputSession``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from .provenance import Tainted


@dataclass(frozen=True)
class MemoryRecord:
    """One real, stored, provenance-tagged memory (ADR-0048).

    Attributes:
        identifier: A real, stable identifier for this record (from
            ``IdPort``, ADR-0054) -- opaque to callers, the same
            "adapter-issued, caller treats as opaque" shape
            ``WindowHandle.value`` already established.
        value: The memorized value, with its own real, unmodified
            ``Provenance`` attached. Never re-wrapped with a fresh,
            unclassified provenance when this record is later read
            back (ADR-0050) -- doing so would silently discard the
            classification this whole milestone's safety story depends
            on.
        written_at: The real wall-clock time this record was written
            (from ``ClockPort``, ADR-0054) -- never computed via
            ``datetime.now()`` directly anywhere this type is
            constructed.
        expires_at: The real wall-clock time this record stops being
            returned by ``RetrievalPort.retrieve()`` (ADR-0051).
            ``None`` means pinned -- retained indefinitely until
            explicitly un-pinned or otherwise deleted, not a separate
            boolean flag alongside this one (one field, one meaning,
            per this project's own minimalism).
    """

    identifier: str
    value: Tainted[object]
    written_at: datetime
    expires_at: datetime | None

    def __post_init__(self) -> None:
        """Validate ``identifier`` is non-empty, matching ``WindowHandle``'s own rule."""
        if not self.identifier:
            msg = "MemoryRecord.identifier must not be empty."
            raise ValueError(msg)

    def is_expired(self, at: datetime) -> bool:
        """Return whether this record has expired as of ``at``.

        A pinned record (``expires_at is None``) is never expired.
        ``at`` is caller-supplied (from a real ``ClockPort``) rather
        than computed internally -- this method stays a pure function
        of its own state, matching this project's own "no wall-clock
        access outside an injected ``ClockPort``" invariant even for
        domain-layer comparisons.
        """
        return self.expires_at is not None and self.expires_at <= at
