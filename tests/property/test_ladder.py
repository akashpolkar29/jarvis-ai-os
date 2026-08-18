"""Property-based tests for jarvis.application.reasoning.ladder.EscalationLadder.

Exercises the five invariants ``ladder.py``'s own module docstring
enumerates, over arbitrary Attempt histories (arbitrary rungs,
candidates, evidence, and verdicts) -- acceptance criterion #1
("Ladder invariants hold under property-based testing over arbitrary
evidence and budgets"). Budgets are deliberately not exercised here:
see ``ladder.py``'s docstring for why budget awareness is out of this
class's scope entirely (deliverable #6, enforced at the dispatcher).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.domain.evidence import (
    Attempt,
    Candidate,
    EscalationRung,
    Evidence,
    EvidenceKind,
    Verdict,
)

CANDIDATES = st.builds(Candidate, author=st.text(min_size=1), content=st.text(min_size=1))
EVIDENCE = st.builds(
    Evidence,
    kind=st.sampled_from(EvidenceKind),
    author=st.text(min_size=1),
    weight=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    description=st.text(min_size=1),
)
RUNGS = st.sampled_from(EscalationRung)
VERDICTS = st.sampled_from(Verdict)
ATTEMPTS = st.builds(
    Attempt,
    rung=RUNGS,
    candidate=CANDIDATES,
    evidence=st.lists(EVIDENCE, max_size=3).map(tuple),
    verdict=VERDICTS,
)
ATTEMPT_HISTORIES = st.lists(ATTEMPTS, max_size=5).map(tuple)

_LADDER = EscalationLadder()


@given(ATTEMPT_HISTORIES)
def test_a_passed_verdict_anywhere_in_history_halts_escalation(
    attempts: tuple[Attempt, ...],
) -> None:
    """Invariant 2: only PASSED halts. A PASSED attempt anywhere always stops the ladder."""
    passed_attempt = Attempt(
        rung=EscalationRung.DETERMINISTIC_FIX,
        candidate=Candidate(author="a", content="c"),
        evidence=(),
        verdict=Verdict.PASSED,
    )
    history_with_a_pass = (*attempts, passed_attempt)

    assert _LADDER.next_rung(history_with_a_pass) is None


def test_the_first_attempt_always_starts_at_deterministic_fix() -> None:
    """Invariant 1: empty history always starts at the cheapest rung."""
    assert _LADDER.next_rung(()) is EscalationRung.DETERMINISTIC_FIX


@given(ATTEMPT_HISTORIES)
def test_next_rung_is_never_lower_than_or_equal_to_any_attempted_rung(
    attempts: tuple[Attempt, ...],
) -> None:
    """Invariant 4: escalation is monotonic -- never revisits or repeats a rung."""
    no_pass = tuple(a for a in attempts if a.verdict is not Verdict.PASSED)
    result = _LADDER.next_rung(no_pass)

    if result is not None and no_pass:
        highest_attempted = max(a.rung for a in no_pass)
        assert result > highest_attempted


@given(ATTEMPT_HISTORIES)
def test_next_rung_never_skips_a_rung(attempts: tuple[Attempt, ...]) -> None:
    """Invariant 3: ADR-0022's fixed order -- the next rung is always exactly one step up."""
    no_pass = tuple(a for a in attempts if a.verdict is not Verdict.PASSED)
    result = _LADDER.next_rung(no_pass)

    if result is not None and no_pass:
        highest_attempted = max(a.rung for a in no_pass)
        assert result == EscalationRung(highest_attempted + 1)


@given(ATTEMPT_HISTORIES)
def test_escalation_stops_once_second_provider_has_been_attempted_without_passing(
    attempts: tuple[Attempt, ...],
) -> None:
    """Invariant 5: escalation is bounded -- nothing exists beyond SECOND_PROVIDER."""
    no_pass = tuple(a for a in attempts if a.verdict is not Verdict.PASSED)
    second_provider_attempt = Attempt(
        rung=EscalationRung.SECOND_PROVIDER,
        candidate=Candidate(author="a", content="c"),
        evidence=(),
        verdict=Verdict.FAILED,
    )
    history = (*no_pass, second_provider_attempt)

    assert _LADDER.next_rung(history) is None
