"""Unit tests for jarvis.application.reasoning.router.ModelRouter.

Uses a real AuthorizationOrchestrator, AuditChain, and
CapabilityRegistry -- no mocking of the authorization path itself,
matching this project's own emphasis on exercising the real choke
point (ADR-0039) rather than a stand-in.
"""

from __future__ import annotations

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audit import AuditChain
from jarvis.domain.capability import Tier
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import ProviderProfile
from jarvis.domain.registry import CapabilityRegistry

_NO_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False, remote_confirmation_available=False
)
_REMOTE_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False, remote_confirmation_available=True
)
_PHYSICAL_CONFIRMATION = PolicyContext(
    physical_confirmation_available=True, remote_confirmation_available=False
)

_LOCAL_PROFILE = ProviderProfile(name="local", is_local=True)
_CLOUD_PROFILE = ProviderProfile(name="family_a", is_local=False)


def _router() -> ModelRouter:
    orchestrator = AuthorizationOrchestrator(
        AuditChain(), CapabilityRegistry(), clock=SystemClockAdapter()
    )
    return ModelRouter(orchestrator)


def _task(classification: Classification) -> Tainted[str]:
    """Build a task with real, untainted provenance carrying just ``classification``.

    Deliberately Trust.USER_DIRECT, not Provenance.external(): these
    tests isolate classification-based effect gating from the
    separate taint-escalation mechanism (CapabilityInvocation.effective_tier,
    ADR-0011) -- using an untrusted-external Trust here would also
    escalate the tier by one step, muddying what each test is actually
    asserting. A directly-typed SECRET (e.g. "my API key is X") is
    exactly ADR-0014/ADR-0038's real scenario regardless of Trust.
    """
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted("do the task", provenance)


def test_a_local_provider_is_always_allowed_no_confirmation_needed() -> None:
    decision = _router().authorize_provider_call(
        _LOCAL_PROFILE, _task(Classification.SECRET), _NO_CONFIRMATION
    )

    assert decision.granted is True
    assert decision.tier is Tier.ALLOW


def test_a_cloud_provider_with_public_data_is_denied_without_confirmation() -> None:
    """ADR-0015: never sent by default, even for the least sensitive classification."""
    decision = _router().authorize_provider_call(
        _CLOUD_PROFILE, _task(Classification.PUBLIC), _NO_CONFIRMATION
    )

    assert decision.granted is False
    assert decision.tier is Tier.CONFIRM


def test_a_cloud_provider_with_sensitive_data_is_granted_with_remote_confirmation() -> None:
    """ADR-0015: SENSITIVE may reach a cloud provider behind explicit CONFIRM."""
    decision = _router().authorize_provider_call(
        _CLOUD_PROFILE, _task(Classification.SENSITIVE), _REMOTE_CONFIRMATION
    )

    assert decision.granted is True
    assert decision.tier is Tier.CONFIRM


def test_a_cloud_provider_with_secret_data_is_denied_even_with_full_confirmation() -> None:
    """ADR-0038: EGRESS_SECRET floors at DENY, an absolute ceiling no confirmation overrides."""
    decision = _router().authorize_provider_call(
        _CLOUD_PROFILE, _task(Classification.SECRET), _PHYSICAL_CONFIRMATION
    )

    assert decision.granted is False
    assert decision.tier is Tier.DENY


def test_every_call_produces_a_real_audit_record() -> None:
    """ADR-0039: every attempted reasoning-provider call gets a real, hash-chained audit entry."""
    chain = AuditChain()
    router = ModelRouter(
        AuthorizationOrchestrator(chain, CapabilityRegistry(), clock=SystemClockAdapter())
    )

    router.authorize_provider_call(_CLOUD_PROFILE, _task(Classification.SECRET), _NO_CONFIRMATION)

    assert len(chain) == 1
