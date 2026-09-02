"""Property-based tests for jarvis.application.job_assistance.drafting.DraftWriteAuthorizer.

Mirrors tests/property/test_memory_writer.py exactly -- the same
unconditional-DENY rigor ADR-0038/ADR-0049 already require, applied
here for a real, conservative implementation default (see
application/job_assistance/classification.py's own docstring): "a
SECRET-classified drafting task never reaches the real reasoning
providers or a real saved file, at any confirmation state, including
physical_confirmation_available=True." Exercised through the real
DraftWriteAuthorizer/AuthorizationOrchestrator code path.

Tasks here use Trust.USER_DIRECT, not Provenance.external(): these
tests isolate classification-based effect gating from the separate
taint-escalation mechanism (CapabilityInvocation.effective_tier,
ADR-0011), matching test_memory_writer.py's own reasoning for the
identical choice.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.job_assistance.drafting import DraftWriteAuthorizer
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


def _authorizer() -> DraftWriteAuthorizer:
    return DraftWriteAuthorizer(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))


def _task(classification: Classification) -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted("draft a cover letter", provenance)


@given(CONTEXTS)
def test_secret_is_never_authorized_to_draft_under_any_circumstance(
    context: PolicyContext,
) -> None:
    """No PolicyContext, including full physical confirmation, can grant a SECRET drafting task."""
    decision = _authorizer().authorize_draft(_task(Classification.SECRET), context)

    assert decision.granted is False


@given(
    CONTEXTS,
    st.sampled_from([Classification.PUBLIC, Classification.PERSONAL, Classification.SENSITIVE]),
)
def test_non_secret_classifications_are_never_denied_by_drafting_alone(
    context: PolicyContext, classification: Classification
) -> None:
    """PUBLIC/PERSONAL/SENSITIVE float at WRITE_LOCAL's own CONFIRM floor, not a special denial."""
    decision = _authorizer().authorize_draft(_task(classification), context)

    expected_granted = (
        context.physical_confirmation_available or context.remote_confirmation_available
    )
    assert decision.granted is expected_granted
