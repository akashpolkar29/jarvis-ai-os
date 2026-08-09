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

Scope limitation, stated plainly: ``CapabilityInvocation.arguments``
wraps a ``Mapping[str, object]`` whose value type is genuinely
unconstrained by the domain. This adapter encodes/decodes that payload
with plain ``json.dumps``/``json.loads`` -- JSON-native content
(dict/list/str/int/float/bool/None) round-trips exactly; a
``frozenset`` or custom object nested *inside* an argument value would
not. Every existing test in this codebase only ever puts JSON-native
content in arguments; extending this to the full canonicalizable-type
surface is real future work, not built speculatively here.

Not handled here: atomic writes (temp-file-then-rename). A crash
mid-``save`` can leave a partially-written file. Real robustness
concern, out of scope for "does a working save/load seam exist."
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from jarvis.domain.audit import AuditChain, AuditRecord
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
    """Encode a CapabilityInvocation's Tainted arguments to JSON-primitive fields."""
    return {
        "value": dict(arguments.value),
        "provenance": _encode_provenance(arguments.provenance),
    }


def _decode_arguments(data: dict[str, Any]) -> Tainted[Mapping[str, object]]:
    """Decode a CapabilityInvocation's Tainted arguments from its encoded fields."""
    return Tainted(dict(data["value"]), _decode_provenance(data["provenance"]))


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
        "record_hash": record.record_hash,
    }


def _decode_record(data: dict[str, Any]) -> AuditRecord:
    """Decode an AuditRecord from its encoded fields.

    Reconstructs through AuditRecord's real constructor, so a
    record_hash that doesn't match its own content raises
    AuditRecordTampered here -- the same guarantee construction
    already provides everywhere else, not a check special to loading.
    """
    return AuditRecord(
        sequence=data["sequence"],
        decision=_decode_decision(data["decision"]),
        previous_hash=data["previous_hash"],
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
        """Overwrite the file at ``path`` with every record currently in ``chain``."""
        records = [_encode_record(record) for record in chain]
        self._path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def load(self) -> AuditChain:
        """Return the chain last saved, or an empty AuditChain if ``path`` doesn't exist yet."""
        if not self._path.exists():
            return AuditChain()
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        records = [_decode_record(item) for item in raw]
        return AuditChain(records)
