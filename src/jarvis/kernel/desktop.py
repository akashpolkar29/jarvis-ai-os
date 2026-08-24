"""The composition root for M3's desktop-control capability family.

Mirrors ``jarvis.kernel.music``'s ``authorize_and_run_music_command``
pattern exactly (WP-46's own "registry/orchestration shell" folded
into this work package, its first real user, rather than built empty
and speculative ahead of any capability needing it -- see
``docs/architecture/m3-desktop-control.md``'s package layout proposal
for ``kernel/desktop.py``'s intended role).

Each ``authorize_and_*`` function wires the same
registry/storage/confirmation/orchestrator pieces together, plus
whichever port that specific capability needs, and follows the exact
same enforcement ordering and audit-save guarantee ``kernel/music.py``
established: ``orchestrator.authorize_by_id()`` always runs first, the
real side effect only ever happens inside ``if decision.granted:``,
and ``storage.save(chain)`` runs in a ``finally`` block so a granted
decision is never lost from disk even if the subsequent real-world
action raises.

Terminal's real multi-step flow (WP-52) is expected to need
``application/desktop/`` orchestration beyond this module's simple
authorize-then-call-one-port-method shape -- not built here, since
nothing in this module yet needs it (the same "don't build ahead of a
real need" reasoning WP-46's own consolidation into this work package
already applied once).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.brave import BraveCliAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Provenance, Tainted
from jarvis.kernel.capabilities import (
    DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
    build_default_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.policy import Decision
    from jarvis.ports.brave import BravePort


def authorize_and_open_brave_url(
    url: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    browser: BravePort | None = None,
) -> Decision:
    """Wire up the stack, authorize opening ``url`` in Brave, and run it only if granted.

    Args:
        url: The URL to navigate to, passed straight through to
            ``browser.open_url`` if granted.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted. Loaded before
            the call and saved again after, unconditionally -- see the
            module docstring's audit-save guarantee.
        browser: The port ``url`` is sent to if granted. Defaults to a
            real ``BraveCliAdapter``. Overridable for tests, exactly as
            ``authorize_and_run_music_command``'s ``media_player`` is.

    Returns:
        The ``Decision`` for this call -- durably appended to the chain
        regardless of outcome. If granted, ``browser`` has already
        received ``open_url(url)`` by the time this returns (barring an
        exception it raised); if denied, it was never touched at all.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)

    decision = orchestrator.authorize_by_id(
        DESKTOP_BRAVE_OPEN_URL_CAPABILITY_ID,
        Tainted({"url": url}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    try:
        if decision.granted:
            real_browser = browser if browser is not None else BraveCliAdapter()
            real_browser.open_url(url)
    finally:
        storage.save(chain)

    return decision
