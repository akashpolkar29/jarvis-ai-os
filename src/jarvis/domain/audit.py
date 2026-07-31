"""The audit log: a hash-chained, tamper-evident record of every Decision.

Every :class:`~jarvis.domain.policy.Decision` is recorded as an
:class:`AuditRecord` and appended to an :class:`AuditChain`. Each
record's hash covers its own sequence number, its previous record's
hash, and a canonical serialization of the Decision itself -- so any
single change to any record's content, or any change to the chain's
order, breaks the hash linkage and is detectable by
:meth:`AuditChain.verify`.

Canonical serialization scheme (see :func:`_canonicalize`): a
Decision's object graph (Decision -> CapabilityInvocation ->
CapabilityDescriptor -> CapabilityId, Tainted -> Provenance) is walked
reflectively via ``dataclasses.fields()`` -- in each dataclass's fixed
declaration order -- down to only ``None``/``bool``/``int``/``float``/
``str``, with ``Enum`` members reduced to their ``.value`` (never
``repr()``, which isn't guaranteed stable across Python versions),
``Mapping`` reduced to a list of ``(key, value)`` pairs sorted by key
(kills insertion-order dependence), and ``frozenset``/``set`` reduced
to a sorted list (kills ``PYTHONHASHSEED``-driven iteration-order
instability for e.g. ``Provenance.sources``). Anything not covered by
this scheme raises :class:`~jarvis.domain.errors.AuditRecordNotSerializable`
rather than falling back to an unstable ``repr()``.

Limitation, stated plainly: this chain detects any tampering with a
single record, or any partial reordering that isn't accompanied by
recomputing every subsequent hash. It does NOT protect against an
attacker with write access to storage who is willing to relabel
sequence numbers and recompute hashes forward through the rest of the
chain -- that requires a signing key, HMAC, or external anchoring,
none of which this module provides. A future work package building
the storage/reload layer needs to read this before assuming more than
this chain actually guarantees.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING

from .errors import AuditRecordNotSerializable, AuditRecordTampered

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from .policy import Decision

GENESIS_PREVIOUS_HASH: str = "GENESIS" + "0" * 57
"""The ``previous_hash`` of the first record in any chain.

64 characters -- the same length as a real sha256 hexdigest -- but
containing uppercase letters, which ``hashlib.sha256(...).hexdigest()``
can never produce (it emits exactly 64 lowercase hex characters,
always). This makes collision with a real hash impossible by
construction, not merely astronomically unlikely.
"""


def _canonicalize(value: object) -> object:
    """Reduce ``value`` to an order-independent, JSON-primitive-only structure.

    Args:
        value: The value to canonicalize.

    Returns:
        A structure containing only ``None``/``bool``/``int``/``float``/
        ``str``/``list``, safe to pass to :func:`json.dumps`.

    Raises:
        AuditRecordNotSerializable: If ``value`` is not one of the
            types this scheme knows how to canonicalize.
    """
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return sorted((key, _canonicalize(val)) for key, val in value.items())
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, (frozenset, set)):
        # _canonicalize's declared return type is `object`, so mypy can't
        # see that these items are always orderable in practice (e.g.
        # Provenance.sources is frozenset[str]); an item that genuinely
        # isn't orderable would raise TypeError here at runtime, which is
        # an acceptable failure mode for content this scheme can't handle.
        return sorted(_canonicalize(item) for item in value)  # type: ignore[type-var]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [
            (field.name, _canonicalize(getattr(value, field.name)))
            for field in dataclasses.fields(value)
        ]
    msg = f"Cannot canonicalize value of type {type(value).__name__!r} for audit hashing."
    raise AuditRecordNotSerializable(msg)


def _compute_record_hash(sequence: int, decision: Decision, previous_hash: str) -> str:
    """Compute the sha256 hexdigest covering ``(sequence, decision, previous_hash)``."""
    canonical = _canonicalize((sequence, decision, previous_hash))
    serialized = json.dumps(canonical, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class AuditRecord:
    """One entry in the audit chain.

    Attributes:
        sequence: This record's position in the chain, starting at 0.
        decision: The Decision being recorded.
        previous_hash: The preceding record's ``record_hash``, or
            :data:`GENESIS_PREVIOUS_HASH` if this is sequence 0.
        record_hash: This record's own hash -- see :meth:`compute_hash`.

    Raises:
        AuditRecordTampered: If ``record_hash`` does not match a fresh
            computation of this record's own content. It is
            structurally impossible to construct an ``AuditRecord``
            whose stored hash doesn't match its content.
    """

    sequence: int
    decision: Decision
    previous_hash: str
    record_hash: str

    def __post_init__(self) -> None:
        """Validate ``record_hash`` matches this record's own content."""
        if self.record_hash != self.compute_hash():
            msg = f"record_hash does not match content at sequence {self.sequence}."
            raise AuditRecordTampered(msg)

    def compute_hash(self) -> str:
        """Compute this record's hash from its own (sequence, decision, previous_hash)."""
        return _compute_record_hash(self.sequence, self.decision, self.previous_hash)


