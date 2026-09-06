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

Not handled here: atomic writes (temp-file-then-rename). A crash
mid-``save`` can leave a partially-written file. Real robustness
concern, out of scope for "does a working save/load seam exist."
"""

from __future__ import annotations

import json
import stat
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
    from pathlib import Path


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
    """Persists an AuditChain as a single JSON file at a constructor-supplied path."""

    def __init__(self, path: Path) -> None:
        """Store the path this adapter reads from and writes to.

        Args:
            path: Where the chain is persisted. Not created or
                validated at construction time -- a nonexistent path
                is a normal, valid state until the first :meth:`save`.
        """
        self._path = path

    def save(self, chain: AuditChain) -> None:
        """Overwrite the file at ``path`` with every record currently in ``chain``.

        Sets restrictive, owner-only permissions (``0o600``) on the
        file after every save (7 real decisions prompt, Decision 6,
        2026-09-05) -- the user's own chosen mitigation against
        casual/other-local-user tampering, the simplest of four real
        options laid out in
        ``docs/architecture/audit-log-integrity-scoping-notes.md``.
        Explicit ``os.chmod`` is required, not merely relying on
        ``Path.write_text``'s own default mode: the file's actual
        permissions after creation follow the process umask (commonly
        ``0o644``, world-readable), not a fixed, safe value --
        confirmed directly, not assumed. Applied unconditionally on
        every save, not only file creation, so a pre-existing file
        with looser permissions (e.g. one written before this fix
        existed) is also tightened the next time it's saved.

        **What this does and does not close, stated plainly**: raises
        the bar against a casual/other-local-user reading or tampering
        with the file at rest. Does **not** close the audit chain's
        other three real, distinct, already-documented gaps -- no
        timestamp field, non-atomic writes, or a cross-process race
        between two legitimate JARVIS processes saving simultaneously
        -- all three remain real, open, accepted limitations,
        unaffected by this specific decision. See
        ``docs/architecture/audit-log-integrity-scoping-notes.md``'s
        own updated note for the full account.
        """
        records = [_encode_record(record) for record in chain]
        self._path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        self._path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def load(self) -> AuditChain:
        """Return the chain last saved, or an empty AuditChain if ``path`` doesn't exist yet."""
        if not self._path.exists():
            return AuditChain()
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        records = [_decode_record(item) for item in raw]
        return AuditChain(records)
