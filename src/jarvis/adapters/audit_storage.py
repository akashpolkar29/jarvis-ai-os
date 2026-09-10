"""Adapters implementing jarvis.ports.audit_storage.AuditStoragePort.

:class:`JsonFileAuditStorageAdapter` is a simple, single-JSON-file
implementation: the whole chain is (re)written on every :meth:`save`
and read back whole on every :meth:`load`.

Serialization here is a genuinely different problem from
``domain.audit._canonicalize`` and deliberately does not reuse it.
``_canonicalize`` solves a one-way, lossy, order-independent problem:
it only ever needs to produce deterministic hash input, and never
needs to come back (a ``Mapping`` becomes a sorted list of pairs, a
``frozenset`` becomes a sorted list, a dataclass becomes a list of
``(field_name, value)`` pairs with its type identity discarded).
Persistence needs the opposite property -- type-preserving,
reconstructible, schema-aware round-tripping -- so this module encodes
and decodes each domain type in the audit object graph explicitly,
one small function per type, reconstructing every dataclass through
its real constructor rather than bypassing it.

That last point matters for tamper detection: reconstructing an
``AuditRecord`` through its real constructor means
``AuditRecord.__post_init__`` -- which already raises
:class:`~jarvis.domain.errors.AuditRecordTampered` if a record's
``record_hash`` doesn't match its own content -- runs automatically on
every load. Per-record tampering is therefore caught for free, with no
new code here. Cross-record tampering (reordering, a deleted middle
record, a dangling ``previous_hash``) is *not* caught by this --
no single record's own hash is wrong in that case -- and this adapter
deliberately does not call
:meth:`~jarvis.domain.audit.AuditChain.verify` automatically either:
``AuditChain``'s own constructor already documents that reload does
not eagerly validate, and having this adapter's :meth:`load` silently
behave differently from direct ``AuditChain(records)`` construction
would be exactly the kind of same-operation-two-behaviors
inconsistency this project avoids elsewhere. Call ``.verify()`` on the
result explicitly if that guarantee is needed -- it already exists and
is a single call.

Argument values, specifically, are the one exception to "type-preserving,
reconstructible round-tripping" stated above: per ADR-0027, this
adapter persists only a sha256 digest of a ``CapabilityInvocation``'s
``Tainted`` argument value (via ``jarvis.domain.audit.digest_value``),
never the value itself. ``_decode_arguments`` cannot and does not
reconstruct the original value -- it rebuilds a ``Tainted`` whose
``.value`` is a reserved placeholder shape wrapping the persisted
digest (see ``jarvis.domain.audit.ARGUMENT_DIGEST_KEY``). This is a
deliberate, permanent, one-way loss of information, not a gap: it is
the entire point of the fix (work package 18). ``Provenance`` (trust,
classification, sources) is unaffected and still round-trips in full --
ADR-0027 scopes the digest-only requirement to argument *values*, not
their provenance metadata.

``save`` writes atomically (temp-file-then-``os.replace``, WP-101,
2026-09-08): a crash or kill mid-write can no longer leave a
truncated, invalid file at ``path`` -- either the old, complete
content is still there, or the new, complete content is.

**WP-115 (2026-09-11): the cross-process race is closed.** Before this,
two independent *processes* racing to ``save()`` the same ``path``
both individually wrote an atomically-complete file, but whichever
process's replace landed *last* won outright -- silently discarding
the other's own newly-appended record, with no corruption and no
error raised (`verify()` on the survivor still reported `valid=True`,
since nothing about *that* chain's own internal linkage was wrong,
only its relationship to history). **The real root cause**: `save()`
persisted exactly the in-memory `AuditChain` it was handed, with no
regard for what another process might have written to the same
``path`` in the meantime -- a blind whole-file overwrite, not a
durable append.

``save()`` now durably *merges* instead of overwrites. It tracks how
many records this adapter instance's own most recent :meth:`load` saw
(`self._loaded_count`); at save time, under a real, cross-process
`fcntl.flock()` exclusive lock (held only for this method's own
critical section -- `load()` needs no lock at all, since an atomic
`os.replace()`-backed file can never be read in a torn state), it
re-reads the file's *current* content fresh, takes only the records
this caller actually appended beyond what it loaded (`chain`'s own
tail beyond `self._loaded_count`), and re-parents each one onto the
file's current tail via `AuditChain.append()` -- recomputing a fresh
`sequence`/`previous_hash`/`record_hash` for each, exactly as if this
caller's own append had happened after whatever the other process
already persisted. The merged result is what gets written, through
the same, unmodified atomic temp-file-then-replace mechanism.

**A real, necessary, explicitly-stated semantic change, not silently
glossed over**: `save()` no longer means "overwrite the file with
exactly this chain" -- it means "durably persist this chain's own new
content, without ever discarding unrelated content already on disk."
`save(AuditChain())` (an empty chain) can no longer be used to wipe an
existing file; there is no mechanism in this codebase that ever relied
on that (confirmed directly, not assumed -- every real kernel caller
follows the identical `load()` -> authorize (-> `append()`) -> `save()`
sequence on one shared adapter instance, never a bare `save()` meant
to discard unrelated history). See
``docs/architecture/audit-chain-process-safety.md`` for the full
account, including the real lock file's own lifecycle and why `load()`
deliberately does not need one.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jarvis.domain.audit import ARGUMENT_DIGEST_KEY, AuditChain, AuditRecord, digest_argument_value
from jarvis.domain.capability import (
    CapabilityDescriptor,
    CapabilityId,
    CapabilityInvocation,
    Effect,
    Tier,
)
from jarvis.domain.policy import Decision, DecisionReason
from jarvis.domain.provenance import Classification, Provenance, Tainted, Trust

if TYPE_CHECKING:
    from collections.abc import Mapping


def _encode_provenance(provenance: Provenance) -> dict[str, Any]:
    """Encode a Provenance to JSON-primitive fields."""
    return {
        "trust": provenance.trust.value,
        "classification": provenance.classification.value,
        "sources": sorted(provenance.sources),
    }


def _decode_provenance(data: dict[str, Any]) -> Provenance:
    """Decode a Provenance from its encoded fields."""
    return Provenance(
        trust=Trust(data["trust"]),
        classification=Classification(data["classification"]),
        sources=frozenset(data["sources"]),
    )


def _encode_arguments(arguments: Tainted[Mapping[str, object]]) -> dict[str, Any]:
    """Encode a CapabilityInvocation's Tainted arguments -- a digest, never the raw value.

    Per ADR-0027: the audit log records only a digest of a capability
    invocation's arguments, never the argument values themselves. Uses
    ``jarvis.domain.audit.digest_argument_value`` -- not a plain
    ``digest_value(arguments.value)`` call -- because a record already
    loaded from storage (its ``.value`` already the digest-placeholder
    shape) must have its existing digest reused verbatim on re-save,
    not hashed a second time; see that function's own docstring for why
    a second, independent copy of this detection logic here would
    silently reintroduce the double-hashing bug it exists to prevent.
    """
    return {
        "value_digest": digest_argument_value(arguments),
        "provenance": _encode_provenance(arguments.provenance),
    }


def _decode_arguments(data: dict[str, Any]) -> Tainted[Mapping[str, object]]:
    """Decode a CapabilityInvocation's Tainted arguments from their persisted digest.

    The raw argument value was never persisted (see :func:`_encode_arguments`),
    so this reconstructs a ``Tainted`` whose ``.value`` is the reserved
    one-key digest-placeholder shape ``domain.audit._canonicalize`` knows
    to recognize and pass through as-is rather than re-hashing -- see
    ``domain.audit.ARGUMENT_DIGEST_KEY``'s own docstring for why.
    """
    return Tainted(
        {ARGUMENT_DIGEST_KEY: data["value_digest"]},
        _decode_provenance(data["provenance"]),
    )


def _encode_descriptor(descriptor: CapabilityDescriptor) -> dict[str, Any]:
    """Encode a CapabilityDescriptor to JSON-primitive fields."""
    return {
        "id": descriptor.id.value,
        "effects": descriptor.effects.value,
        "description": descriptor.description,
    }


def _decode_descriptor(data: dict[str, Any]) -> CapabilityDescriptor:
    """Decode a CapabilityDescriptor from its encoded fields."""
    return CapabilityDescriptor(
        id=CapabilityId(data["id"]),
        effects=Effect(data["effects"]),
        description=data["description"],
    )


def _encode_invocation(invocation: CapabilityInvocation) -> dict[str, Any]:
    """Encode a CapabilityInvocation to JSON-primitive fields."""
    return {
        "descriptor": _encode_descriptor(invocation.descriptor),
        "arguments": _encode_arguments(invocation.arguments),
    }


def _decode_invocation(data: dict[str, Any]) -> CapabilityInvocation:
    """Decode a CapabilityInvocation from its encoded fields."""
    return CapabilityInvocation(
        descriptor=_decode_descriptor(data["descriptor"]),
        arguments=_decode_arguments(data["arguments"]),
    )


def _encode_decision(decision: Decision) -> dict[str, Any]:
    """Encode a Decision to JSON-primitive fields."""
    return {
        "tier": decision.tier.value,
        "granted": decision.granted,
        "reasons": decision.reasons.value,
        "invocation": _encode_invocation(decision.invocation),
    }


def _decode_decision(data: dict[str, Any]) -> Decision:
    """Decode a Decision from its encoded fields."""
    return Decision(
        tier=Tier(data["tier"]),
        granted=data["granted"],
        reasons=DecisionReason(data["reasons"]),
        invocation=_decode_invocation(data["invocation"]),
    )


def _encode_record(record: AuditRecord) -> dict[str, Any]:
    """Encode an AuditRecord to JSON-primitive fields."""
    return {
        "sequence": record.sequence,
        "decision": _encode_decision(record.decision),
        "previous_hash": record.previous_hash,
        "written_at": record.written_at,
        "record_hash": record.record_hash,
    }


def _decode_record(data: dict[str, Any]) -> AuditRecord:
    """Decode an AuditRecord from its encoded fields.

    Reconstructs through AuditRecord's real constructor, so a
    record_hash that doesn't match its own content raises
    AuditRecordTampered here -- the same guarantee construction
    already provides everywhere else, not a check special to loading.

    **A real, deliberate breaking-change consequence, stated plainly,
    not silently handled**: ``written_at`` (2026-09-07) is read via
    plain ``data["written_at"]``, the same required-key style as every
    other field here -- a pre-2026-09-07 chain file has no such key at
    all, so loading one raises a plain ``KeyError`` here, not a
    special, softer error. No migration path is built (see
    ``jarvis.domain.audit``'s own module docstring for why); this
    matches the exact same real, accepted precedent this module's own
    ADR-0027 Tainted-digest change already established for this file.
    """
    return AuditRecord(
        sequence=data["sequence"],
        decision=_decode_decision(data["decision"]),
        previous_hash=data["previous_hash"],
        written_at=data["written_at"],
        record_hash=data["record_hash"],
    )


class JsonFileAuditStorageAdapter:
    """Persists an AuditChain as a single JSON file at a constructor-supplied path.

    WP-115 (2026-09-11): safe across independent OS processes, not
    merely within one. See this module's own docstring for the full
    account of the real race this closes and how.
    """

    def __init__(self, path: Path) -> None:
        """Store the path this adapter reads from and writes to.

        Args:
            path: Where the chain is persisted. Not created or
                validated at construction time -- a nonexistent path
                is a normal, valid state until the first :meth:`save`.
        """
        self._path = path
        self._loaded_count = 0
        """How many records this instance's own most recent :meth:`load`
        saw. Used by :meth:`save` to know which of ``chain``'s own
        records are genuinely new (everything from this index onward)
        versus already-persisted content this instance itself read.
        Starts at 0 (not ``None``) so a :meth:`save` call with no prior
        :meth:`load` on this instance treats its entire chain as new
        -- appended after whatever is already on disk, never silently
        discarding it. Updated again after every real :meth:`save`, so
        repeated ``save()`` calls on one instance (with no intervening
        ``load()``) also work correctly."""

    @property
    def _lock_path(self) -> Path:
        """A real, permanent, zero-byte sibling file used only for ``fcntl.flock()``.

        **Why a separate file, not the chain file itself**: :meth:`save`'s
        own atomic write replaces ``path``'s inode via ``Path.replace()``
        -- ``flock()``ing the chain file directly would leave the lock
        bound to the *old* inode the instant any writer's replace
        lands, silently detaching it from the path every future caller
        actually opens. A separate, stable-identity file has no such
        hazard: it is never replaced, only ever opened and flocked.

        **Why permanent, never deleted**: deleting a lock file while
        another process might still hold a lock on it recreates it
        under a new inode too -- the identical hazard from a different
        angle (a waiting process's already-open file descriptor would
        stay locked against the *deleted* inode, while a new caller
        opens and locks the *freshly recreated* one, and neither
        excludes the other). A small, permanent, zero-byte file is the
        accepted, standard cost of ``flock()``-based locking, not an
        oversight -- see ``docs/architecture/audit-chain-process-safety.md``.
        """
        return self._path.with_name(self._path.name + ".lock")

    def _read_records_from_disk(self) -> list[AuditRecord]:
        """Read and decode every record currently at ``path``, or ``[]`` if it doesn't exist yet.

        The real, shared implementation both :meth:`load` (unlocked --
        an atomic ``os.replace()``-backed file can never be read in a
        torn state, so no lock is needed just to read it) and
        :meth:`save` (locked -- re-reading the *current* state is the
        core of how the cross-process race is closed) call.
        """
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [_decode_record(item) for item in raw]

    def _write_atomic(self, records: list[AuditRecord]) -> None:
        """Atomically overwrite ``path`` with exactly ``records`` (temp-file-then-replace, WP-101).

        Unchanged from the pre-WP-115 mechanism -- see :meth:`save`'s
        own docstring for what calls this and why it is now always fed
        a real, merged record list rather than the raw chain argument.
        """
        payload = json.dumps([_encode_record(record) for record in records], indent=2)
        fd, tmp_name = tempfile.mkstemp(
            dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                tmp_file.write(payload)
            tmp_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            tmp_path.replace(self._path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    def save(self, chain: AuditChain) -> None:
        """Durably persist ``chain``'s own new records, merged against the current disk state.

        **WP-115 (2026-09-11)**: this is no longer a blind whole-file
        overwrite -- see this module's own docstring for the full
        account of the cross-process race this closes and why.
        Concretely, under a real, cross-process exclusive
        ``fcntl.flock()`` held only for this method's own critical
        section:

        1. Re-reads ``path``'s *current* content fresh (never trusts
           whatever this instance's own last :meth:`load` saw -- that
           may now be stale if another process has since saved).
        2. Takes only ``chain``'s own genuinely new records -- its
           tail beyond ``self._loaded_count`` (the count this
           instance's own most recent :meth:`load` returned; 0 if
           :meth:`load` was never called on this instance).
        3. Re-parents each new record onto the file's current tail via
           ``AuditChain.append()`` -- recomputing a fresh ``sequence``/
           ``previous_hash``/``record_hash`` for each, exactly as if
           this caller's own append had happened after whatever
           another process already persisted, since a record's
           position in the chain is only truly known at the moment it
           is actually durably persisted, not when it was first
           computed in memory.
        4. Atomically writes the merged result (:meth:`_write_atomic`,
           unchanged from WP-101) and updates
           ``self._loaded_count`` to match.

        **A real, necessary, explicitly-named consequence**: a
        record's own in-memory ``sequence``/``previous_hash``/
        ``record_hash`` (as originally computed by
        ``AuthorizationOrchestrator``/``AuditChain.append()`` at
        authorization time) may differ from what is actually persisted
        if another process's own save landed in between -- this is
        invisible to every real caller in this codebase, confirmed
        directly: no kernel composition function ever reads
        ``AuditRecord.sequence``/``.record_hash`` from a just-appended,
        not-yet-reloaded record (`Decision`, the one value every real
        ``authorize_and_*`` function returns, carries neither field at
        all). A caller that reads the chain back via a fresh
        :meth:`load` always sees the true, correctly-rebased final
        state.

        In the common case -- no concurrent writer, the overwhelming
        majority of real calls -- the disk has not moved since this
        instance's own :meth:`load`, so rebasing the new records onto
        the unchanged base reproduces ``chain`` exactly, record for
        record, hash for hash; this method's observable behavior is
        byte-for-byte identical to before WP-115.

        Restrictive, owner-only permissions (``0o600``, 7 real
        decisions prompt, Decision 6) are still applied to the written
        file on every real call, unchanged.

        Raises:
            jarvis.domain.errors.AuditRecordTampered: If ``path``'s
                *current* on-disk content (re-read under the lock) is
                itself tampered -- a real, additional safety property
                WP-115 adds for free: the pre-WP-115 `save()` never
                read the disk at all, so it would have silently
                overwritten a corrupted file without ever noticing.
        """
        lock_fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                disk_records = self._read_records_from_disk()
                new_records = list(chain)[self._loaded_count :]
                merged_chain = AuditChain(disk_records)
                for record in new_records:
                    merged_chain.append(record.decision, written_at=record.written_at)
                self._write_atomic(list(merged_chain))
                self._loaded_count = len(merged_chain)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)

    def load(self) -> AuditChain:
        """Return the chain last saved, or an empty AuditChain if ``path`` doesn't exist yet.

        No lock is taken -- an atomic, ``os.replace()``-backed file can
        never be observed in a torn state by a concurrent reader, so
        reading it is always safe without one (see this module's own
        docstring). Records how many records were seen
        (``self._loaded_count``) so a later :meth:`save` on this same
        instance knows which of its own chain's records are new.
        """
        records = self._read_records_from_disk()
        self._loaded_count = len(records)
        return AuditChain(records)
