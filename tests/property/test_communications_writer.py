"""Property-based tests for jarvis.application.communications.writer.

Mirrors tests/property/test_memory_writer.py exactly -- ADR-0057's own
required acceptance criteria (2 and 3): "a Classification.SECRET email
body/attendee-bearing calendar summary is denied unconditionally when
sent/created, including when physical_confirmation_available=True."
Exercised through the real EmailSendAuthorizer/CalendarEventAuthorizer/
AuthorizationOrchestrator code path, not just the domain-level property
test tests/property/test_capability.py already covers.

Tasks here use Trust.USER_DIRECT, not Provenance.external(): these
tests isolate classification-based effect gating from the separate
taint-escalation mechanism (CapabilityInvocation.effective_tier,
ADR-0011), matching test_memory_writer.py's own reasoning for the
identical choice.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from jarvis.application.communications.writer import CalendarEventAuthorizer, EmailSendAuthorizer
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

_NON_SECRET = [Classification.PUBLIC, Classification.PERSONAL, Classification.SENSITIVE]


def _email_authorizer() -> EmailSendAuthorizer:
    return EmailSendAuthorizer(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))


def _calendar_authorizer() -> CalendarEventAuthorizer:
    return CalendarEventAuthorizer(AuthorizationOrchestrator(AuditChain(), CapabilityRegistry()))


def _body(classification: Classification) -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted("real message body", provenance)


def _summary(classification: Classification) -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted("real event summary", provenance)


@given(CONTEXTS)
def test_secret_email_body_is_never_sent_under_any_circumstance(context: PolicyContext) -> None:
    """No PolicyContext, including full physical confirmation, can grant a SECRET email send."""
    decision = _email_authorizer().authorize_send(
        ("recipient@example.com",), "subject", _body(Classification.SECRET), context
    )

    assert decision.granted is False


@given(CONTEXTS, st.sampled_from(_NON_SECRET))
def test_non_secret_email_bodies_are_never_denied_by_send_alone(
    context: PolicyContext, classification: Classification
) -> None:
    """PUBLIC/PERSONAL/SENSITIVE bodies float at EGRESS_SENSITIVE's own CONFIRM floor."""
    decision = _email_authorizer().authorize_send(
        ("recipient@example.com",), "subject", _body(classification), context
    )

    expected_granted = (
        context.physical_confirmation_available or context.remote_confirmation_available
    )
    assert decision.granted is expected_granted


@given(CONTEXTS, st.lists(st.text(min_size=1), min_size=2, max_size=5))
def test_secret_email_body_denied_regardless_of_recipient_count(
    context: PolicyContext, recipients: list[str]
) -> None:
    """ADR-0057's own 'all-or-nothing' amendment: recipient count never bypasses SECRET DENY."""
    decision = _email_authorizer().authorize_send(
        tuple(recipients), "subject", _body(Classification.SECRET), context
    )

    assert decision.granted is False


@given(CONTEXTS)
def test_secret_summary_with_attendees_is_never_created_under_any_circumstance(
    context: PolicyContext,
) -> None:
    """No PolicyContext can grant a SECRET-classified, attendee-bearing calendar event."""
    decision = _calendar_authorizer().authorize_create(
        _summary(Classification.SECRET), has_attendees=True, context=context
    )

    assert decision.granted is False


@given(CONTEXTS)
def test_secret_summary_without_attendees_is_not_specially_denied(context: PolicyContext) -> None:
    """An attendee-less event floors at WRITE_LOCAL/CONFIRM regardless of summary classification."""
    decision = _calendar_authorizer().authorize_create(
        _summary(Classification.SECRET), has_attendees=False, context=context
    )

    expected_granted = (
        context.physical_confirmation_available or context.remote_confirmation_available
    )
    assert decision.granted is expected_granted


@given(CONTEXTS, st.sampled_from(_NON_SECRET))
def test_non_secret_attendee_bearing_summary_floors_at_confirm(
    context: PolicyContext, classification: Classification
) -> None:
    decision = _calendar_authorizer().authorize_create(
        _summary(classification), has_attendees=True, context=context
    )

    expected_granted = (
        context.physical_confirmation_available or context.remote_confirmation_available
    )
    assert decision.granted is expected_granted
