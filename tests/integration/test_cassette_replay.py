"""Acceptance criterion #7: full ladder replays deterministically from cassettes, network disabled.

Wires a real Dispatcher (WP-37) with CassettePlayer instances (WP-38)
standing in for SELF_REPAIR's and SECOND_PROVIDER's real
ReasoningPort adapters, loaded from real files under
``tests/cassettes/`` -- the "regression corpus" deliverable #10
describes. "Network disabled" here is structural, not configured:
neither CassettePlayer ever holds a reference to any real adapter,
D-Bus connection, or subprocess -- there is no code path in this test
that could reach a real network at all.
"""

from __future__ import annotations

from pathlib import Path

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.reasoning.cassette import CassettePlayer
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.application.reasoning.arbiter import Arbiter
from jarvis.application.reasoning.dispatcher import Dispatcher, DispatchResult
from jarvis.application.reasoning.ladder import EscalationLadder
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audit import AuditChain
from jarvis.domain.evidence import Candidate, EscalationRung, Evidence, EvidenceKind, Verdict
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import ProviderProfile, TaskBudget
from jarvis.domain.registry import CapabilityRegistry

_CASSETTES_DIR = Path(__file__).resolve().parents[1] / "cassettes"
_TASK_STRING = "fix the failing test in the ROS2 package"

_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_FAMILY_A_PROFILE = ProviderProfile(name="family_a", is_local=False)

_CONTEXT = PolicyContext(physical_confirmation_available=True, remote_confirmation_available=True)


class _FirstAttemptFailsThenPasses:
    """A validator that fails the first candidate it sees and passes every one after.

    Matches the recorded cassette's own story: the SELF_REPAIR
    candidate ("reinstalled the missing dependency") did not actually
    fix the failing test; the SECOND_PROVIDER candidate ("added the
    missing package.xml dependency entry") did.
    """

    def __init__(self) -> None:
        self._seen_one = False

    async def validate(self, candidate: Candidate) -> tuple[Verdict, tuple[Evidence, ...]]:
        evidence = Evidence(
            kind=EvidenceKind.VALIDATION_RESULT,
            author="pytest",
            weight=1.0,
            description=f"Checked {candidate.author}'s candidate against the cassette story.",
        )
        verdict = Verdict.PASSED if self._seen_one else Verdict.FAILED
        self._seen_one = True
        return (verdict, (evidence,))


def _build_dispatcher() -> Dispatcher:
    self_repair_player = CassettePlayer.load(_CASSETTES_DIR / "example_self_repair.json")
    second_provider_player = CassettePlayer.load(_CASSETTES_DIR / "example_second_provider.json")
    router = ModelRouter(
        AuthorizationOrchestrator(AuditChain(), CapabilityRegistry(), clock=SystemClockAdapter())
    )
    providers = {
        EscalationRung.SELF_REPAIR: ((_LOCAL_PROFILE, self_repair_player),),
        EscalationRung.SECOND_PROVIDER: ((_FAMILY_A_PROFILE, second_provider_player),),
    }
    return Dispatcher(
        EscalationLadder(), Arbiter(), router, _FirstAttemptFailsThenPasses(), providers
    )


def _task() -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=Classification.PUBLIC, sources=frozenset()
    )
    return Tainted(_TASK_STRING, provenance)


async def _run_once() -> DispatchResult:
    dispatcher = _build_dispatcher()
    return await dispatcher.run(_task(), TaskBudget(limit=10), _CONTEXT)


async def test_the_full_ladder_replays_the_recorded_story_from_cassettes() -> None:
    result = await _run_once()

    rungs = [attempt.rung for attempt in result.attempts]
    assert rungs == [
        EscalationRung.DETERMINISTIC_FIX,
        EscalationRung.SELF_REPAIR,
        EscalationRung.SECOND_PROVIDER,
    ]
    self_repair_content = "attempted patch: reinstalled the missing dependency"
    assert result.attempts[1].candidate.content == self_repair_content
    assert result.attempts[1].verdict is Verdict.FAILED
    assert result.attempts[2].candidate.author == "family_a"
    assert result.attempts[2].verdict is Verdict.PASSED


async def test_replaying_the_same_cassettes_twice_is_byte_for_byte_deterministic() -> None:
    """Acceptance criterion #7's own wording: replays deterministically."""
    first_run = await _run_once()
    second_run = await _run_once()

    assert first_run.attempts == second_run.attempts
