"""Unit tests for jarvis.application.policy.orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.confirmation import ManualConfirmationAdapter
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

_FULL_CONFIRMATION = PolicyContext(
    physical_confirmation_available=True,
    remote_confirmation_available=True,
)

_THREE_SEQUENTIAL_CALLS = 3
_TWO_SHARED_CALLS = 2


class _MutableConfirmationSource:
    """A ConfirmationPort test double whose reported context can change between calls.

    Used to prove get_current_context() fetches fresh on every call
    rather than caching the context it got back the first time (or at
    construction).
    """

    def __init__(self, context: PolicyContext) -> None:
        """Start out reporting ``context``."""
        self._context = context

    def get_context(self) -> PolicyContext:
        """Return whatever context was most recently set."""
        return self._context

    def set_context(self, context: PolicyContext) -> None:
        """Change what the next get_context() call will return."""
        self._context = context


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


def test_get_descriptor_returns_the_registered_descriptor() -> None:
    """get_descriptor() returns exactly the descriptor registered under that id."""
    registry = CapabilityRegistry()
    descriptor = _descriptor(Effect.READ_LOCAL)
    registry.register(descriptor)
    orchestrator = AuthorizationOrchestrator(AuditChain(), registry)

    assert orchestrator.get_descriptor(descriptor.id) is descriptor


def test_get_descriptor_raises_for_unregistered_capability() -> None:
    """get_descriptor() raises CapabilityNotRegistered for an id that was never registered."""
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    with pytest.raises(CapabilityNotRegistered):
        orchestrator.get_descriptor(CapabilityId("fs.read_file"))


def test_get_descriptor_does_not_touch_the_chain() -> None:
    """get_descriptor() is a pure read: it is not a decision and is never audited."""
    chain = AuditChain()
    registry = CapabilityRegistry()
    descriptor = _descriptor(Effect.READ_LOCAL)
    registry.register(descriptor)
    orchestrator = AuthorizationOrchestrator(chain, registry)

    orchestrator.get_descriptor(descriptor.id)

    assert len(chain) == 0


def test_is_registered_true_for_registered_capability() -> None:
    """is_registered() is True for an id that was registered."""
    registry = CapabilityRegistry()
    descriptor = _descriptor(Effect.READ_LOCAL)
    registry.register(descriptor)
    orchestrator = AuthorizationOrchestrator(AuditChain(), registry)

    assert orchestrator.is_registered(descriptor.id) is True


def test_is_registered_false_for_unregistered_capability() -> None:
    """is_registered() is False for an id that was never registered."""
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    assert orchestrator.is_registered(CapabilityId("fs.read_file")) is False


def test_is_registered_does_not_touch_the_chain() -> None:
    """is_registered() is a pure read: it is not a decision and is never audited."""
    chain = AuditChain()
    orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry())

    orchestrator.is_registered(CapabilityId("fs.read_file"))

    assert len(chain) == 0


def test_list_capabilities_empty_registry_returns_empty_tuple() -> None:
    """list_capabilities() on an empty registry returns an empty tuple."""
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    assert orchestrator.list_capabilities() == ()


def test_list_capabilities_returns_every_registered_descriptor() -> None:
    """list_capabilities() returns exactly the registered descriptors, in any order."""
    registry = CapabilityRegistry()
    first = _descriptor(Effect.READ_LOCAL, "fs.read_file")
    second = _descriptor(Effect.DESTRUCTIVE, "fs.delete_file")
    registry.register(first)
    registry.register(second)
    orchestrator = AuthorizationOrchestrator(AuditChain(), registry)

    capabilities = orchestrator.list_capabilities()

    assert isinstance(capabilities, tuple)
    assert set(capabilities) == {first, second}


def test_list_capabilities_does_not_touch_the_chain() -> None:
    """list_capabilities() is a pure read: it is not a decision and is never audited."""
    chain = AuditChain()
    registry = CapabilityRegistry()
    registry.register(_descriptor(Effect.READ_LOCAL))
    orchestrator = AuthorizationOrchestrator(chain, registry)

    orchestrator.list_capabilities()

    assert len(chain) == 0


def test_get_current_context_returns_the_port_supplied_context() -> None:
    """get_current_context() returns exactly what the injected ConfirmationPort reports."""
    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=True,
        remote_confirmation_available=False,
    )
    orchestrator = AuthorizationOrchestrator(
        AuditChain(), CapabilityRegistry(), confirmation=confirmation
    )

    context = orchestrator.get_current_context()

    assert context == confirmation.get_context()


def test_get_current_context_raises_without_a_confirmation_port_configured() -> None:
    """get_current_context() raises when no ConfirmationPort was provided at construction."""
    orchestrator = AuthorizationOrchestrator(AuditChain(), CapabilityRegistry())

    with pytest.raises(RuntimeError, match="no ConfirmationPort configured"):
        orchestrator.get_current_context()


def test_get_current_context_does_not_touch_the_chain() -> None:
    """get_current_context() is a pure read: it is not a decision and is never audited."""
    chain = AuditChain()
    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=True,
        remote_confirmation_available=True,
    )
    orchestrator = AuthorizationOrchestrator(chain, CapabilityRegistry(), confirmation=confirmation)

    orchestrator.get_current_context()

    assert len(chain) == 0


def test_get_current_context_is_fetched_fresh_not_cached() -> None:
    """Two calls after the port's underlying context changes return different results.

    Proves get_current_context() queries the port on every call rather
    than caching what it got back at construction or on first call --
    the correctness property that matters once a real presence-sensing
    adapter exists (a stale "physically present" reading must not be
    able to authorize a later action after the human left).
    """
    source = _MutableConfirmationSource(_NO_CONFIRMATION)
    orchestrator = AuthorizationOrchestrator(
        AuditChain(), CapabilityRegistry(), confirmation=source
    )

    first = orchestrator.get_current_context()
    source.set_context(_FULL_CONFIRMATION)
    second = orchestrator.get_current_context()

    assert first == _NO_CONFIRMATION
    assert second == _FULL_CONFIRMATION


def test_authorize_with_fetched_context_matches_authorize_with_explicit_context() -> None:
    """get_current_context() composes with authorize() through the same evaluate-then-audit path.

    Proves this is not a third, parallel way to reach a Decision: using
    the fetched context produces the identical outcome (and identical
    audit behavior) as passing the same context value directly.
    """
    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=False,
        remote_confirmation_available=False,
    )
    invocation = _invocation(Effect.DESTRUCTIVE)

    fetched_chain = AuditChain()
    fetched_orchestrator = AuthorizationOrchestrator(
        fetched_chain, CapabilityRegistry(), confirmation=confirmation
    )
    fetched_decision = fetched_orchestrator.authorize(
        invocation, fetched_orchestrator.get_current_context()
    )

    explicit_chain = AuditChain()
    explicit_orchestrator = AuthorizationOrchestrator(explicit_chain, CapabilityRegistry())
    explicit_decision = explicit_orchestrator.authorize(invocation, _NO_CONFIRMATION)

    assert fetched_decision == explicit_decision
    assert len(fetched_chain) == 1
    assert len(explicit_chain) == 1
