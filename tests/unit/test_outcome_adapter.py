"""Unit tests for jarvis.adapters.outcome.JsonLinesOutcomeSinkAdapter.

Nothing is mocked: a real temp file is written and read back, matching
this project's precedent for adapters whose real I/O (here, plain file
appends) is reliable and cheap enough in CI to exercise directly --
see adapters/workspace.py's own docstring for the same reasoning
applied to ``git apply``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from jarvis.adapters.outcome import JsonLinesOutcomeSinkAdapter

if TYPE_CHECKING:
    from pathlib import Path

_EXPECTED_TWO_RECORDED_LINES = 2


def test_record_appends_one_json_line(tmp_path: Path) -> None:
    path = tmp_path / "outcomes.jsonl"
    adapter = JsonLinesOutcomeSinkAdapter(path)

    adapter.record({"rung": "SELF_REPAIR", "latency_seconds": 1.5, "verdict": "passed"})

    lines = path.read_text(encoding="utf-8").splitlines()
    expected = {"rung": "SELF_REPAIR", "latency_seconds": 1.5, "verdict": "passed"}
    assert len(lines) == 1
    assert json.loads(lines[0]) == expected


def test_record_appends_across_multiple_calls_without_overwriting(tmp_path: Path) -> None:
    path = tmp_path / "outcomes.jsonl"
    adapter = JsonLinesOutcomeSinkAdapter(path)

    adapter.record({"rung": "SELF_REPAIR", "latency_seconds": 1.0, "verdict": "failed"})
    adapter.record({"rung": "SECOND_PROVIDER", "latency_seconds": 2.0, "verdict": "passed"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == _EXPECTED_TWO_RECORDED_LINES
    assert json.loads(lines[0])["rung"] == "SELF_REPAIR"
    assert json.loads(lines[1])["rung"] == "SECOND_PROVIDER"


def test_record_creates_the_file_if_it_does_not_exist(tmp_path: Path) -> None:
    path = tmp_path / "does_not_exist_yet.jsonl"
    adapter = JsonLinesOutcomeSinkAdapter(path)

    adapter.record({"rung": "SELF_REPAIR", "latency_seconds": 0.1, "verdict": "passed"})

    assert path.exists()
