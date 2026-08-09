"""The composition root for the "ping" capability: proves the whole stack wires together.

:func:`authorize_ping` is the kernel's first real job: it is the one
place that knows about every ring at once (per this package's own
docstring), wiring a :class:`~jarvis.domain.registry.CapabilityRegistry`,
an :class:`~jarvis.adapters.audit_storage.JsonFileAuditStorageAdapter`,
a :class:`~jarvis.adapters.confirmation.ManualConfirmationAdapter`, and
an :class:`~jarvis.application.policy.AuthorizationOrchestrator`
together for one authorization call against a single, hardcoded
capability -- ``ping``, a no-op with ``Effect.READ_LOCAL`` (``Tier.ALLOW``).

This is a plain one-shot function, not a persistent in-process kernel
object: each CLI invocation is already a fresh process, so there is no
present benefit to a long-lived session here. A real, long-lived
kernel (serving a daemon over ``jarvis.ipc``, say) is future work.

Note that ``ping``'s ``Tier.ALLOW`` means it is granted unconditionally
regardless of ``physical_confirmation_available``/
``remote_confirmation_available`` -- ``evaluate()``'s ``ALLOW`` branch
never reads the context at all. Those parameters are still threaded
all the way through here (into ``ManualConfirmationAdapter`` and out
through ``orchestrator.get_current_context()``) to prove the plumbing
itself works end-to-end; they just don't change this particular
capability's outcome. A second, higher-tier hardcoded capability to
make them observably matter would be scope beyond what this module
exists to prove.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.capability import CapabilityDescriptor, CapabilityId, Effect
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.domain.registry import CapabilityRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.policy import Decision

PING_CAPABILITY_ID = CapabilityId("ping")
"""The hardcoded capability id this module registers and authorizes."""


def authorize_ping(
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
) -> Decision:
    """Wire up the whole authorization stack and authorize one call to "ping".

    Args:
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted. Loaded before
            the call and saved again after -- state persists across
            separate invocations of this function (e.g. separate CLI
            runs against the same path).

    Returns:
        The ``Decision`` produced for this single "ping" call, already
        durably appended to the chain at ``chain_path`` by the time
        this returns.
    """
    registry = CapabilityRegistry()
    ping_descriptor = CapabilityDescriptor(
        id=PING_CAPABILITY_ID,
        effects=Effect.READ_LOCAL,
        description="A no-op capability that proves the authorization stack is wired end-to-end.",
    )
    registry.register(ping_descriptor)

    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        PING_CAPABILITY_ID,
        Tainted({}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    storage.save(chain)
    return decision
