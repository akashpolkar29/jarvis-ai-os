"""Unit tests for jarvis.adapters.audit_storage.JsonFileAuditStorageAdapter."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from pathlib import Path

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

_NO_CONFIRMATION = PolicyContext(
    physical_confirmation_available=False,
    remote_confirmation_available=False,
)

_RECORDS_AFTER_MIDDLE_DELETION = 2
_VARIED_CHAIN_LENGTH = 3
"""The real, fixed number of records `_build_varied_chain()` always builds."""


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
    chain.append(
        evaluate(allow_invocation, _NO_CONFIRMATION), written_at="2026-09-07T00:00:00+00:00"
    )

    manual_only_invocation = CapabilityInvocation(
        _descriptor(Effect.DESTRUCTIVE, "fs.delete_file"),
        Tainted({}, Provenance.user()),
    )
    chain.append(
        evaluate(manual_only_invocation, _NO_CONFIRMATION), written_at="2026-09-07T00:00:00+00:00"
    )

    tainted_invocation = CapabilityInvocation(
        _descriptor(Effect.WRITE_LOCAL, "notes.append"),
        Tainted(
            {"text": "hello"},
            Provenance.external("untrusted-webpage.example", Classification.PERSONAL),
        ),
    )
    chain.append(
        evaluate(tainted_invocation, _NO_CONFIRMATION), written_at="2026-09-07T00:00:00+00:00"
    )

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
        assert loaded_record.written_at == original_record.written_at
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
    chain.append(evaluate(invocation, _NO_CONFIRMATION), written_at="2026-09-07T00:00:00+00:00")

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


def test_loading_a_pre_written_at_format_file_raises_key_error(tmp_path: Path) -> None:
    """A chain file written before the written_at field existed (2026-09-07) fails loudly.

    The real, honest compatibility-break finding, asserted by a test,
    not just described in prose: adding written_at to the hashed tuple
    means every record_hash computed before this change is invalid
    under the new formula. There is no migration path, by construction
    -- see domain/audit.py's own module docstring for the full
    reasoning, and test_loading_a_pre_digest_only_format_file_raises_key_error
    above for the identical, already-accepted precedent this mirrors
    exactly (ADR-0027's own Tainted-digest change made the same real
    tradeoff for this same file format, once before).
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    adapter.save(_build_varied_chain())

    raw = json.loads(path.read_text(encoding="utf-8"))
    for record in raw:
        del record["written_at"]
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


def test_editing_the_written_at_field_directly_on_disk_is_caught_on_load(tmp_path: Path) -> None:
    """Tampering with written_at alone (record_hash untouched) is caught exactly like any other field.

    written_at (2026-09-07) is included in the hashed tuple (see
    domain/audit.py's own module docstring), so backdating or
    forward-dating a record without also recomputing a matching hash
    is exactly the same class of forgery
    test_editing_a_real_past_decision_field_directly_on_disk_is_caught_on_load
    above already proves for a Decision field -- this is the same
    real mechanism, a new field.
    """  # noqa: E501
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    adapter.save(_build_varied_chain())

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw[0]["written_at"] = "1970-01-01T00:00:00+00:00"  # forged, record_hash untouched
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


def test_save_of_an_empty_chain_on_a_fresh_instance_does_not_discard_existing_records(
    tmp_path: Path,
) -> None:
    """WP-115: save() no longer means "overwrite with exactly this chain."

    Before WP-115, saving an empty ``AuditChain()`` replaced the whole
    file, wiping out any real, already-persisted history -- exactly
    the same blind-overwrite mechanism that caused the cross-process
    race this work package closes. A *fresh* adapter instance (one
    that never called :meth:`load`) saving an empty chain must not
    discard real, existing content it never saw -- it has nothing new
    to contribute, so the file is left exactly as it was.
    """
    path = tmp_path / "audit.json"
    JsonFileAuditStorageAdapter(path).save(_build_varied_chain())

    JsonFileAuditStorageAdapter(path).save(AuditChain())
    loaded = JsonFileAuditStorageAdapter(path).load()

    assert len(loaded) == _VARIED_CHAIN_LENGTH
    assert loaded.verify().valid is True


def test_save_on_the_same_instance_that_loaded_first_correctly_appends_only_the_new_records(
    tmp_path: Path,
) -> None:
    """The real, established kernel pattern: one instance, load() then append then save().

    Mirrors every real ``kernel/*.py`` composition function's own
    ``storage = JsonFileAuditStorageAdapter(chain_path); chain =
    storage.load(); ...; storage.save(chain)`` shape -- the new
    record(s) a caller appended to the chain it loaded are the only
    ones persisted; the base content it loaded is never duplicated.
    """
    path = tmp_path / "audit.json"
    JsonFileAuditStorageAdapter(path).save(_build_varied_chain())

    adapter = JsonFileAuditStorageAdapter(path)
    chain = adapter.load()
    new_invocation = CapabilityInvocation(
        _descriptor(Effect.READ_LOCAL, "ping"), Tainted({}, Provenance.user())
    )
    chain.append(evaluate(new_invocation, _NO_CONFIRMATION), written_at="2026-09-11T00:00:00+00:00")
    adapter.save(chain)

    loaded = JsonFileAuditStorageAdapter(path).load()
    assert len(loaded) == _VARIED_CHAIN_LENGTH + 1
    assert loaded.verify().valid is True
    assert [record.sequence for record in loaded] == list(range(_VARIED_CHAIN_LENGTH + 1))


