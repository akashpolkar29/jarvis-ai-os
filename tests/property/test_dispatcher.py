"""Property-based tests for jarvis.application.reasoning.dispatcher.Dispatcher.

Exercises acceptance criterion #5 ("Budget exhaustion terminates and
surfaces partial results, never silently continues") over arbitrary
budgets and validator verdicts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypothesis import given
from hypothesis import strategies as st

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

_MAX_POSSIBLE_ATTEMPTS = 3

_CONTEXT = PolicyContext(physical_confirmation_available=True, remote_confirmation_available=True)
_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_FAMILY_A_PROFILE = ProviderProfile(name="family_a", is_local=False)


class _FakeReasoningProvider:
    async def generate(self, task: str, _prior_attempts: tuple[Attempt, ...]) -> Tainted[Candidate]:
        return Tainted(Candidate(author="local", content=task), Provenance.system())


class _FakeValidator:
    def __init__(self, verdict: Verdict) -> None:
        self._verdict = verdict

    async def validate(self, _candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        evidence = Evidence(
            kind=EvidenceKind.VALIDATION_RESULT, author="fake", weight=1.0, description="check"
        )
        return (self._verdict, (evidence,))


def _dispatcher(verdict: Verdict) -> Dispatcher:
    router = ModelRouter(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))
    providers = {
        EscalationRung.SELF_REPAIR: ((_LOCAL_PROFILE, _FakeReasoningProvider()),),
        EscalationRung.SECOND_PROVIDER: ((_FAMILY_A_PROFILE, _FakeReasoningProvider()),),
    }
    return Dispatcher(EscalationLadder(), Arbiter(), router, _FakeValidator(verdict), providers)


def _task() -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
    )
    return Tainted("do the task", provenance)


_VERDICTS = st.sampled_from([Verdict.FAILED, Verdict.UNVERIFIABLE])
_LIMITS = st.integers(min_value=0, max_value=5)


@given(_LIMITS, _VERDICTS)
async def test_run_always_terminates_and_never_exceeds_three_attempts(
    limit: int, verdict: Verdict
) -> None:
    """The ladder structurally bounds total attempts to 3, regardless of budget size."""
    result = await _dispatcher(verdict).run(_task(), TaskBudget(limit=limit), _CONTEXT)

    assert len(result.attempts) <= _MAX_POSSIBLE_ATTEMPTS


@given(_VERDICTS)
async def test_a_zero_limit_budget_permits_no_real_spending_attempts(verdict: Verdict) -> None:
    result = await _dispatcher(verdict).run(_task(), TaskBudget(limit=0), _CONTEXT)

    assert result.budget.spent == 0
    assert result.budget.is_exhausted


@given(_LIMITS, _VERDICTS)
async def test_the_run_never_spends_more_than_one_unit_past_its_limit(
    limit: int, verdict: Verdict
) -> None:
    """Once exhausted, the next loop check stops the run -- spend overshoots by at most one."""
    result = await _dispatcher(verdict).run(_task(), TaskBudget(limit=limit), _CONTEXT)

    assert result.budget.spent <= limit + 1
