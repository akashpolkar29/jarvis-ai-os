"""Unit tests for jarvis.application.policy.orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.audit import AuditChain
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
)
from jarvis.domain.errors import AuditRecordNotSerializable, CapabilityNotRegistered
from jarvis.domain.policy import PolicyContext
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.registry import CapabilityRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping


def _descriptor(effects: Effect, capability_id: str = "test.capability") -> CapabilityDescriptor:
    """Build a CapabilityDescriptor with the given effects and id."""
    return CapabilityDescriptor(
        id=CapabilityId(capability_id),
        effects=effects,
        description="A test capability.",
    )


def _invocation(
    effects: Effect, arguments_value: Mapping[str, object] | None = None
) -> CapabilityInvocation:
    """Build a CapabilityInvocation with the given effects and (default: empty) arguments."""
    descriptor = _descriptor(effects)
    value = arguments_value if arguments_value is not None else {}
    return CapabilityInvocation(descriptor, Tainted(value, Provenance.user()))


_NO_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False,
    remote_confirmation_available=False,
)

_THREE_SEQUENTIAL_CALLS = 3
_TWO_SHARED_CALLS = 2


def test_granted_decision_is_returned_and_appended() -> None:
    """An ALLOW-tier decision is both returned and present in the chain."""
    chain = AuditChain()
    orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry())
    invocation = _invocation(Effect.READ_LOCAL)

    decision = orchestrator.authorize(invocation, _NO_CONFIRMATION)

    assert decision.granted is True
    assert len(chain) == 1
    assert chain[0].decision == decision


def test_denied_decision_is_still_returned_and_appended() -> None:
    """A MANUAL_ONLY decision denied for lack of physical confirmation is still audited."""
    chain = AuditChain()
    orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry())
    invocation = _invocation(Effect.DESTRUCTIVE)

    decision = orchestrator.authorize(invocation, _NO_CONFIRMATION)

    assert decision.granted is False
    assert len(chain) == 1
    assert chain[0].decision == decision


def test_sequential_calls_produce_a_verifiable_chain() -> None:
    """Multiple authorize() calls on one orchestrator produce a chain that verifies."""
    chain = AuditChain()
    orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry())

    orchestrator.authorize(_invocation(Effect.READ_LOCAL), _NO_CONFIRMATION)
    orchestrator.authorize(_invocation(Effect.DESTRUCTIVE), _NO_CONFIRMATION)
    orchestrator.authorize(_invocation(Effect.EXECUTE), _NO_CONFIRMATION)

    result = chain.verify()
    assert result.valid is True
    assert result.first_invalid_sequence is None
    assert len(chain) == _THREE_SEQUENTIAL_CALLS


def test_unauditable_decision_raises_and_is_not_appended() -> None:
    """A decision that cannot be canonicalized propagates and never reaches the chain.

    Proves the design answer: it must not be possible to receive a
    granted-or-denied Decision back from authorize() that was not
    already durably appended -- so a failed append raises instead of
    being swallowed, and leaves the chain exactly as it was.
    """

    class Opaque:
        """A deliberately opaque, non-canonicalizable value."""

    chain = AuditChain()
    orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry())
    invocation = _invocation(Effect.READ_LOCAL, {"bad": Opaque()})

    with pytest.raises(AuditRecordNotSerializable):
        orchestrator.authorize(invocation, _NO_CONFIRMATION)

    assert len(chain) == 0


def test_chain_is_injected_not_constructed_internally() -> None:
    """Two orchestrators sharing one injected chain both append to that same chain."""
    chain = AuditChain()
    first_orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry())
    second_orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry())

    first_orchestrator.authorize(_invocation(Effect.READ_LOCAL), _NO_CONFIRMATION)
    second_orchestrator.authorize(_invocation(Effect.EXECUTE), _NO_CONFIRMATION)

    assert len(chain) == _TWO_SHARED_CALLS
    assert chain.verify().valid is True


def test_authorize_by_id_granted_matches_authorize() -> None:
    """authorize_by_id() for a registered ALLOW-tier capability behaves like authorize()."""
    chain = AuditChain()
    registry = CapabilityRegistry()
    descriptor = _descriptor(Effect.READ_LOCAL)
    registry.register(descriptor)
    orchestrator = AuthorizationOrchestrator(chain, registry)
    arguments: Tainted[Mapping[str, object]] = Tainted({}, Provenance.user())

    decision = orchestrator.authorize_by_id(descriptor.id, arguments, _NO_CONFIRMATION)

    assert decision.granted is True
    assert len(chain) == 1
    assert chain[0].decision == decision


def test_authorize_by_id_denied_matches_authorize() -> None:
    """authorize_by_id() for a registered MANUAL_ONLY capability behaves like authorize()."""
    chain = AuditChain()
    registry = CapabilityRegistry()
    descriptor = _descriptor(Effect.DESTRUCTIVE)
    registry.register(descriptor)
    orchestrator = AuthorizationOrchestrator(chain, registry)
    arguments: Tainted[Mapping[str, object]] = Tainted({}, Provenance.user())

    decision = orchestrator.authorize_by_id(descriptor.id, arguments, _NO_CONFIRMATION)

    assert decision.granted is False
    assert len(chain) == 1
    assert chain[0].decision == decision


def test_authorize_by_id_unregistered_id_raises_and_appends_nothing() -> None:
    """authorize_by_id() for an unregistered id raises and never touches the chain.

    The registry lookup fails before evaluate() is ever called, so
    this is symmetric with the audit-append-failure guarantee: nothing
    partial happens either way.
    """
    chain = AuditChain()
    orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry())
    arguments: Tainted[Mapping[str, object]] = Tainted({}, Provenance.user())

    with pytest.raises(CapabilityNotRegistered):
        orchestrator.authorize_by_id(CapabilityId("fs.read_file"), arguments, _NO_CONFIRMATION)

    assert len(chain) == 0


def test_authorize_by_id_and_authorize_produce_identical_results() -> None:
    """authorize_by_id() is a genuine convenience wrapper, not a subtly different code path."""
    descriptor = _descriptor(Effect.EXECUTE)
    arguments: Tainted[Mapping[str, object]] = Tainted({}, Provenance.user())

    direct_chain = AuditChain()
    direct_orchestrator = AuthorizationOrchestrator(direct_chain, CapabilityRegistry())
    direct_invocation = CapabilityInvocation(descriptor, arguments)
    direct_decision = direct_orchestrator.authorize(direct_invocation, _NO_CONFIRMATION)

    by_id_chain = AuditChain()
    by_id_registry = CapabilityRegistry()
    by_id_registry.register(descriptor)
    by_id_orchestrator = AuthorizationOrchestrator(by_id_chain, by_id_registry)
    by_id_decision = by_id_orchestrator.authorize_by_id(descriptor.id, arguments, _NO_CONFIRMATION)

    assert direct_decision == by_id_decision