def test_save_leaves_no_leftover_temp_file_on_success(tmp_path: Path) -> None:
    """A successful save() leaves exactly the target file plus the real, permanent lock file.

    WP-101 (2026-09-08): save() writes to a temp file in the same
    directory first, then ``Path.replace``s it over the real path.
    ``replace`` consumes the temp file (renames it), so nothing named
    differently from the target (or the real, permanent, WP-115 lock
    file) should remain in the directory afterward.
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)

    adapter.save(_build_varied_chain())

    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["audit.json", "audit.json.lock"]


def test_save_leaves_the_original_file_untouched_if_the_write_fails_partway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real, simulated crash between temp-file creation and the atomic replace.

    WP-101 (2026-09-08): save() writes the full new content to a temp
    file, chmods it, then ``Path.replace``s it over the real path in
    one atomic step. Simulating a failure at the chmod step (standing
    in for a crash/kill at any point before the replace) must leave
    the real, pre-existing file at `path` completely untouched -- old
    content, not truncated, not replaced -- and must not leave the
    temp file lingering behind either. WP-115's own real, permanent
    lock file is expected to exist (it is created and locked *before*
    this simulated crash, and is never deleted by design -- see this
    module's own ``_lock_path`` docstring).
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    adapter.save(_build_varied_chain())
    original_content = path.read_bytes()

    def _raising_chmod(_self: Path, _mode: int) -> None:
        raise OSError("simulated crash mid-save")

    monkeypatch.setattr(Path, "chmod", _raising_chmod)

    with pytest.raises(OSError, match="simulated crash mid-save"):
        adapter.save(AuditChain())

    assert path.read_bytes() == original_content
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["audit.json", "audit.json.lock"]


def test_save_releases_its_real_lock_even_when_the_write_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP-115: a real exception inside save()'s own critical section still releases the lock.

    Proven directly and deterministically, not inferred from a later
    call merely succeeding (which could also "succeed" by hanging
    forever if the lock were never actually checked) -- immediately
    after the failed ``save()`` call, a second, independent attempt to
    take the identical real ``fcntl.flock()`` in *non-blocking* mode
    must succeed at once. If ``save()`` had left the lock held, this
    second attempt would raise ``BlockingIOError`` instead.
    """
    path = tmp_path / "audit.json"
    adapter = JsonFileAuditStorageAdapter(path)
    adapter.save(_build_varied_chain())

    def _raising_chmod(_self: Path, _mode: int) -> None:
        raise OSError("simulated crash mid-save")

    monkeypatch.setattr(Path, "chmod", _raising_chmod)

    with pytest.raises(OSError, match="simulated crash mid-save"):
        adapter.save(AuditChain())

    lock_path = tmp_path / "audit.json.lock"
    probe_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(probe_fd, fcntl.LOCK_UN)
    finally:
        os.close(probe_fd)


def test_two_independent_writers_racing_on_the_same_file_both_records_survive(
    tmp_path: Path,
) -> None:
    """WP-115: the real, previously-confirmed cross-process lost-write race is now closed.

    Real concurrency investigation (property-matrix/fuzzing/concurrency
    pass, Track 3, 2026-09-04) originally found and confirmed this real
    race: two independent AuditChain + JsonFileAuditStorageAdapter
    pairs -- standing in for two separate real OS processes, e.g. the
    CLI invoked twice concurrently against the same --chain-path, or
    the CLI and a running `jarvis ui` server both targeting the same
    file -- each uses its *own* single adapter instance for its own
    whole load() -> append() -> save() sequence, exactly mirroring how
    every real `kernel/*.py` composition function uses one
    `JsonFileAuditStorageAdapter` instance throughout one real call.
    Both writers load() the same starting chain, both append() their
    own new decision, then save() in sequence.

    **Before WP-115**: the second save() completely replaced the
    first's whole, valid file with its own whole, valid file -- the
    first writer's own new record was not merged, not detected as a
    conflict, and not present anywhere in the final file, even though
    `verify()` on the survivor still reported `valid=True` (the loss
    was invisible to the one integrity check this codebase had).

    **After WP-115**: the second writer's own `save()` re-reads the
    file's real, current state under a real, cross-process lock,
    finds the first writer's own record already there, and correctly
    rebases its own new record *after* it -- both records end up in
    the final, valid chain; neither is lost.
    """
    path = tmp_path / "audit.json"

    starting_chain = _build_varied_chain()
    JsonFileAuditStorageAdapter(path).save(starting_chain)

    first_writer = JsonFileAuditStorageAdapter(path)
    first_writer_chain = first_writer.load()
    second_writer = JsonFileAuditStorageAdapter(path)
    second_writer_chain = second_writer.load()

    first_new_invocation = CapabilityInvocation(
        _descriptor(Effect.READ_LOCAL, "ping"),
        Tainted({}, Provenance.user()),
    )
    first_new_record = first_writer_chain.append(
        evaluate(first_new_invocation, _NO_CONFIRMATION), written_at="2026-09-07T00:00:00+00:00"
    )

    second_new_invocation = CapabilityInvocation(
        _descriptor(Effect.READ_LOCAL, "git.status"),
        Tainted({}, Provenance.user()),
    )
    second_new_record = second_writer_chain.append(
        evaluate(second_new_invocation, _NO_CONFIRMATION), written_at="2026-09-07T00:00:00+00:00"
    )

    first_writer.save(first_writer_chain)
    second_writer.save(second_writer_chain)

    final_chain = JsonFileAuditStorageAdapter(path).load()
    final_capability_ids = {
        record.decision.invocation.descriptor.id.value for record in final_chain
    }

    assert first_new_record.decision.invocation.descriptor.id.value in final_capability_ids
    assert second_new_record.decision.invocation.descriptor.id.value in final_capability_ids
    assert len(final_chain) == _VARIED_CHAIN_LENGTH + 2
    assert final_chain.verify().valid is True
    assert [record.sequence for record in final_chain] == list(range(_VARIED_CHAIN_LENGTH + 2))
    assert final_chain.verify().valid is True
