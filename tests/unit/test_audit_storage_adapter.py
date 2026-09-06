"""Unit tests for jarvis.adapters.audit_storage.JsonFileAuditStorageAdapter."""

from __future__ import annotations

import json
import stat
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


def test_editing_a_real_past_decision_field_directly_on_disk_is_caught_on_load(
    tmp_path: Path,
) -> None:
    """The real, named tampering scenario this project's own threat model asks to prove.

    Real audit-log-integrity investigation (adapter-resilience/
    mutation-extension/audit-log-integrity pass, Track 3, 2026-09-05):
    the existing sibling test above only tampers with the
    ``record_hash`` field itself, never a real *decision* field with
    ``record_hash`` left untouched -- the more realistic, more
    security-relevant forgery attempt ("edit a past denied action to
    look granted, without knowing how to also recompute a matching
    hash"). Confirms the same real mechanism
    (``AuditRecord.__post_init__`` recomputing ``compute_hash()`` from
    the record's own real content and comparing) catches this too --
    a real, previously-unclosed test gap, not a new mechanism.
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    chain = _build_varied_chain()
    assert chain[1].decision.granted is False  # the real MANUAL_ONLY-denied record
    adapter.save(chain)

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw[1]["decision"]["granted"] = True  # forge a denial into a grant, record_hash untouched
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


def test_save_sets_restrictive_owner_only_file_permissions(tmp_path: Path) -> None:
    """save() leaves the real file at 0o600 -- owner read/write only, no group/other access.

    Real decision (7 real decisions prompt, Decision 6, 2026-09-05):
    the simplest of four real mitigation options against casual/other-
    local-user tampering (`docs/architecture/audit-log-integrity-scoping-notes.md`).
    Confirmed directly via a real `os.stat()` call, not assumed from
    the `os.chmod` call site alone -- `Path.write_text`'s own default
    mode follows the process umask, not a fixed value, so this proves
    the explicit `os.chmod` in `save()` actually took effect on a real
    file.
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)

    adapter.save(_build_varied_chain())

    real_mode = stat.S_IMODE(path.stat().st_mode)
    assert real_mode == (stat.S_IRUSR | stat.S_IWUSR)


def test_save_re_tightens_permissions_on_a_pre_existing_looser_file(tmp_path: Path) -> None:
    """A file saved once, then loosened, is re-tightened by the next real save() -- not just at creation."""  # noqa: E501
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    adapter.save(_build_varied_chain())
    path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    adapter.save(AuditChain())

    real_mode = stat.S_IMODE(path.stat().st_mode)
    assert real_mode == (stat.S_IRUSR | stat.S_IWUSR)


def test_save_overwrites_a_previous_save(tmp_path: Path) -> None:
    """A second save() replaces the file's content, it doesn't append to it."""
    adapter = JsonFileAuditStorageAdapter(tmp_path / "audit.json")
    first_chain = _build_varied_chain()
    adapter.save(first_chain)

    second_chain = AuditChain()
    adapter.save(second_chain)
    loaded = adapter.load()

    assert len(loaded) == 0


def test_two_independent_writers_racing_on_the_same_file_silently_lose_one_writers_record(
    tmp_path: Path,
) -> None:
    """A real, deliberately-caused cross-process lost-write race -- confirmed, not fixed.

    Real concurrency investigation (property-matrix/fuzzing/concurrency
    pass, Track 3, 2026-09-04). Two independent AuditChain +
    JsonFileAuditStorageAdapter pairs -- standing in for two separate
    real OS processes, e.g. the CLI invoked twice concurrently against
    the same --chain-path, or the CLI and a running voice loop both
    targeting the same file -- both load() the same starting chain,
    both append() their own new decision, then save() in sequence.
    Because save() always overwrites the whole file (this module's own
    docstring already documents "not handled here: atomic writes" as a
    known scope limit), the second save() completely replaces the
    first's -- the first writer's own new record is not merged, not
    detected as a conflict, and not present anywhere in the final
    file. verify() on the final loaded chain still reports valid=True:
    the surviving chain is internally coherent, so this loss is
    invisible to the one integrity check this codebase already has.

    Deliberately NOT fixed here: unlike the in-process AuditChain.append()
    race this same pass found and fixed with an internal lock, closing
    this cross-process gap for real would mean changing
    AuditStoragePort's own save()/load() contract (real file locking,
    or an append-only file format) -- a genuine architecture decision,
    not a test-writing fix, and out of this pass's own safe scope
    (see CLAUDE.md's standing "never silently change the architecture"
    rule). Recorded here as a real, confirmed, previously-undocumented-
    as-a-concrete-scenario gap for docs/threat-model/v0.md, not
    silently patched.
    """
    path = tmp_path / "audit.json"

    starting_chain = _build_varied_chain()
    JsonFileAuditStorageAdapter(path).save(starting_chain)

    first_writer_chain = JsonFileAuditStorageAdapter(path).load()
    second_writer_chain = JsonFileAuditStorageAdapter(path).load()

    first_new_invocation = CapabilityInvocation(
        _descriptor(Effect.READ_LOCAL, "ping"),
        Tainted({}, Provenance.user()),
    )
    first_new_record = first_writer_chain.append(evaluate(first_new_invocation, _NO_CONFIRMATION))

    second_new_invocation = CapabilityInvocation(
        _descriptor(Effect.READ_LOCAL, "git.status"),
        Tainted({}, Provenance.user()),
    )
    second_new_record = second_writer_chain.append(
        evaluate(second_new_invocation, _NO_CONFIRMATION)
    )

    JsonFileAuditStorageAdapter(path).save(first_writer_chain)
    JsonFileAuditStorageAdapter(path).save(second_writer_chain)

    final_chain = JsonFileAuditStorageAdapter(path).load()
    final_capability_ids = {
        record.decision.invocation.descriptor.id.value for record in final_chain
    }

    assert second_new_record.decision.invocation.descriptor.id.value in final_capability_ids
    assert first_new_record.decision.invocation.descriptor.id.value not in final_capability_ids
    assert final_chain.verify().valid is True
