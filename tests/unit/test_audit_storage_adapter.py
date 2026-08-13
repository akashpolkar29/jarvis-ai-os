"""Unit tests for jarvis.adapters.audit_storage.JsonFileAuditStorageAdapter."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.domain.audit import ARGUMENT_DIGEST_KEY, AuditChain, digest_value
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
)
from jarvis.domain.errors import AuditRecordTampered
from jarvis.domain.policy import PolicyContext, evaluate
from jarvis.domain.provenance import Classification, Provenance, Tainted

if TYPE_CHECKING:
    from pathlib import Path

_NO_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False,
    remote_confirmation_available=False,
)

_RECORDS_AFTER_MIDDLE_DELETION = 2


def _descriptor(effects: Effect, capability_id: str) -> CapabilityDescriptor:
    """Build a CapabilityDescriptor with the given effects and id."""
    return CapabilityDescriptor(
        id=CapabilityId(capability_id),
        effects=effects,
        description="A test capability.",
    )


def _build_varied_chain() -> AuditChain:
    """Build a chain exercising a granted decision, a denied one, and taint escalation.

    Deliberately varied so the round-trip test can't pass by
    coincidentally handling only the simplest case: it covers a
    granted ALLOW decision, a MANUAL_ONLY decision denied for lack of
    physical confirmation (exercises DecisionReason.NO_PHYSICAL_CONFIRMATION,
    a Flag combination), and a taint-escalated invocation with a
    non-empty Provenance.sources (exercises frozenset round-tripping).
    """
    chain = AuditChain()

    allow_invocation = CapabilityInvocation(
        _descriptor(Effect.READ_LOCAL, "fs.read_file"),
        Tainted({"path": "/tmp/example"}, Provenance.user()),
    )
    chain.append(evaluate(allow_invocation, _NO_CONFIRMATION))

    manual_only_invocation = CapabilityInvocation(
        _descriptor(Effect.DESTRUCTIVE, "fs.delete_file"),
        Tainted({}, Provenance.user()),
    )
    chain.append(evaluate(manual_only_invocation, _NO_CONFIRMATION))

    tainted_invocation = CapabilityInvocation(
        _descriptor(Effect.WRITE_LOCAL, "notes.append"),
        Tainted(
            {"text": "hello"},
            Provenance.external("untrusted-webpage.example", Classification.PERSONAL),
        ),
    )
    chain.append(evaluate(tainted_invocation, _NO_CONFIRMATION))

    return chain


def test_load_on_a_nonexistent_path_returns_an_empty_chain(tmp_path: Path) -> None:
    """load() before any save() returns an empty AuditChain, not an error."""
    adapter = JsonFileAuditStorageAdapter(tmp_path / "audit.json")

    loaded = adapter.load()

    assert len(loaded) == 0
    assert loaded.verify().valid is True


def test_round_trip_preserves_content_and_verifies(tmp_path: Path) -> None:
    """A saved-then-loaded chain verifies and matches the original record-for-record.

    "Matches" excludes the raw argument value on purpose: per ADR-0027
    (work package 18), that value is never persisted, so a reloaded
    record's ``arguments.value`` is structurally the
    ``{ARGUMENT_DIGEST_KEY: <hex>}`` placeholder, not the original
    dict -- this is asserted explicitly below, alongside everything
    else that *does* round-trip byte-for-byte.
    """
    original = _build_varied_chain()
    adapter = JsonFileAuditStorageAdapter(tmp_path / "audit.json")

    adapter.save(original)
    loaded = adapter.load()

    assert loaded.verify().valid is True
    assert len(loaded) == len(original)
    for loaded_record, original_record in zip(loaded, original, strict=True):
        assert loaded_record.sequence == original_record.sequence
        assert loaded_record.previous_hash == original_record.previous_hash
        assert loaded_record.record_hash == original_record.record_hash

        loaded_decision = loaded_record.decision
        original_decision = original_record.decision
        assert loaded_decision.tier == original_decision.tier
        assert loaded_decision.granted == original_decision.granted
        assert loaded_decision.reasons == original_decision.reasons
        assert loaded_decision.invocation.descriptor == original_decision.invocation.descriptor

        loaded_arguments = loaded_decision.invocation.arguments
        original_arguments = original_decision.invocation.arguments
        assert loaded_arguments.provenance == original_arguments.provenance
        assert loaded_arguments.value != original_arguments.value
        assert loaded_arguments.value == {
            ARGUMENT_DIGEST_KEY: digest_value(original_arguments.value)
        }


def test_saved_file_never_contains_the_raw_argument_value(tmp_path: Path) -> None:
    """The literal raw argument value must not appear anywhere in the persisted file's bytes.

    This is the actual regression test ADR-0027 was missing -- caught
    by the WP-17 threat model, not by any test, because every prior
    test only checked round-trip correctness, never the absence of
    raw values from what's written to disk.
    """
    chain_path = tmp_path / "audit_chain.json"
    sensitive_marker = "this-exact-string-must-never-be-written-raw"
    invocation = CapabilityInvocation(
        _descriptor(Effect.EGRESS_LOCAL, "fs.read_file"),
        Tainted({"path": sensitive_marker}, Provenance.user()),
    )
    chain = AuditChain()
    chain.append(evaluate(invocation, _NO_CONFIRMATION))

    JsonFileAuditStorageAdapter(chain_path).save(chain)

    raw_bytes = chain_path.read_bytes()
    assert sensitive_marker.encode("utf-8") not in raw_bytes


def test_loading_a_pre_digest_only_format_file_raises_key_error(tmp_path: Path) -> None:
    """A chain file written before work package 18 (raw "value", no "value_digest") fails loudly.

    There is no migration path -- see domain/audit.py's module
    docstring for why a valid record_hash cannot be recomputed for an
    old-format record without the raw value that was never meant to be
    persisted in the first place. A clean, identifiable exception
    (KeyError, not a silent misparse) is the honest failure mode here.
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    adapter.save(_build_varied_chain())

    raw = json.loads(path.read_text(encoding="utf-8"))
    for record in raw:
        arguments = record["decision"]["invocation"]["arguments"]
        arguments["value"] = {}
        del arguments["value_digest"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(KeyError):
        adapter.load()


def test_round_trip_of_an_empty_chain(tmp_path: Path) -> None:
    """Saving and loading an empty chain round-trips to another empty, valid chain."""
    adapter = JsonFileAuditStorageAdapter(tmp_path / "audit.json")

    adapter.save(AuditChain())
    loaded = adapter.load()

    assert len(loaded) == 0
    assert loaded.verify().valid is True


def test_a_corrupted_record_hash_raises_on_load(tmp_path: Path) -> None:
    """A tampered record_hash is caught at load time, via AuditRecord's own constructor.

    This is the per-record tamper-detection tier: reconstructing
    through the real AuditRecord constructor means
    AuditRecordTampered fires automatically, with no bespoke check in
    this adapter.
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    adapter.save(_build_varied_chain())

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw[0]["record_hash"] = "0" * 64
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(AuditRecordTampered):
        adapter.load()


def test_a_deleted_middle_record_is_not_caught_by_load_but_is_caught_by_verify(
    tmp_path: Path,
) -> None:
    """Cross-record corruption is not caught by load() itself, only by an explicit verify().

    Deleting a middle record leaves the remaining records' own hashes
    self-consistent (nothing about their own content changed), so
    load() must not raise. But the chain's sequence/linkage is now
    broken, which is exactly what verify() exists to catch -- proving
    the documented boundary: load() guarantees per-record integrity
    for free, chain-level integrity remains the caller's explicit,
    one-call responsibility.
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    adapter.save(_build_varied_chain())

    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw[1]
    path.write_text(json.dumps(raw), encoding="utf-8")

    loaded = adapter.load()

    assert len(loaded) == _RECORDS_AFTER_MIDDLE_DELETION
    assert loaded.verify().valid is False


def test_save_overwrites_a_previous_save(tmp_path: Path) -> None:
    """A second save() replaces the file's content, it doesn't append to it."""
    adapter = JsonFileAuditStorageAdapter(tmp_path / "audit.json")
    first_chain = _build_varied_chain()
    adapter.save(first_chain)

    second_chain = AuditChain()
    adapter.save(second_chain)
    loaded = adapter.load()

    assert len(loaded) == 0
