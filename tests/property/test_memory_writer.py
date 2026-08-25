"""Property-based tests for jarvis.application.memory.writer.MemoryWriteAuthorizer.

Mirrors tests/property/test_router.py exactly -- ADR-0049's own
required acceptance criterion, matching ADR-0038's acceptance
criterion #9 rigor: "a SECRET-classified value never reaches the real
vector store at any rung, under any circumstance, including
physical_confirmation_available=True." Exercised through the real
MemoryWriteAuthorizer/AuthorizationOrchestrator code path, not just
the domain-level property test tests/property/test_capability.py
already covers.

Tasks here use Trust.USER_DIRECT, not Provenance.external(): these
tests isolate classification-based effect gating from the separate
taint-escalation mechanism (CapabilityInvocation.effective_tier,
ADR-0011), matching test_router.py's own reasoning for the identical
choice.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.memory.writer import MemoryWriteAuthorizer
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.domain.audit import AuditChain
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.registry import CapabilityRegistry

CONTEXTS = st.builds(
    PolicyContext,
    physical_confirmation_available=st.booleans(),
    remote_confirmation_available=st.booleans(),
)


def _authorizer() -> MemoryWriteAuthorizer:
    return MemoryWriteAuthorizer(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))


def _value(classification: Classification) -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted("remember this", provenance)


@given(CONTEXTS)
def test_secret_is_never_written_to_memory_under_any_circumstance(context: PolicyContext) -> None:
    """No PolicyContext, including full physical confirmation, can grant a SECRET memory write."""
    decision = _authorizer().authorize_write(_value(Classification.SECRET), context)

    assert decision.granted is False


@given(
    CONTEXTS,
    st.sampled_from([Classification.PUBLIC, Classification.PERSONAL, Classification.SENSITIVE]),
)
def test_non_secret_classifications_are_never_denied_by_memory_write_alone(
    context: PolicyContext, classification: Classification
) -> None:
    """PUBLIC/PERSONAL/SENSITIVE float at WRITE_LOCAL's own CONFIRM floor, not a special denial.

    Granted whenever *some* confirmation channel is available, matching
    Tier.CONFIRM's own evaluate() rule -- not a new restriction ADR-0049
    adds beyond what an ordinary local write already required.
    """
    decision = _authorizer().authorize_write(_value(classification), context)

    expected_granted = (
        context.physical_confirmation_available or context.remote_confirmation_available
    )
    assert decision.granted is expected_granted
