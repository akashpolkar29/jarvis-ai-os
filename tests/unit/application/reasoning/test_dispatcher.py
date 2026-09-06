"""Unit tests for jarvis.application.reasoning.dispatcher.Dispatcher.

Uses real EscalationLadder/Arbiter/ModelRouter/AuthorizationOrchestrator
-- only the ReasoningPort/ValidationPort adapters are faked, since
those are the actual I/O boundary this dispatcher orchestrates around,
matching WP-31/WP-33's own contract-test fakes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.application.reasoning.arbiter import Arbiter
from jarvis.application.reasoning.dispatcher import Dispatcher
from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audit import AuditChain
from jarvis.domain.evidence import Candidate, EscalationRung, Evidence, EvidenceKind, Verdict
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import ProviderProfile, TaskBudget
from jarvis.domain.registry import CapabilityRegistry

if TYPE_CHECKING:
    from jarvis.domain.evidence import Attempt

_EXPECTED_STUB_PLUS_ONE_REAL_ATTEMPT = 2

_NO_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False, remote_confirmation_available=False
)
_FULL_CONFIRMATION = PolicyContext(
    physical_confirmation_available=True, remote_confirmation_available=True
)

_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_FAMILY_A_PROFILE = ProviderProfile(name="family_a", is_local=False)
_FAMILY_B_PROFILE = ProviderProfile(name="family_b", is_local=False)


class _FakeReasoningProvider:
    """A minimal, test-local ReasoningPort, always returning a fixed Candidate."""

    def __init__(self, author: str) -> None:
        self._author = author

    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        candidate = Candidate(author=self._author, content=f"{self._author}: {task}")
        return Tainted(candidate, Provenance.system())


class _FakeValidator:
    """A minimal, test-local ValidationPort, always returning a fixed Verdict."""

    def __init__(self, verdict: Verdict) -> None:
        self._verdict = verdict

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        evidence = Evidence(
            kind=EvidenceKind.VALIDATION_RESULT,
            author="fake-validator",
            weight=1.0,
            description=f"Fake check of {candidate.author}'s candidate.",
        )
        return (self._verdict, (evidence,))


def _task(classification: Classification = Classification.PUBLIC) -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted("do the task", provenance)


def _dispatcher(
    validator: _FakeValidator,
    self_repair: tuple[tuple[ProviderProfile, _FakeReasoningProvider], ...] = (),
    second_provider: tuple[tuple[ProviderProfile, _FakeReasoningProvider], ...] = (),
) -> Dispatcher:
    router = ModelRouter(
        AuthorizationOrchestrator(AuditChain(), CapabilityRegistry(), clock=SystemClockAdapter())
    )
    providers = {
        EscalationRung.SELF_REPAIR: self_repair,
        EscalationRung.SECOND_PROVIDER: second_provider,
    }
    return Dispatcher(EscalationLadder(), Arbiter(), router, validator, providers)


async def test_an_immediately_exhausted_budget_returns_no_attempts() -> None:
    dispatcher = _dispatcher(_FakeValidator(Verdict.PASSED))
    exhausted = TaskBudget(limit=0, spent=0)

    result = await dispatcher.run(_task(), exhausted, _NO_CONFIRMATION)

    assert result.attempts == ()
    assert result.budget.is_exhausted


async def test_deterministic_fix_is_recorded_as_a_failed_no_op_and_spends_no_budget() -> None:
    dispatcher = _dispatcher(
        _FakeValidator(Verdict.PASSED),
        self_repair=((_LOCAL_PROFILE, _FakeReasoningProvider("local")),),
    )

    result = await dispatcher.run(_task(), TaskBudget(limit=10), _NO_CONFIRMATION)

    assert result.attempts[0].rung is EscalationRung.DETERMINISTIC_FIX
    assert result.attempts[0].verdict is Verdict.FAILED
    assert result.budget.spent == 1  # only the real SELF_REPAIR attempt spent budget


async def test_a_passed_self_repair_attempt_stops_the_run() -> None:
    dispatcher = _dispatcher(
        _FakeValidator(Verdict.PASSED),
        self_repair=((_LOCAL_PROFILE, _FakeReasoningProvider("local")),),
        second_provider=((_FAMILY_A_PROFILE, _FakeReasoningProvider("family_a")),),
    )

    result = await dispatcher.run(_task(), TaskBudget(limit=10), _NO_CONFIRMATION)

    assert result.attempts[-1].rung is EscalationRung.SELF_REPAIR
    assert result.attempts[-1].verdict is Verdict.PASSED
    # DETERMINISTIC_FIX stub, then the passing SELF_REPAIR attempt
    assert len(result.attempts) == _EXPECTED_STUB_PLUS_ONE_REAL_ATTEMPT


async def test_escalates_through_every_rung_and_stops_when_exhausted_unpassed() -> None:
    dispatcher = _dispatcher(
        _FakeValidator(Verdict.FAILED),
        self_repair=((_LOCAL_PROFILE, _FakeReasoningProvider("local")),),
        second_provider=((_FAMILY_A_PROFILE, _FakeReasoningProvider("family_a")),),
    )

    # Full confirmation: this test exercises the real generate/validate path at every
    # rung, not policy denial -- SECOND_PROVIDER's cloud call needs a real CONFIRM grant
    # to reach the fake validator at all (ADR-0015).
    result = await dispatcher.run(_task(), TaskBudget(limit=10), _FULL_CONFIRMATION)

    rungs = [attempt.rung for attempt in result.attempts]
    assert rungs == [
        EscalationRung.DETERMINISTIC_FIX,
        EscalationRung.SELF_REPAIR,
        EscalationRung.SECOND_PROVIDER,
    ]
    assert result.attempts[-1].verdict is Verdict.FAILED
    assert not result.budget.is_exhausted


async def test_second_provider_selects_a_winner_via_the_real_arbiter() -> None:
    dispatcher = _dispatcher(
        _FakeValidator(Verdict.PASSED),
        self_repair=(),
        second_provider=(
            (_FAMILY_A_PROFILE, _FakeReasoningProvider("family_a")),
            (_FAMILY_B_PROFILE, _FakeReasoningProvider("family_b")),
        ),
    )

    # Full confirmation: both cloud providers must actually be authorized to reach
    # generate/validate, so there's a real winner for the arbiter to select between.
    result = await dispatcher.run(_task(), TaskBudget(limit=10), _FULL_CONFIRMATION)

    final = result.attempts[-1]
    assert final.rung is EscalationRung.SECOND_PROVIDER
    assert final.candidate.author in {"family_a", "family_b"}


async def test_a_secret_task_gets_no_authorized_cloud_provider_and_reports_unverifiable() -> None:
    """Acceptance criterion #9, exercised through the real dispatcher end-to-end."""
    dispatcher = _dispatcher(
        _FakeValidator(Verdict.FAILED),
        self_repair=(),
        second_provider=((_FAMILY_A_PROFILE, _FakeReasoningProvider("family_a")),),
    )

    result = await dispatcher.run(
        _task(Classification.SECRET), TaskBudget(limit=10), _FULL_CONFIRMATION
    )

    final = result.attempts[-1]
    assert final.rung is EscalationRung.SECOND_PROVIDER
    assert final.verdict is Verdict.UNVERIFIABLE
    assert final.candidate.author == "dispatcher"


async def test_budget_exhaustion_mid_run_surfaces_partial_results() -> None:
    """Acceptance criterion #5: terminates and surfaces partial results, never silently going on."""
    dispatcher = _dispatcher(
        _FakeValidator(Verdict.FAILED),
        self_repair=((_LOCAL_PROFILE, _FakeReasoningProvider("local")),),
        second_provider=((_FAMILY_A_PROFILE, _FakeReasoningProvider("family_a")),),
    )

    result = await dispatcher.run(_task(), TaskBudget(limit=1), _NO_CONFIRMATION)

    assert result.budget.is_exhausted
    # DETERMINISTIC_FIX stub (free) + one real, budget-spending attempt
    assert len(result.attempts) == _EXPECTED_STUB_PLUS_ONE_REAL_ATTEMPT
    assert result.attempts[-1].rung is EscalationRung.SELF_REPAIR
