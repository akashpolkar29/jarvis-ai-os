"""Contract test: adapters must structurally satisfy jarvis.ports.outcome.OutcomeSinkPort."""

from __future__ import annotations

from pathlib import Path

from jarvis.adapters.outcome import JsonLinesOutcomeSinkAdapter
from jarvis.ports.outcome import OutcomeSinkPort


def test_json_lines_outcome_sink_adapter_satisfies_outcome_sink_port() -> None:
    """JsonLinesOutcomeSinkAdapter is structurally an OutcomeSinkPort.

    Safe to construct with a nonexistent path here: __init__ does zero
    I/O (it only stores the path), so no real file needs to exist.
    """
    adapter = JsonLinesOutcomeSinkAdapter(Path("/nonexistent"))

    assert isinstance(adapter, OutcomeSinkPort)


def test_an_object_missing_record_does_not_satisfy_outcome_sink_port() -> None:
    """The isinstance check is meaningful: it actually rejects non-conforming objects."""

    class NotAnOutcomeSink:
        """Deliberately lacks record()."""

    assert isinstance(NotAnOutcomeSink(), OutcomeSinkPort) is False
