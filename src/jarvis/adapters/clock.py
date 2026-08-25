"""Adapters implementing jarvis.ports.clock.ClockPort.

:class:`SystemClockAdapter` wraps the real, current wall-clock time --
the one call in this repo ADR-0054 permits, both by
`tests/meta/test_source_invariants.py`'s own allowlist and by the
`# noqa: TID251` on the one line below. No other file in `src/` may
make this call; ruff's own banned-api rule and the AST-based meta-test
both check this independently.
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClockAdapter:
    """The real system clock, UTC, timezone-aware."""

    def now(self) -> datetime:
        """Return the real, current wall-clock time."""
        return datetime.now(UTC)  # noqa: TID251 -- the one call ClockPort exists to wrap
