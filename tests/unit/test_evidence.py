"""Unit tests for jarvis.domain.evidence."""

from __future__ import annotations

import dataclasses

import pytest

from jarvis.domain.evidence import (
    Attempt,
    Candidate,
    EscalationRung,
    Evidence,
    EvidenceKind,
    Verdict,
)


def test_escalation_rung_is_ordered_cheapest_first() -> None:
    """DETERMINISTIC_FIX < SELF_REPAIR < SECOND_PROVIDER, matching ADR-0022's ordering."""
    assert EscalationRung.DETERMINISTIC_FIX < EscalationRung.SELF_REPAIR
    assert EscalationRung.SELF_REPAIR < EscalationRung.SECOND_PROVIDER


def test_evidence_accepts_valid_construction() -> None:
    """A well-formed Evidence is constructable and its fields round-trip."""
    evidence = Evidence(
        kind=EvidenceKind.VALIDATION_RESULT,
        author="pytest-validator",
        weight=1.0,
        description="The full test suite passed.",
    )
    assert evidence.kind is EvidenceKind.VALIDATION_RESULT
    assert evidence.author == "pytest-validator"
    assert evidence.weight == 1.0
    assert evidence.description == "The full test suite passed."


def test_evidence_accepts_zero_weight() -> None:
    """Zero weight is valid -- e.g. ADR-0025's zero-weighted self-authored test."""
    evidence = Evidence(
        kind=EvidenceKind.VALIDATION_RESULT,
        author="provider-a",
        weight=0.0,
        description="Self-authored, zero-weighted per ADR-0025.",
    )
    assert evidence.weight == 0.0


def test_evidence_rejects_empty_author() -> None:
    """Evidence.author must not be empty."""
    with pytest.raises(ValueError, match=r"Evidence\.author"):
        Evidence(
            kind=EvidenceKind.MODEL_OPINION,
            author="",
            weight=1.0,
            description="An opinion.",
        )


def test_evidence_rejects_empty_description() -> None:
    """Evidence.description must not be empty."""
    with pytest.raises(ValueError, match=r"Evidence\.description"):
        Evidence(
            kind=EvidenceKind.MODEL_OPINION,
            author="provider-a",
            weight=1.0,
            description="",
        )


def test_evidence_rejects_negative_weight() -> None:
    """Evidence.weight must be non-negative."""
    with pytest.raises(ValueError, match=r"Evidence\.weight"):
        Evidence(
            kind=EvidenceKind.MODEL_OPINION,
            author="provider-a",
            weight=-1.0,
            description="An opinion.",
        )


def test_evidence_is_frozen() -> None:
    """Evidence is immutable, matching every other domain value object."""
    evidence = Evidence(
        kind=EvidenceKind.MODEL_OPINION,
        author="provider-a",
        weight=1.0,
        description="An opinion.",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.weight = 0.0  # type: ignore[misc]


def test_candidate_accepts_valid_construction() -> None:
    """A well-formed Candidate is constructable and its fields round-trip."""
    candidate = Candidate(author="provider-a", content="--- a patch ---")
    assert candidate.author == "provider-a"
    assert candidate.content == "--- a patch ---"


def test_candidate_rejects_empty_author() -> None:
    """Candidate.author must not be empty."""
    with pytest.raises(ValueError, match=r"Candidate\.author"):
        Candidate(author="", content="--- a patch ---")


def test_candidate_rejects_empty_content() -> None:
    """Candidate.content must not be empty."""
    with pytest.raises(ValueError, match=r"Candidate\.content"):
        Candidate(author="provider-a", content="")


def test_candidate_is_frozen() -> None:
    """Candidate is immutable, matching every other domain value object."""
    candidate = Candidate(author="provider-a", content="--- a patch ---")
    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.content = "--- a different patch ---"  # type: ignore[misc]


def test_attempt_holds_its_rung_candidate_evidence_and_verdict() -> None:
    """Attempt is a plain, constructable bundle of its four fields."""
    candidate = Candidate(author="provider-a", content="--- a patch ---")
    evidence = (
        Evidence(
            kind=EvidenceKind.VALIDATION_RESULT,
            author="pytest-validator",
            weight=1.0,
            description="The full test suite passed.",
        ),
    )
    attempt = Attempt(
        rung=EscalationRung.SELF_REPAIR,
        candidate=candidate,
        evidence=evidence,
        verdict=Verdict.PASSED,
    )
    assert attempt.rung is EscalationRung.SELF_REPAIR
    assert attempt.candidate is candidate
    assert attempt.evidence == evidence
    assert attempt.verdict is Verdict.PASSED


def test_attempt_accepts_no_evidence_at_all() -> None:
    """An empty evidence tuple is valid -- e.g. an UNVERIFIABLE attempt with nothing to judge it."""
    candidate = Candidate(author="provider-a", content="--- a patch ---")
    attempt = Attempt(
        rung=EscalationRung.DETERMINISTIC_FIX,
        candidate=candidate,
        evidence=(),
        verdict=Verdict.UNVERIFIABLE,
    )
    assert attempt.evidence == ()


def test_attempt_is_frozen() -> None:
    """Attempt is immutable, matching every other domain value object."""
    candidate = Candidate(author="provider-a", content="--- a patch ---")
    attempt = Attempt(
        rung=EscalationRung.DETERMINISTIC_FIX,
        candidate=candidate,
        evidence=(),
        verdict=Verdict.UNVERIFIABLE,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        attempt.verdict = Verdict.FAILED  # type: ignore[misc]
