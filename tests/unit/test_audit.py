"""Unit tests for jarvis.domain.audit."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest

from jarvis.domain.audit import (
    ARGUMENT_DIGEST_KEY,
    GENESIS_PREVIOUS_HASH,
    AuditChain,
    AuditRecord,
    digest_argument_value,
    digest_value,
)
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
)
from jarvis.domain.errors import AuditRecordNotSerializable, AuditRecordTampered
from jarvis.domain.policy import Decision, PolicyContext, evaluate
from jarvis.domain.provenance import Provenance, Tainted

if TYPE_CHECKING:
    from collections.abc import Mapping

_HEX_DIGITS = frozenset("0123456789abcdef")
_SHA256_HEXDIGEST_LENGTH = 64


def _build_invocation(arguments_value: Mapping[str, object]) -> CapabilityInvocation:
    """Build a CapabilityInvocation whose arguments carry the given value."""
    descriptor = CapabilityDescriptor(
        id=CapabilityId("test.capability"),
        effects=Effect.READ_LOCAL,
        description="A test capability.",
    )
    return CapabilityInvocation(descriptor, Tainted(arguments_value, Provenance.user()))


def _decision(arguments_value: Mapping[str, object] | None = None) -> Decision:
    """Build a Decision for a capability with the given arguments value."""
    invocation = _build_invocation(arguments_value if arguments_value is not None else {})
    context = PolicyContext(
        physical_confirmation_available=True,
        remote_confirmation_available=True,
    )
    return evaluate(invocation, context)


def test_genesis_previous_hash_exact_value() -> None:
    """GENESIS_PREVIOUS_HASH is exactly 'GENESIS' followed by 57 zeros."""
    assert GENESIS_PREVIOUS_HASH == "GENESIS" + "0" * 57
    assert len(GENESIS_PREVIOUS_HASH) == _SHA256_HEXDIGEST_LENGTH


def test_genesis_previous_hash_cannot_be_a_real_sha256_digest() -> None:
    """No real sha256 hexdigest can ever equal the genesis constant.

    hexdigest() always emits exactly 64 lowercase hex characters. The
    genesis constant contains uppercase letters, so this is impossible
    by construction, not merely astronomically unlikely.
    """
    assert len(GENESIS_PREVIOUS_HASH) == _SHA256_HEXDIGEST_LENGTH
    assert not set(GENESIS_PREVIOUS_HASH).issubset(_HEX_DIGITS)


def test_audit_record_rejects_mismatched_hash() -> None:
    """Constructing an AuditRecord with a wrong record_hash raises AuditRecordTampered."""
    decision = _decision()
    with pytest.raises(AuditRecordTampered):
        AuditRecord(
            sequence=0,
            decision=decision,
            previous_hash=GENESIS_PREVIOUS_HASH,
            record_hash="0" * 64,
        )


def test_verify_on_empty_chain_is_valid() -> None:
    """An empty chain is vacuously valid: nothing in it can be inconsistent."""
    chain = AuditChain()
    result = chain.verify()
    assert result.valid is True
    assert result.first_invalid_sequence is None


def test_audit_chain_supports_reload_from_a_list_of_existing_records() -> None:
    """An AuditChain built from a list of already-valid records verifies correctly.

    This is the reload-from-storage scenario a later work package will
    need: verify() must not depend on the chain having been built via
    this specific instance's append() calls.
    """
    record_count = 3
    source_chain = AuditChain()
    for index in range(record_count):
        source_chain.append(_decision({"index": index}))

    reloaded_chain = AuditChain(list(source_chain))
    result = reloaded_chain.verify()
    assert result.valid is True
    assert result.first_invalid_sequence is None
    assert len(reloaded_chain) == record_count
    assert list(reloaded_chain) == list(source_chain)


def test_append_raises_on_non_canonicalizable_argument_value() -> None:
    """Appending a Decision whose arguments contain an opaque object raises.

    A plain object() has no stable structural serialization -- this
    must fail loudly at hash-computation time, not silently produce an
    unstable hash.
    """

    class Opaque:
        """A deliberately opaque, non-canonicalizable value."""

    decision = _decision({"bad": Opaque()})
    chain = AuditChain()
    with pytest.raises(AuditRecordNotSerializable):
        chain.append(decision)


def test_audit_chain_getitem_and_len() -> None:
    """AuditChain supports len() and indexing without exposing the internal list."""
    expected_length = 2
    chain = AuditChain()
    first = chain.append(_decision({"n": 1}))
    second = chain.append(_decision({"n": 2}))
    assert len(chain) == expected_length
    assert chain[0] == first
    assert chain[1] == second


def test_audit_record_is_frozen() -> None:
    """AuditRecord instances cannot be mutated through normal attribute assignment."""
    chain = AuditChain()
    record = chain.append(_decision())
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.sequence = 99  # type: ignore[misc]


def test_digest_value_is_deterministic() -> None:
    """digest_value() returns the same hexdigest for the same input every time."""
    value = {"path": "/home/user/secret.txt"}
    assert digest_value(value) == digest_value(value)


def test_digest_value_is_a_sha256_hexdigest() -> None:
    """digest_value() returns exactly 64 lowercase hex characters."""
    digest = digest_value({"path": "/home/user/secret.txt"})
    assert len(digest) == _SHA256_HEXDIGEST_LENGTH
    assert set(digest).issubset(_HEX_DIGITS)


def test_digest_value_distinguishes_different_inputs() -> None:
    """digest_value() produces different output for different input."""
    assert digest_value({"path": "/a"}) != digest_value({"path": "/b"})


def test_record_hash_is_sensitive_to_the_argument_value() -> None:
    """Two decisions differing only in argument value produce different record hashes.

    Proves the argument value's digest genuinely participates in
    record_hash (not, say, a constant placeholder regardless of
    content) -- see test_reloaded_digest_placeholder_is_not_rehashed
    below for the complementary proof that a digest already computed
    once is echoed, not rehashed, on reload.
    """
    chain_a = AuditChain()
    chain_b = AuditChain()
    record_a = chain_a.append(_decision({"path": "/home/user/a.txt"}))
    record_b = chain_b.append(_decision({"path": "/home/user/b.txt"}))
    assert record_a.record_hash != record_b.record_hash


def test_digest_argument_value_treats_a_non_string_digest_key_value_as_real_content() -> None:
    """A Mapping with exactly the ARGUMENT_DIGEST_KEY but a non-str value is not the placeholder.

    The placeholder shape is specifically {ARGUMENT_DIGEST_KEY: <hex
    str>} -- only ever produced by _decode_arguments. A genuine
    argument value that happens to have this one key with, say, an int
    value is real content and must be hashed normally via
    digest_value(), not mistaken for an already-computed digest.
    """
    value = {ARGUMENT_DIGEST_KEY: 12345}
    tainted = Tainted(value, Provenance.user())
    assert digest_argument_value(tainted) == digest_value(value)


def test_reloaded_digest_placeholder_is_not_rehashed() -> None:
    """A Tainted wrapping the ARGUMENT_DIGEST_KEY placeholder hashes using that digest as-is.

    This is the mechanism that makes AuditChain.verify() succeed after
    a save()/load() round-trip through JsonFileAuditStorageAdapter: the
    digest computed once at save time must be echoed byte-for-byte at
    verify time, never hashed a second time (which would produce a
    different result and make every reloaded record look tampered).
    """
    real_value = {"path": "/home/user/secret.txt"}
    value_digest = digest_value(real_value)

    fresh_decision = _decision(real_value)
    fresh_record = AuditChain().append(fresh_decision)

    placeholder_decision = _decision({ARGUMENT_DIGEST_KEY: value_digest})
    reconstructed_record = AuditRecord(
        sequence=0,
        decision=placeholder_decision,
        previous_hash=GENESIS_PREVIOUS_HASH,
        record_hash=fresh_record.record_hash,
    )

    assert reconstructed_record.record_hash == fresh_record.record_hash
