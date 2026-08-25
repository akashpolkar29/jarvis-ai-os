"""Contract test: adapters must structurally satisfy jarvis.ports.clock.ClockPort."""

from __future__ import annotations

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.ports.clock import ClockPort


def test_system_clock_adapter_satisfies_clock_port() -> None:
    """SystemClockAdapter is structurally a ClockPort.

    Safe to construct with no arguments here: __init__ does zero I/O.
    """
    adapter = SystemClockAdapter()

    assert isinstance(adapter, ClockPort)


def test_an_object_missing_now_does_not_satisfy_clock_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAClockSource:
        """Deliberately lacks now()."""

    assert isinstance(NotAClockSource(), ClockPort) is False
