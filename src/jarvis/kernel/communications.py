"""The composition root for M6a's real communications capabilities -- reads and writes both.

:func:`authorize_and_list_email`, :func:`authorize_and_read_email`, and
:func:`authorize_and_list_calendar_events` are the first point real
email/calendar reads exist as actual, invocable capabilities --
mirroring `kernel/browser.py`'s own `authorize_and_capture_screenshot`
composition shape exactly (registry/storage/confirmation/orchestrator
wiring, `authorize_by_id()` against a static registry entry, the real
side effect only ever inside `if decision.granted:`).

**All three reads are static, fixed-effect capabilities**
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

**`authorize_and_send_email`/`authorize_and_create_calendar_event`
(WP-79 onward, following ADR-0057's Acceptance -- 2026-09-03, directly
by the user, in conversation, after direct review of the ADR's own
full text)** route through `EmailSendAuthorizer`/`CalendarEventAuthorizer`
directly, mirroring `authorize_and_remember`'s own composition shape
exactly (registry/storage/confirmation/orchestrator wiring) everywhere
except the authorization call itself -- neither is registered in
`build_default_registry()`, the same reason `memory.write` never is
either: the real `Effect` genuinely varies per invocation with the
outgoing content's own classification (and, for calendar, whether the
draft has attendees at all), which a statically-registered
`CapabilityDescriptor` cannot express. Both wrap their real,
directly-typed/spoken content as `Tainted(value, Provenance.user())`,
matching `authorize_and_remember`'s own identical choice -- always
`Classification.PUBLIC` here, so these calls float at
`EGRESS_SENSITIVE`/`CONFIRM` (email, or an attendee-bearing event)
never the unconditional `EGRESS_SECRET`/`DENY` floor a genuinely
`SECRET`-classified value would hit. **The identical trust-boundary
caveat `authorize_and_remember`'s own docstring already states applies
here too**: a future caller constructing this value from a
less-trusted or more sensitive source is responsible for giving it the
correct provenance before calling this function -- this function does
not, and cannot, second-guess a provenance it did not compute.

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

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarvis.adapters.audit_storage import JsonFileAuditStorageAdapter
from jarvis.adapters.confirmation import ManualConfirmationAdapter
from jarvis.application.communications.writer import CalendarEventAuthorizer, EmailSendAuthorizer
from jarvis.application.policy import AuthorizationOrchestrator
from jarvis.domain.calendar import CalendarEventDraft
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


async def authorize_and_send_email(  # noqa: PLR0913 -- one per composition-function pass-through
    to: tuple[str, ...],
    subject: str,
    body: str,
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    email_port: EmailPort,
) -> Decision:
    """Wire up the stack, authorize sending a real email, and send it only if granted.

    Args:
        to: The real recipient addresses.
        subject: The real subject line.
        body: The real message body, typed or spoken directly by the
            user -- wrapped as ``Tainted(body, Provenance.user())``,
            matching ``authorize_and_remember``'s own identical choice.
            ``egress_effect_for()`` (ADR-0057) resolves the real
            ``Effect`` this declares from that provenance's own
            classification -- ``PUBLIC`` here, so this call always
            floors at ``EGRESS_SENSITIVE``/``CONFIRM``, never the
            unconditional ``EGRESS_SECRET``/``DENY`` floor a
            ``SECRET``-classified value would hit. A future caller
            constructing this value from a less-trusted or more
            sensitive source is responsible for giving it the correct
            provenance before calling this function -- this function
            does not, and cannot, second-guess a provenance it did not
            compute (the same trust boundary ADR-0057's own Amendment
            2026-09-01, finding 1, names).
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        email_port: The real port to send through. No default (see
            module docstring for why) -- a real caller supplies its own.

    Returns:
        The real ``Decision`` -- already durably appended to the
        injected ``AuditChain`` by the time this returns. The real
        call to ``EmailPort.send_message`` happens only if ``granted``.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)
    authorizer = EmailSendAuthorizer(orchestrator)

    body_value = Tainted(body, Provenance.user())
    decision = authorizer.authorize_send(
        to, subject, body_value, orchestrator.get_current_context()
    )

    try:
        if decision.granted:
            await email_port.send_message(to, subject, body)
    finally:
        storage.save(chain)

    return decision


@dataclass(frozen=True)
class CalendarEventCreateOutcome:
    """The result of one authorize_and_create_calendar_event() call.

    Attributes:
        decision: The Decision for this create -- durably appended to
            the chain regardless of outcome.
        uid: The new event's real uid, if the decision was granted.
            ``None`` if denied.
    """

    decision: Decision
    uid: str | None


async def authorize_and_create_calendar_event(  # noqa: PLR0913 -- one per composition-function pass-through
    summary: str,
    start: str,
    end: str,
    attendees: tuple[str, ...],
    *,
    physical_confirmation_available: bool,
    remote_confirmation_available: bool,
    chain_path: Path,
    calendar_port: CalendarPort,
) -> CalendarEventCreateOutcome:
    """Wire up the stack, authorize creating a real calendar event, and create it only if granted.

    Args:
        summary: The draft event's own real summary, typed or spoken
            directly by the user -- wrapped as
            ``Tainted(summary, Provenance.user())``, matching
            ``authorize_and_send_email``'s own identical choice and
            identical trust-boundary caveat. Only consulted for
            classification when ``attendees`` is non-empty
            (``calendar_effect_for``).
        start: The real, ISO-8601 start time.
        end: The real, ISO-8601 end time.
        attendees: The real attendee addresses. An empty tuple floors
            this call at ``Effect.WRITE_LOCAL``/``Tier.CONFIRM``
            regardless of ``summary``'s own classification (``git.push``'s
            own precedent -- see ``calendar_effect_for``'s own docstring).
        physical_confirmation_available: Whether a human is physically
            present, passed straight through to the constructed
            ``ManualConfirmationAdapter``.
        remote_confirmation_available: As above, for remote confirmation.
        chain_path: Where the audit chain is persisted.
        calendar_port: The real port to create against. No default
            (see module docstring for why) -- a real caller supplies
            its own.

    Returns:
        A ``CalendarEventCreateOutcome`` -- see its own docstring.
    """
    registry = build_default_registry()
    storage = JsonFileAuditStorageAdapter(chain_path)
    chain = storage.load()

    confirmation = ManualConfirmationAdapter(
        physical_confirmation_available=physical_confirmation_available,
        remote_confirmation_available=remote_confirmation_available,
    )
    orchestrator = AuthorizationOrchestrator(chain, registry, confirmation=confirmation)
    authorizer = CalendarEventAuthorizer(orchestrator)

    summary_value = Tainted(summary, Provenance.user())
    has_attendees = bool(attendees)
    decision = authorizer.authorize_create(
        summary_value, has_attendees=has_attendees, context=orchestrator.get_current_context()
    )

    uid: str | None = None
    try:
        if decision.granted:
            draft = CalendarEventDraft(summary=summary, start=start, end=end, attendees=attendees)
            uid = await calendar_port.create_event(draft)
    finally:
        storage.save(chain)

    return CalendarEventCreateOutcome(decision=decision, uid=uid)
