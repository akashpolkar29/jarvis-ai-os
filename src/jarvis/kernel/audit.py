"""The composition root for audit.history: real, invocable audit-log inspection (Phase 10).

Before this pass, the only way to see what the real, persisted audit
chain actually contains was to open its JSON file directly (bypassing
this project's own authorization/audit-logging discipline entirely) --
a real gap the 10-phase combined pass's own "audit-history CLI" task
closes.

``audit.history`` (``Effect.READ_LOCAL``, ``Tier.ALLOW`` -- the same
classification ``git.status`` already uses for "a read-only state
viewer of already-locally-known structured data," not
``fs.read_file``'s own ``EGRESS_LOCAL`` "raw arbitrary file content"
reasoning, since a record's own content here is always this project's
own structured `Decision` shape, never arbitrary file bytes) is a
static, fixed-effect capability, registered in
``build_default_registry()`` and authorized via the ordinary
``authorize_by_id()`` path, exactly like ``git.status``/``ping``.

**Real, deliberate scope boundary, matching this pass's own hard
gate**: this module reads the real audit chain via the existing,
unmodified ``JsonFileAuditStorageAdapter.load()`` -- it does not touch
that adapter's save/load format, and it does not display a timestamp
for any record, because none exists in the current, real
``AuditRecord`` shape (``sequence``/``decision``/``previous_hash``/
``record_hash`` only -- confirmed by reading ``domain/audit.py``
directly). Adding a timestamp field would be exactly the kind of
audit-chain-format change this pass's own hard gate forbids; this
module works honestly within what already exists rather than silently
proposing that change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.clock import SystemClockAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import AUDIT_HISTORY_CAPABILITY_ID, build_default_registry

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.audit import AuditRecord
    from jarvis.domain.policy import Decision


@dataclass(frozen=True)
class AuditHistoryOutcome:
    """The result of one authorize_and_view_audit_history() call.

    Attributes:
        decision: The Decision for this history view -- durably
            appended to the chain regardless of outcome.
        records: Every real, matching audit record, oldest first,
            if the decision was granted. ``()`` if denied -- never
            ``None``, since an empty result is a real, valid outcome
            (a fresh or fully-filtered-out chain), not the same as
            "never touched" the way ``MemoryWipeOutcome.deleted_count``
            distinguishes denial from an empty store.
    """

    decision: Decision
    records: tuple[AuditRecord, ...]


def authorize_and_view_audit_history(
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    limit: int | None = None,
    capability_id: str | None = None,
) -> AuditHistoryOutcome:
    """Wire up the stack, authorize viewing the real audit history, and return it if granted.

    Args:
        physical_confirmation_available: Whether a human is physically
            present. ``audit.history`` is ``Tier.ALLOW``, so this has
            no effect on the outcome -- threaded through for
            consistency, same as ``ping``/``git.status``.
        remote_confirmation_available: As above.
        chain_path: Where the real audit chain is persisted.
        limit: Return at most this many of the most recent records.
            ``None`` (the default) returns every record.
        capability_id: Only return records whose own
            ``decision.invocation.descriptor.id.value`` matches this
            exactly. ``None`` (the default) returns records for every
            capability.

    Returns:
        An ``AuditHistoryOutcome`` -- see its own docstring.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(
        chain, registry, confirmation=confirmation, clock=SystemClockAdapter()
    )

    decision = orchestrator.authorize_by_id(
        AUDIT_HISTORY_CAPABILITY_ID,
        Tainted({}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    records: tuple[AuditRecord, ...] = ()
    try:
        if decision.granted:
            matching = tuple(
                record
                for record in chain
                if capability_id is None
                or record.decision.invocation.descriptor.id.value == capability_id
            )
            records = matching[-limit:] if limit is not None else matching
    finally:
        storage.save(chain)

    return AuditHistoryOutcome(decision=decision, records=records)
