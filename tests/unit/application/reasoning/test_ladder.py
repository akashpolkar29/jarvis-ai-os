"""Unit tests for jarvis.application.reasoning.ladder.EscalationLadder.

Deterministic, example-based tests exercising each of ``next_rung``'s
branches directly -- guarantees this module's required 100% branch
coverage (ADR-0041) regardless of what ``tests/property/test_ladder.py``'s
randomized search happens to generate on a given run; the property
tests are the deeper correctness net over arbitrary histories, these
are the coverage guarantee.
"""

from __future__ import annotations

from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.domain.evidence import Attempt, Candidate, EscalationRung, Verdict

_CANDIDATE = Candidate(author="local", content="a candidate")
_LADDER = EscalationLadder()


def _attempt(rung: EscalationRung, verdict: Verdict) -> Attempt:
    return Attempt(rung=rung, candidate=_CANDIDATE, evidence=(), verdict=verdict)


def test_an_empty_history_starts_at_deterministic_fix() -> None:
    assert _LADDER.next_rung(()) is EscalationRung.DETERMINISTIC_FIX


def test_a_passed_deterministic_fix_halts_escalation() -> None:
    history = (_attempt(EscalationRung.DETERMINISTIC_FIX, Verdict.PASSED),)

    assert _LADDER.next_rung(history) is None


def test_a_failed_deterministic_fix_escalates_to_self_repair() -> None:
    history = (_attempt(EscalationRung.DETERMINISTIC_FIX, Verdict.FAILED),)

    assert _LADDER.next_rung(history) is EscalationRung.SELF_REPAIR


def test_an_unverifiable_self_repair_still_escalates_to_second_provider() -> None:
    """UNVERIFIABLE is not success -- escalation continues, same as FAILED would."""
    history = (
        _attempt(EscalationRung.DETERMINISTIC_FIX, Verdict.FAILED),
        _attempt(EscalationRung.SELF_REPAIR, Verdict.UNVERIFIABLE),
    )

    assert _LADDER.next_rung(history) is EscalationRung.SECOND_PROVIDER


def test_a_failed_second_provider_terminates_escalation() -> None:
    history = (
        _attempt(EscalationRung.DETERMINISTIC_FIX, Verdict.FAILED),
        _attempt(EscalationRung.SELF_REPAIR, Verdict.FAILED),
        _attempt(EscalationRung.SECOND_PROVIDER, Verdict.FAILED),
    )

    assert _LADDER.next_rung(history) is None


def test_a_late_pass_halts_escalation_even_with_earlier_failures() -> None:
    history = (
        _attempt(EscalationRung.DETERMINISTIC_FIX, Verdict.FAILED),
        _attempt(EscalationRung.SELF_REPAIR, Verdict.PASSED),
    )

    assert _LADDER.next_rung(history) is None
