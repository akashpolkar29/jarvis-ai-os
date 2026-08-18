"""Property-based tests for jarvis.application.reasoning.arbiter.Arbiter.

Exercises acceptance criteria #2 ("Arbiter output is byte-identical to
one input candidate, always"), #3 ("A test authored by provider X
contributes zero weight when scoring X's own candidate"), and #4
("MODEL_OPINION evidence can never change a selection") over arbitrary
attempts.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.reasoning.arbiter import Arbiter
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
WEIGHTS = st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False)
ATTEMPTS = st.builds(
    Attempt,
    rung=st.sampled_from(EscalationRung),
    candidate=CANDIDATES,
    evidence=st.lists(EVIDENCE, max_size=4).map(tuple),
    verdict=st.sampled_from(Verdict),
)
NONEMPTY_ATTEMPT_LISTS = st.lists(ATTEMPTS, min_size=1, max_size=6).map(tuple)

_ARBITER = Arbiter()


def _score(attempt: Attempt) -> float:
    return Arbiter._score(attempt)


@given(NONEMPTY_ATTEMPT_LISTS)
def test_select_always_returns_one_input_candidate_unmodified(
    attempts: tuple[Attempt, ...],
) -> None:
    """Criterion #2: never a merge -- the result is always one input candidate, by identity."""
    result = _ARBITER.select(attempts)

    assert any(result is attempt.candidate for attempt in attempts)


@given(CANDIDATES, WEIGHTS)
def test_self_authored_validation_evidence_never_affects_the_score(
    candidate: Candidate, weight: float
) -> None:
    """Criterion #3: an attempt's own author gets zero weight scoring its own candidate."""
    self_authored = Evidence(
        kind=EvidenceKind.VALIDATION_RESULT,
        author=candidate.author,
        weight=weight,
        description="self-reported",
    )
    without = Attempt(
        rung=EscalationRung.SECOND_PROVIDER,
        candidate=candidate,
        evidence=(),
        verdict=Verdict.PASSED,
    )
    with_self_authored = Attempt(
        rung=EscalationRung.SECOND_PROVIDER,
        candidate=candidate,
        evidence=(self_authored,),
        verdict=Verdict.PASSED,
    )

    assert _score(without) == _score(with_self_authored)


@given(CANDIDATES, st.text(min_size=1), WEIGHTS)
def test_model_opinion_evidence_never_affects_the_score(
    candidate: Candidate, other_author: str, weight: float
) -> None:
    """Criterion #4: MODEL_OPINION evidence contributes zero weight, regardless of author."""
    opinion = Evidence(
        kind=EvidenceKind.MODEL_OPINION, author=other_author, weight=weight, description="opinion"
    )
    without = Attempt(
        rung=EscalationRung.SECOND_PROVIDER,
        candidate=candidate,
        evidence=(),
        verdict=Verdict.PASSED,
    )
    with_opinion = Attempt(
        rung=EscalationRung.SECOND_PROVIDER,
        candidate=candidate,
        evidence=(opinion,),
        verdict=Verdict.PASSED,
    )

    assert _score(without) == _score(with_opinion)
