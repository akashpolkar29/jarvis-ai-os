"""The composition root for M6a's real, read-only communications capabilities.

:func:`authorize_and_list_email`, :func:`authorize_and_read_email`, and
:func:`authorize_and_list_calendar_events` are the first point real
email/calendar reads exist as actual, invocable capabilities --
mirroring `kernel/browser.py`'s own `authorize_and_capture_screenshot`
composition shape exactly (registry/storage/confirmation/orchestrator
wiring, `authorize_by_id()` against a static registry entry, the real
side effect only ever inside `if decision.granted:`).

**All three are static, fixed-effect capabilities**
(`Effect.EGRESS_LOCAL`, `Tier.ALLOW`) -- `m6a-communications.md`'s own
worked example: "extracting real content out to the caller is an
egress even though it never leaves the machine," the identical
reasoning `fs.read_file`/`memory.retrieve`/`browser.screenshot`
already establish. Registered in `build_default_registry()`.

**Real, adversary-influenced content is tainted at the point it
enters this codebase**, mirroring `authorize_and_capture_screenshot`'s
own real tainting exactly: every returned `EmailSummary`/`EmailMessage`/
`CalendarEvent` is individually wrapped as
`Tainted(value, Provenance.external(source=<its own real id>,
classification=Classification.SENSITIVE))` -- anyone who can email the
user, or invite them to a calendar event, can put content in front of
JARVIS, the same real threat class `browser.screenshot`'s own
docstring already names for web content. Tainted per-item, not as one
blended-source tuple: each message/event has its own real, distinct
source, the same "everything carries its own real provenance"
discipline `MemoryRecord` already follows.

**`communications.send_email`/`communications.create_calendar_event`
do not exist in this module, and no work package builds them here** --
`EmailPort.send_message`/`CalendarPort.create_event` are unimplemented
by every real adapter (blocked on ADR-0057, `Proposed`, not
`Accepted`), so there is nothing this composition root could
authorize-and-call yet. Building the dynamic-effect authorizer for
these (`application/communications/classification.py::egress_effect_for`,
WP-79 in `m6a-communications.md`'s own sketch) remains real, separate,
blocked future work -- not started by this pass.

**`email_port`/`calendar_port` have no default, on purpose** --
mirroring `kernel/job_assistance.py`'s own `providers` "no implicit
default for a genuinely undecided, per-deployment choice" precedent
exactly: which real IMAP host/CalDAV URL/account credentials to use is
real, per-deployment configuration this module does not decide.
Unlike `browser_automation`/`embedding_port` (one real adapter, no
policy ambiguity), there is no single real mailbox/calendar this
codebase could default to. A real caller constructs its own real
`ImapEmailAdapter`/`CalDavCalendarAdapter` (with its own real
`SecretPort`-resolved credential) and passes it in explicitly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.provenance import Classification, Provenance, Tainted
from jarvis.kernel.capabilities import (
    CALENDAR_LIST_EVENTS_CAPABILITY_ID,
    EMAIL_LIST_MESSAGES_CAPABILITY_ID,
    EMAIL_READ_MESSAGE_CAPABILITY_ID,
    build_default_registry,
)

if TYPE_CHECKING:
    from pathlib import Path

    from jarvis.domain.calendar import CalendarEvent
    from jarvis.domain.email import EmailMessage, EmailSummary
    from jarvis.domain.policy import Decision
    from jarvis.ports.calendar import CalendarPort
    from jarvis.ports.email import EmailPort


async def authorize_and_list_email(  # noqa: PLR0913 -- one per composition-function pass-through
    folder: str,
    limit: int,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    email_port: EmailPort,
) -> tuple[Decision, tuple[Tainted[EmailSummary], ...] | None]:
    """Wire up the stack, authorize listing ``folder``, and list real messages only if granted.

    Args:
        folder: The real IMAP folder to list.
        limit: The maximum number of real summaries to return.
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        email_port: The real port to list against. No default (see
            module docstring for why) -- a real caller supplies its own.

    Returns:
        ``(decision, summaries)`` -- ``summaries`` is real, individually
        tainted content if granted (never happens with
        ``memory.retrieve``'s own identical ``Tier.ALLOW`` reasoning
        applying here too -- confirmation is asked regardless, matching
        every other capability, but always granted), ``None`` if denied.
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
        EMAIL_LIST_MESSAGES_CAPABILITY_ID,
        Tainted({"folder": folder, "limit": limit}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    summaries: tuple[Tainted[EmailSummary], ...] | None = None
    try:
        if decision.granted:
            raw = await email_port.list_messages(folder, limit)
            summaries = tuple(
                Tainted(
                    summary,
                    Provenance.external(
                        source=summary.message_id, classification=Classification.SENSITIVE
                    ),
                )
                for summary in raw
            )
    finally:
        storage.save(chain)

    return decision, summaries


async def authorize_and_read_email(
    message_id: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    email_port: EmailPort,
) -> tuple[Decision, Tainted[EmailMessage] | None]:
    """Wire up the stack, authorize reading ``message_id``, and read it only if granted.

    See `authorize_and_list_email`'s own docstring for the shared
    argument/return shape. Raises `EmailMessageNotFoundError` (from the
    granted adapter call) if ``message_id`` matches no real message --
    not caught here, the same "a genuine operational failure propagates,
    it is not silently swallowed" discipline every other composition
    function in this codebase already follows.
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
        EMAIL_READ_MESSAGE_CAPABILITY_ID,
        Tainted({"message_id": message_id}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    message: Tainted[EmailMessage] | None = None
    try:
        if decision.granted:
            raw = await email_port.read_message(message_id)
            message = Tainted(
                raw,
                Provenance.external(source=raw.message_id, classification=Classification.SENSITIVE),
            )
    finally:
        storage.save(chain)

    return decision, message


async def authorize_and_list_calendar_events(  # noqa: PLR0913 -- one per composition-function pass-through
    start: str,
    end: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    calendar_port: CalendarPort,
) -> tuple[Decision, tuple[Tainted[CalendarEvent], ...] | None]:
    """Wire up the stack, authorize listing events in ``[start, end]``, and list only if granted.

    See `authorize_and_list_email`'s own docstring for the shared
    argument/return shape (``start``/``end`` here in place of
    ``folder``/``limit``).
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
        CALENDAR_LIST_EVENTS_CAPABILITY_ID,
        Tainted({"start": start, "end": end}, Provenance.user()),
        orchestrator.get_current_context(),
    )

    events: tuple[Tainted[CalendarEvent], ...] | None = None
    try:
        if decision.granted:
            raw = await calendar_port.list_events(start, end)
            events = tuple(
                Tainted(
                    event,
                    Provenance.external(source=event.uid, classification=Classification.SENSITIVE),
                )
                for event in raw
            )
    finally:
        storage.save(chain)

    return decision, events
