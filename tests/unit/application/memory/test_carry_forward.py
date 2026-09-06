"""Unit tests for jarvis.application.memory.carry_forward.

ADR-0050's own required real proof: a recalled `MemoryRecord`'s real
provenance, merged with the caller's own real task provenance, is what
actually gates a new cloud-provider `CapabilityInvocation` -- not a
fresh, unclassified wrap, and not the record's provenance used alone
either (the caller's own task content can independently push the
required tier up too).
"""

from __future__ import annotations

from datetime import UTC, datetime

from jarvis.adapters.clock import SystemClockAdapter
from jarvis.application.memory.carry_forward import authorize_reasoning_call_with_recalled_context
from jarvis.application.policy.orchestrator import AuthorizationOrchestrator
from jarvis.application.reasoning.router import ModelRouter
from jarvis.domain.audit import AuditChain
from jarvis.domain.memory import MemoryRecord
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust
from jarvis.domain.reasoning import ProviderProfile
from jarvis.domain.registry import CapabilityRegistry

_CLOUD_PROFILE = ProviderProfile(name="family_a", is_local=False)
_NO_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False, remote_confirmation_available=False
)
_FULL_CONFIRMATION = PolicyContext(
    physical_confirmation_available=True, remote_confirmation_available=True
)


def _router() -> ModelRouter:
    return ModelRouter(
        AuthorizationOrchestrator(AuditChain(), CapabilityRegistry(), clock=SystemClockAdapter())
    )


def _record(classification: Classification) -> MemoryRecord:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return MemoryRecord(
        identifier="mem:1",
        value=Tainted("prefers dark mode", provenance),
        written_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=None,
    )


def _task(classification: Classification) -> Tainted[str]:
    provenance = Provenance(
        trust=Trust.USER_DIRECT, classification=classification, sources=frozenset()
    )
    return Tainted("summarize my preferences", provenance)


def test_a_sensitive_recalled_record_requires_confirm_for_a_cloud_provider() -> None:
    record = _record(Classification.SENSITIVE)
    task = _task(Classification.PUBLIC)

    denied = authorize_reasoning_call_with_recalled_context(
        record, task, _CLOUD_PROFILE, _router(), _NO_CONFIRMATION
    )
    granted = authorize_reasoning_call_with_recalled_context(
        record, task, _CLOUD_PROFILE, _router(), _FULL_CONFIRMATION
    )

    assert denied.granted is False
    assert granted.granted is True


def test_a_secret_task_merged_with_a_public_record_is_denied_unconditionally() -> None:
    """Even full confirmation cannot grant this -- the merged classification floors DENY."""
    record = _record(Classification.PUBLIC)
    task = _task(Classification.SECRET)

    decision = authorize_reasoning_call_with_recalled_context(
        record, task, _CLOUD_PROFILE, _router(), _FULL_CONFIRMATION
    )

    assert decision.granted is False


def test_a_public_record_and_public_task_still_requires_confirm() -> None:
    """No ALLOW-tier cloud egress exists in the fixed taxonomy -- CONFIRM is the real floor."""
    record = _record(Classification.PUBLIC)
    task = _task(Classification.PUBLIC)

    denied = authorize_reasoning_call_with_recalled_context(
        record, task, _CLOUD_PROFILE, _router(), _NO_CONFIRMATION
    )
    granted = authorize_reasoning_call_with_recalled_context(
        record, task, _CLOUD_PROFILE, _router(), _FULL_CONFIRMATION
    )

    assert denied.granted is False
    assert granted.granted is True


def test_the_combined_tasks_provenance_is_the_real_merge_not_a_fresh_wrap() -> None:
    """Directly proves the carry-forward rule -- not Provenance.user(), the real merge."""
    record = _record(Classification.SENSITIVE)
    task = _task(Classification.PERSONAL)

    decision = authorize_reasoning_call_with_recalled_context(
        record, task, _CLOUD_PROFILE, _router(), _FULL_CONFIRMATION
    )

    provenance = decision.invocation.arguments.provenance
    assert provenance.classification is Classification.SENSITIVE  # max(SENSITIVE, PERSONAL)
    assert provenance != Provenance.user()
    assert provenance != Provenance.system()
