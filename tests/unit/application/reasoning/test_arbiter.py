"""Unit tests for jarvis.application.reasoning.arbiter.Arbiter.

Deterministic, example-based tests -- guarantees this module's
required 100% branch coverage regardless of what
``tests/property/test_arbiter.py``'s randomized search happens to
generate on a given run.
"""

from __future__ import annotations

import pytest

from jarvis.application.reasoning.arbiter import Arbiter
from jarvis.domain.evidence import (
    Attempt,
    Candidate,
    EscalationRung,
    Evidence,
    EvidenceKind,
    Verdict,
)

_ARBITER = Arbiter()


def _attempt(author: str, evidence: tuple[Evidence, ...]) -> Attempt:
    return Attempt(
        rung=EscalationRung.SECOND_PROVIDER,
        candidate=Candidate(author=author, content=f"{author}'s candidate"),
        evidence=evidence,
        verdict=Verdict.PASSED,
    )


def _validation(author: str, weight: float) -> Evidence:
    return Evidence(
        kind=EvidenceKind.VALIDATION_RESULT, author=author, weight=weight, description="a check"
    )


def _opinion(author: str, weight: float) -> Evidence:
    return Evidence(
        kind=EvidenceKind.MODEL_OPINION, author=author, weight=weight, description="an opinion"
    )


def test_select_raises_on_an_empty_attempts_tuple() -> None:
    with pytest.raises(ValueError, match="requires at least one"):
        _ARBITER.select(())


def test_select_returns_the_only_candidate_when_there_is_no_competition() -> None:
    solo = _attempt("family_a", evidence=())

    assert _ARBITER.select((solo,)) is solo.candidate


def test_select_picks_the_higher_scoring_candidate() -> None:
    weak = _attempt("family_a", evidence=(_validation("build", 1.0),))
    strong = _attempt("family_b", evidence=(_validation("build", 1.0), _validation("pytest", 1.0)))

    assert _ARBITER.select((weak, strong)) is strong.candidate


def test_a_providers_own_validation_evidence_scores_zero_for_its_own_candidate() -> None:
    """ADR-0025: family_a's own self-reported validation doesn't count toward family_a."""
    self_reported = _attempt("family_a", evidence=(_validation("family_a", 100.0),))
    independently_validated = _attempt("family_b", evidence=(_validation("build", 1.0),))

    result = _ARBITER.select((self_reported, independently_validated))

    assert result is independently_validated.candidate


def test_a_providers_own_evidence_still_counts_toward_a_different_candidate() -> None:
    """Author-exclusion is per-candidate, not a blanket ban on that author's evidence."""
    reviewed_by_a = _attempt("family_b", evidence=(_validation("family_a", 1.0),))

    assert _ARBITER.select((reviewed_by_a,)) is reviewed_by_a.candidate


def test_model_opinion_evidence_cannot_tip_a_selection() -> None:
    """Criterion #4: a huge MODEL_OPINION weight still loses to a smaller real validation."""
    all_opinion = _attempt("family_a", evidence=(_opinion("family_b", 1_000_000.0),))
    real_validation = _attempt("family_b", evidence=(_validation("build", 0.1),))

    assert _ARBITER.select((all_opinion, real_validation)) is real_validation.candidate


def test_ties_resolve_to_the_first_attempt_in_order() -> None:
    first = _attempt("family_a", evidence=())
    second = _attempt("family_b", evidence=())

    assert _ARBITER.select((first, second)) is first.candidate