@dataclasses.dataclass(frozen=True)
class ChainVerificationResult:
    """The result of verifying an :class:`AuditChain`'s integrity.

    Attributes:
        valid: Whether every record in the chain passed verification.
        first_invalid_sequence: The sequence number of the first
            record that failed, or ``None`` if the chain is valid (or
            empty).
    """

    valid: bool
    first_invalid_sequence: int | None


class AuditChain:
    """An append-only, hash-chained sequence of AuditRecords."""

    def __init__(self, records: Iterable[AuditRecord] = ()) -> None:
        """Build a chain from an existing sequence of records (default: empty).

        Supports reloading a chain from storage: construction does not
        eagerly validate. Call :meth:`verify` explicitly once loaded.

        Args:
            records: The records to initialize the chain with, in order.
        """
        self._records: list[AuditRecord] = list(records)

    def append(self, decision: Decision) -> AuditRecord:
        """Append a new record for ``decision`` and return it.

        The only way a record enters the chain -- there is no way to
        insert, edit, or remove one afterward.

        Args:
            decision: The Decision to record.

        Returns:
            The newly-appended AuditRecord.
        """
        sequence = len(self._records)
        previous_hash = self._records[-1].record_hash if self._records else GENESIS_PREVIOUS_HASH
        record_hash = _compute_record_hash(sequence, decision, previous_hash)
        record = AuditRecord(
            sequence=sequence,
            decision=decision,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )
        self._records.append(record)
        return record

    def verify(self) -> ChainVerificationResult:
        """Walk the whole chain, checking sequence, linkage, and self-consistency.

        Any single failure anywhere means the whole chain is invalid --
        a tampered record in the middle is detected, not just one at
        the end.

        Returns:
            A ChainVerificationResult describing whether the chain is
            valid and, if not, where the first failure is.
        """
        expected_previous_hash = GENESIS_PREVIOUS_HASH
        for expected_sequence, record in enumerate(self._records):
            if (
                record.sequence != expected_sequence
                or record.previous_hash != expected_previous_hash
                or record.record_hash != record.compute_hash()
            ):
                return ChainVerificationResult(
                    valid=False,
                    first_invalid_sequence=expected_sequence,
                )
            expected_previous_hash = record.record_hash
        return ChainVerificationResult(valid=True, first_invalid_sequence=None)

    def __len__(self) -> int:
        """Return the number of records in the chain."""
        return len(self._records)

    def __iter__(self) -> Iterator[AuditRecord]:
        """Iterate over records in order, without exposing the underlying list."""
        return iter(self._records)

    def __getitem__(self, index: int) -> AuditRecord:
        """Return the record at ``index``."""
        return self._records[index]
