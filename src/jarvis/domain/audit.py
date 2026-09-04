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

One deliberate exception to that generic walk: a :class:`~.provenance.Tainted`
value is never canonicalized by walking into its ``.value`` directly.
Instead it is reduced to a digest of that value (see :func:`digest_value`)
-- this is what makes it possible for
:class:`~jarvis.adapters.audit_storage.JsonFileAuditStorageAdapter` to
persist only a digest of a capability invocation's arguments, never
the raw value, per ADR-0027 (work package 18; this was not true from
work package 12 through work package 17, and was caught by the
work-package-17 threat model, not by a test). See :func:`digest_value`
and the ``Tainted`` branch inside :func:`_canonicalize` for the
mechanism, and ``adapters/audit_storage.py`` for how it's used. One
consequence stated plainly: because this changes what
:func:`_canonicalize` produces for *every* ``Tainted`` value, every
``record_hash`` computed before this change becomes invalid under the
new formula -- including records whose arguments were empty. There is
no migration path; a pre-work-package-18 audit chain file cannot be
loaded by this version, by construction (the raw values needed to
recompute a valid hash under the new formula were never persisted).

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
import threading
from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING

from .errors import AuditRecordNotSerializable, AuditRecordTampered
from .provenance import Tainted

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


ARGUMENT_DIGEST_KEY = "__jarvis_argument_digest_sha256__"
"""The reserved key a reconstructed, digest-only Tainted's ``.value`` uses.

Set by :func:`jarvis.adapters.audit_storage._decode_arguments` when
rebuilding a ``Tainted`` from a persisted digest (the raw value is
never persisted -- see :func:`digest_value`). :func:`_canonicalize`
recognizes a ``Mapping`` with exactly this one key as "already a
digest" and reuses the stored hex string directly rather than hashing
it a second time -- hashing it again would produce a different digest
than the one computed the first time, breaking hash verification on
every reload. The collision risk (a genuine capability argument
mapping happening to contain exactly this key) is real but treated as
negligible given the deliberately reserved-looking name; it is not
possible to make this fully collision-proof without changing
``CapabilityInvocation.arguments``'s domain-level type, which is out
of proportion to this fix.
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
    if isinstance(value, Tainted):
        return _canonicalize_tainted(value)
    if isinstance(value, Mapping):
        return sorted((key, _canonicalize(val)) for key, val in value.items())
    if isinstance(value, (list, tuple, frozenset, set)):
        canonicalized_items = [_canonicalize(item) for item in value]
        # _canonicalize's declared return type is `object`, so mypy can't
        # see that frozenset/set items are always orderable in practice
        # (e.g. Provenance.sources is frozenset[str]); an item that
        # genuinely isn't orderable would raise TypeError here at
        # runtime, an acceptable failure mode for content this scheme
        # can't handle.
        return (
            sorted(canonicalized_items)  # type: ignore[type-var]
            if isinstance(value, (frozenset, set))
            else canonicalized_items
        )
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [
            (field.name, _canonicalize(getattr(value, field.name)))
            for field in dataclasses.fields(value)
        ]
    msg = f"Cannot canonicalize value of type {type(value).__name__!r} for audit hashing."
    raise AuditRecordNotSerializable(msg)


def _canonicalize_tainted(value: Tainted[object]) -> object:
    """Canonicalize a Tainted as a digest of its value, never the value itself.

    Checked before the generic dataclass branch would otherwise catch
    ``Tainted`` (it is itself a dataclass) and walk into ``.value``
    directly -- which is exactly the behavior this function replaces,
    per ADR-0027 (work package 18).
    """
    value_digest = digest_argument_value(value)
    return [("value_digest", value_digest), ("provenance", _canonicalize(value.provenance))]


def digest_argument_value[T](arguments: Tainted[T]) -> str:
    """Return the digest to use for a Tainted argument value, reusing one already computed.

    If ``arguments.value`` is already the one-key
    ``{ARGUMENT_DIGEST_KEY: <hex>}`` placeholder shape (only ever
    produced by reconstructing a record from persisted storage -- see
    ``adapters.audit_storage._decode_arguments``), the existing hex
    digest is reused as-is rather than hashed again: hashing it a
    second time would produce a different digest than the one computed
    when the record was first appended, which would make every
    reloaded-then-resaved record look tampered even though nothing
    was. Otherwise, ``.value`` is real content and gets hashed fresh
    via :func:`digest_value`.

    This is the single source of truth both :func:`_canonicalize_tainted`
    (live hash computation) and
    ``adapters.audit_storage._encode_arguments`` (persistence) call --
    deliberately the same function, not two independent copies of the
    same detection logic, since a divergence between them would
    silently reintroduce the double-hashing bug this exists to prevent.
    """
    raw = arguments.value
    if isinstance(raw, Mapping) and set(raw.keys()) == {ARGUMENT_DIGEST_KEY}:
        existing_digest = raw[ARGUMENT_DIGEST_KEY]
        if isinstance(existing_digest, str):
            return existing_digest
    return digest_value(raw)


def digest_value(value: object) -> str:
    """Return the sha256 hex digest of ``value``'s canonical form.

    Uses the exact same canonicalization :func:`_compute_record_hash`
    already uses for tamper-detection hashing -- deliberately the same
    kind of problem (deterministic, one-way, never needs to
    reconstruct the original), not a different one, so reusing it here
    is not a stretch. This is the public entry point for anything that
    needs a stable, one-way digest of a value it must never be able to
    (or need to) reverse -- e.g. ``adapters.audit_storage``'s
    digest-only argument persistence (ADR-0027).

    Args:
        value: The value to digest.

    Returns:
        A 64-character lowercase sha256 hexdigest.

    Raises:
        AuditRecordNotSerializable: If ``value`` contains anything
            :func:`_canonicalize` cannot represent.
    """
    canonical = _canonicalize(value)
    serialized = json.dumps(canonical, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
    """An append-only, hash-chained sequence of AuditRecords.

    :meth:`append` is internally locked (a plain ``threading.Lock``,
    stdlib-only -- compatible with this ring's own "no I/O, no async,
    no wall-clock/randomness" constraint) so two concurrent callers
    sharing one ``AuditChain`` instance can never both read the same
    pre-append ``sequence``/``previous_hash`` state. Found by a real,
    deterministic concurrency test (property-matrix/fuzzing/
    concurrency pass, Track 3, 2026-09-04): without this lock, two
    threads racing on the same instance could both compute
    ``sequence=0``, producing two audit records that both claim the
    same position in the chain -- a real, reproducible hash-chain
    corruption, not a hypothetical one. This closes the in-process
    version of that gap; the separate, cross-process case (two
    independent OS processes each holding their own ``AuditChain``,
    both writing to the same ``JsonFileAuditStorageAdapter`` file) is
    a different, larger problem this lock cannot and does not solve --
    see ``docs/threat-model/v0.md``'s own note on that.
    """

    def __init__(self, records: Iterable[AuditRecord] = ()) -> None:
        """Build a chain from an existing sequence of records (default: empty).

        Supports reloading a chain from storage: construction does not
        eagerly validate. Call :meth:`verify` explicitly once loaded.

        Args:
            records: The records to initialize the chain with, in order.
        """
        self._records: list[AuditRecord] = list(records)
        self._lock = threading.Lock()

    def append(self, decision: Decision) -> AuditRecord:
        """Append a new record for ``decision`` and return it.

        The only way a record enters the chain -- there is no way to
        insert, edit, or remove one afterward. Thread-safe: the whole
        read-compute-append sequence runs under this instance's own
        lock, so two concurrent callers can never race each other into
        computing the same ``sequence``/``previous_hash`` (see this
        class's own docstring).

        Args:
            decision: The Decision to record.

        Returns:
            The newly-appended AuditRecord.
        """
        with self._lock:
            sequence = len(self._records)
            previous_hash = (
                self._records[-1].record_hash if self._records else GENESIS_PREVIOUS_HASH
            )
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
