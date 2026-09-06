"""Property-based tests for jarvis.application.reasoning.router.ModelRouter.

Exercises acceptance criterion #9 (ADR-0038: "a SECRET-classified task
never reaches a cloud provider at any rung, under any circumstance,
including physical_confirmation_available=True") through the real
ModelRouter/AuthorizationOrchestrator code path, not just the
domain-level property test WP-30 already added to
tests/property/test_capability.py. Also covers acceptance criterion #6
as corrected against real, Accepted ADR-0015 (not the recovered
m2-reasoning-layer.md wording, which contradicts it -- flagged during
WP-36, not silently resolved): SENSITIVE data may reach a cloud
provider, but never without some real confirmation channel available.

Tasks here use Trust.USER_DIRECT, not Provenance.external(): these
tests isolate classification-based effect gating from the separate
taint-escalation mechanism (CapabilityInvocation.effective_tier,
ADR-0011) -- an untrusted-external Trust would also escalate the tier
by one step, muddying what each test actually asserts.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audit import AuditChain
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import ProviderProfile
from jarvis.domain.registry import CapabilityRegistry

CONTEXTS = st.builds(
    PolicyContext,
    physical_confirmation_available=st.booleans(),
    remote_confirmation_available=st.booleans(),
)
CLOUD_PROFILES = st.builds(
    ProviderProfile, name=st.sampled_from(["family_a", "family_b"]), is_local=st.just(False)
)


def _router() -> ModelRouter:
    return ModelRouter(
        AuthorizationOrchestrator(AuditChain(), CapabilityRegistry(), clock=SystemClockAdapter())
    )


def _task(classification: Classification) -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted("do the task", provenance)


@given(CLOUD_PROFILES, CONTEXTS)
def test_secret_never_reaches_a_cloud_provider_under_any_circumstance(
    profile: ProviderProfile, context: PolicyContext
) -> None:
    """Criterion #9: no PolicyContext, including full physical confirmation, can grant this."""
    decision = _router().authorize_provider_call(profile, _task(Classification.SECRET), context)

    assert decision.granted is False


@given(CLOUD_PROFILES)
def test_sensitive_never_reaches_a_cloud_provider_without_any_confirmation(
    profile: ProviderProfile,
) -> None:
    """Criterion #6 (corrected per ADR-0015): never sent by default, with no confirmation at all."""
    no_confirmation = PolicyContext(
        physical_confirmation_available=False, remote_confirmation_available=False
    )

    decision = _router().authorize_provider_call(
        profile, _task(Classification.SENSITIVE), no_confirmation
    )

    assert decision.granted is False


@given(CLOUD_PROFILES)
def test_sensitive_can_reach_a_cloud_provider_with_explicit_confirmation(
    profile: ProviderProfile,
) -> None:
    """Criterion #6 (corrected per ADR-0015): the CONFIRM gate is real, not a disguised DENY."""
    confirmed = PolicyContext(
        physical_confirmation_available=True, remote_confirmation_available=False
    )

    decision = _router().authorize_provider_call(
        profile, _task(Classification.SENSITIVE), confirmed
    )

    assert decision.granted is True
