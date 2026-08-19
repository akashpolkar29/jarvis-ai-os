"""Unit tests for jarvis.application.reasoning.outcome_logger.Outcome/OutcomeLogger."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.application.reasoning.outcome_logger import Outcome, OutcomeLogger
from jarvis.domain.evidence import EscalationRung, Verdict

if TYPE_CHECKING:
    from collections.abc import Mapping


class _FakeSink:
    """A minimal, test-local stand-in OutcomeSinkPort, recording every entry it receives."""

    def __init__(self) -> None:
        self.recorded: list[Mapping[str, object]] = []

    def record(self, entry: Mapping[str, object]) -> None:
        self.recorded.append(entry)


def test_outcome_rejects_a_negative_latency() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        Outcome(rung=EscalationRung.SELF_REPAIR, latency_seconds=-1.0, verdict=Verdict.FAILED)


def test_outcome_logger_records_a_plain_json_serializable_entry() -> None:
    sink = _FakeSink()
    logger = OutcomeLogger(sink)
    outcome = Outcome(
        rung=EscalationRung.SECOND_PROVIDER, latency_seconds=2.5, verdict=Verdict.PASSED
    )

    logger.record(outcome)

    assert sink.recorded == [
        {"rung": "SECOND_PROVIDER", "latency_seconds": 2.5, "verdict": "passed"}
    ]


def test_outcome_logger_entry_has_exactly_the_three_authorized_fields() -> None:
    """Structural enforcement of ADR-0039: nothing beyond rung/latency/verdict can leak in."""
    sink = _FakeSink()
    logger = OutcomeLogger(sink)
    outcome = Outcome(
        rung=EscalationRung.DETERMINISTIC_FIX, latency_seconds=0.0, verdict=Verdict.FAILED
    )

    logger.record(outcome)

    assert set(sink.recorded[0].keys()) == {"rung", "latency_seconds", "verdict"}
