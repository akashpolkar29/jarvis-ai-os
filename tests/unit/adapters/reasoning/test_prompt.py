"""Unit tests for jarvis.adapters.reasoning._prompt.build_prompt."""

from __future__ import annotations

from jarvis.adapters.reasoning._prompt import build_prompt
from jarvis.domain.evidence import (
    Attempt,
    Candidate,
    EscalationRung,
    Evidence,
    EvidenceKind,
    Verdict,
)


def test_a_first_attempt_returns_the_task_unchanged() -> None:
    assert build_prompt("fix the failing test", ()) == "fix the failing test"


def test_a_prior_attempt_appends_its_candidate_and_verdict() -> None:
    attempt = Attempt(
        rung=EscalationRung.DETERMINISTIC_FIX,
        candidate=Candidate(author="local", content="applied patch X"),
        evidence=(
            Evidence(
                kind=EvidenceKind.VALIDATION_RESULT,
                author="build",
                weight=1.0,
                description="build still fails: missing dependency",
            ),
        ),
        verdict=Verdict.FAILED,
    )

    prompt = build_prompt("fix the failing test", (attempt,))

    assert "fix the failing test" in prompt
    assert "applied patch X" in prompt
    assert "local" in prompt
    assert "failed" in prompt
    assert "missing dependency" in prompt


def test_multiple_prior_attempts_are_folded_in_order() -> None:
    first = Attempt(
        rung=EscalationRung.DETERMINISTIC_FIX,
        candidate=Candidate(author="local", content="first try"),
        evidence=(),
        verdict=Verdict.FAILED,
    )
    second = Attempt(
        rung=EscalationRung.SELF_REPAIR,
        candidate=Candidate(author="local", content="second try"),
        evidence=(),
        verdict=Verdict.FAILED,
    )

    prompt = build_prompt("task", (first, second))

    assert prompt.index("first try") < prompt.index("second try")
