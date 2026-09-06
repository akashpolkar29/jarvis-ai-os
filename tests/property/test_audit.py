"""Property-based tests for jarvis.domain.audit."""

from __future__ import annotations

import copy

from hypothesis import given
from hypothesis import strategies as st

from jarvis.domain.audit import AuditChain
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
)
from jarvis.domain.policy import Decision, PolicyContext, evaluate
from jarvis.domain.provenance import Classification, Provenance, Tainted


def _decision(index: int, *, tainted: bool) -> Decision:
    """Build a Decision for a distinct capability, so hashes vary meaningfully."""
    descriptor = CapabilityDescriptor(
        id=CapabilityId(f"test.capability.{index}"),
        effects=Effect.READ_LOCAL,
        description=f"Test capability {index}.",
    )
    provenance = (
        Provenance.external(f"source-{index}", Classification.PUBLIC)
        if tainted
        else Provenance.user()
    )
    invocation = CapabilityInvocation(descriptor, Tainted({"index": index}, provenance))
    context = PolicyContext(
        physical_confirmation_available=True,
        remote_confirmation_available=True,
    )
    return evaluate(invocation, context)


def _decision_with_arg_order(index: int, *, tainted: bool, reversed_order: bool) -> Decision:
    """Build a logically-equal Decision to _decision, with a differently-ordered arguments dict."""
    descriptor = CapabilityDescriptor(
        id=CapabilityId(f"test.capability.{index}"),
        effects=Effect.READ_LOCAL,
        description=f"Test capability {index}.",
    )
    provenance = (
        Provenance.external(f"source-{index}", Classification.PUBLIC)
        if tainted
        else Provenance.user()
    )
    arguments_value = (
        {"b": index, "a": index * 2} if reversed_order else {"a": index * 2, "b": index}
    )
    invocation = CapabilityInvocation(descriptor, Tainted(arguments_value, provenance))
    context = PolicyContext(
        physical_confirmation_available=True,
        remote_confirmation_available=True,
    )
    return evaluate(invocation, context)


RECIPE = st.lists(
    st.tuples(st.integers(min_value=0, max_value=1000), st.booleans()),
    min_size=1,
    max_size=8,
)
DECISIONS = st.lists(
    st.builds(_decision, index=st.integers(min_value=0, max_value=1000), tainted=st.booleans()),
    min_size=1,
    max_size=8,
)
DECISIONS_MIN2 = st.lists(
    st.builds(_decision, index=st.integers(min_value=0, max_value=1000), tainted=st.booleans()),
    min_size=2,
    max_size=8,
)


@given(DECISIONS)
def test_append_produces_contiguous_sequence(decisions: list[Decision]) -> None:
    """Appending N decisions yields sequence numbers exactly 0..N-1, no gaps."""
    chain = AuditChain()
    for decision in decisions:
        chain.append(decision, written_at="2026-09-07T00:00:00+00:00")
    assert len(chain) == len(decisions)
    assert [record.sequence for record in chain] == list(range(len(decisions)))


@given(DECISIONS)
def test_freshly_appended_chain_always_verifies(decisions: list[Decision]) -> None:
    """A chain built purely via append() always passes verify()."""
    chain = AuditChain()
    for decision in decisions:
        chain.append(decision, written_at="2026-09-07T00:00:00+00:00")
    result = chain.verify()
    assert result.valid is True
    assert result.first_invalid_sequence is None


@given(DECISIONS, st.integers(min_value=0))
def test_tampering_a_single_field_is_always_detected(decisions: list[Decision], seed: int) -> None:
    """Corrupting any one field of any one record always fails verify().

    AuditRecord's constructor makes an internally-inconsistent record
    impossible to build normally, so tampering is simulated the way it
    would really happen -- an already-valid record corrupted out of
    band (e.g. a buggy deserializer) -- via copy.copy() (which bypasses
    __post_init__) plus object.__setattr__ (which bypasses frozen=True).
    """
    chain = AuditChain()
    for decision in decisions:
        chain.append(decision, written_at="2026-09-07T00:00:00+00:00")

    tamper_index = seed % len(chain)
    records = list(chain)
    tampered = copy.copy(records[tamper_index])

    field_choice = seed % 3
    if field_choice == 0:
        object.__setattr__(tampered, "sequence", tampered.sequence + 1)
    elif field_choice == 1:
        object.__setattr__(tampered, "previous_hash", "0" * 64)
    else:
        object.__setattr__(tampered, "record_hash", "0" * 64)

    records[tamper_index] = tampered
    tampered_chain = AuditChain(records)
    result = tampered_chain.verify()
    assert result.valid is False
    assert result.first_invalid_sequence == tamper_index


@given(RECIPE)
def test_hashing_is_deterministic_across_independent_chains(recipe: list[tuple[int, bool]]) -> None:
    """Two independently-built chains produce identical record_hash values.

    Each chain is built from its own, separately-constructed Decision
    objects (different object identities), with the arguments dict
    built in the opposite key order for the second chain -- proving
    determinism isn't accidentally riding on object identity or dict
    insertion order.
    """
    chain_a = AuditChain()
    chain_b = AuditChain()
    for index, tainted in recipe:
        chain_a.append(
            _decision_with_arg_order(index, tainted=tainted, reversed_order=False),
            written_at="2026-09-07T00:00:00+00:00",
        )
        chain_b.append(
            _decision_with_arg_order(index, tainted=tainted, reversed_order=True),
            written_at="2026-09-07T00:00:00+00:00",
        )
    hashes_a = [record.record_hash for record in chain_a]
    hashes_b = [record.record_hash for record in chain_b]
    assert hashes_a == hashes_b


@given(DECISIONS_MIN2, st.integers(min_value=0))
def test_deleting_a_middle_record_is_detected(decisions: list[Decision], seed: int) -> None:
    """Removing a record from the chain (not just corrupting a field) is caught."""
    chain = AuditChain()
    for decision in decisions:
        chain.append(decision, written_at="2026-09-07T00:00:00+00:00")

    delete_index = seed % (len(chain) - 1)  # never delete the last record
    records = list(chain)
    del records[delete_index]

    shortened_chain = AuditChain(records)
    result = shortened_chain.verify()
    assert result.valid is False
    assert result.first_invalid_sequence == delete_index
