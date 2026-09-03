# JARVIS — M6a: Communications & Productivity (email, calendar, research)

**Status: real design, drafted 2026-09-01, not yet approved — and,
like M5's own design doc, resting on reasoning worked through while
away from the machine, not confirmed by the user directly in this
pass.** This document replaces the placeholder that existed at this
path before this pass, per this project's own rolling-wave planning
principle (see `docs/ROADMAP.md`) — written only once M6a genuinely
became the next milestone to scope
(`m6-scoping-notes.md`'s own six questions, four answered directly by
the user in conversation on 2026-09-01, this document resolving the
fifth — item 6, research — and consuming the other four as given).

**Updated 2026-09-03 — this design is now fully real, implemented, and
tested end to end, both halves.** The read half landed first
(WP-76 through WP-80); **ADR-0057 was then Accepted 2026-09-03,
directly by the user, in conversation, after direct review of its own
full text** — closing out the classification question below as
settled, not outstanding — and the write half (`send_message`/
`create_event`) was built immediately after, in the same pass (WP-79
onward): `application/communications/classification.py`
(`egress_effect_for`/`calendar_effect_for`), `EmailSendAuthorizer`/
`CalendarEventAuthorizer` (`application/communications/writer.py`),
real `smtplib`-backed `send_message` on `ImapEmailAdapter`, real
`caldav`-backed `create_event` on `CalDavCalendarAdapter` (via
`Calendar.add_event`), and `kernel/communications.py`'s
`authorize_and_send_email`/`authorize_and_create_calendar_event`. The
read-only pass's own deliberately conservative scoping choice
(implementing neither `send_message` nor `create_event`, attendee-less
or not, until ADR-0057's Acceptance) is now superseded by real code —
see `docs/threat-model/v0.md`'s own "Milestone 6a additions" and its
follow-up write-half note for the full, real account of both passes.
This document's own classification reasoning below is unchanged from
its original, remotely-reasoned draft — that reasoning is what the
user reviewed and accepted, and what the real code above now
implements.

**Real, load-bearing difference from M6a's own scoping precedent,
stated plainly**: the four scoping answers this design *starts from*
(Docker/ROS2 dropped, IMAP/CalDAV chosen, M6a/M6b split) were each
confirmed by the user directly, in conversation. **Everything past
that point — the real port shapes, the `Effect`/`Tier` classification
reasoning, ADR-0057 itself — was this pass's own reasoning, worked
through once while the user was away, the same "remotely-reasoned
working assumption" caveat `m5-browser-coding.md`'s own header states
for its own five answers** — until 2026-09-03, when the user reviewed
the classification reasoning below directly and accepted ADR-0057
as-is, closing out that provenance gap.

`m6-scoping-notes.md` itself remains untouched, real research and real
open questions, exactly as it was before this document existed — this
document resolves its item 6 and leaves item 5 (M6b's own auto-apply
boundary question) entirely alone, out of scope for this document,
per the user's own explicit instruction for this pass.

## M6a's own scope, restated precisely

Communications/productivity: email (IMAP read, SMTP send — see
"A real technical correction" below), calendar (CalDAV read/write),
and research (resolved below: no new capability, reuses M5's existing
`BrowserAutomationPort`). Vendor-neutral throughout, per ADR-0021 and
the user's own resolved answer to `m6-scoping-notes.md`'s item 4 — no
provider-specific API (Gmail/Outlook/Google Calendar SDKs) anywhere in
this design.

**A real technical correction made while drafting, not silently
smoothed over**: the working instruction for this pass described email
as "via IMAP (read + send)." That is not technically accurate — IMAP
is a mailbox-*reading*/management protocol only; it has no mechanism
for originating a new outbound message at all. Sending real email
requires SMTP, a genuinely different protocol. This document corrects
that: `EmailPort` covers both, backed by two different real protocol
libraries internally (`imaplib`, standard library, for reading;
`smtplib`, also standard library, for sending) — one port expressing
the conceptual capability ("email"), the same way `BrowserAutomationPort`
already bundles several distinct real CDP JSON-RPC domains behind one
port.

## Item 6, resolved: research needs no new port

Checked directly against `BrowserAutomationPort`'s real, existing
interface (`ports/browser_automation.py`) before deciding, not assumed:

- `open_page(url)` — navigates to any real URL, including a search
  engine's results page or an arbitrary article.
- `query_dom(handle, selector)` — returns the real outer HTML of any
  element matching a CSS selector against the page's live DOM.
  `query_dom(handle, "body")` returns the entire page's real content;
  a caller needing cleaner extracted text over raw HTML does that
  parsing itself, in application-layer code, the same way any
  HTML-to-text step would regardless of which port supplied the HTML —
  not a gap in the port itself.
- `capture_screenshot(handle)` — real visual capture, if a research
  task ever needs to *show* a source rather than just read its text.
- `close(handle)` — real cleanup, already required after every
  `open_page` call.

These four primitives are sufficient for the real, minimal shape
"research" needs: navigate to a source, read its real content,
optionally show it, clean up. **No new port is needed.** A real
"research" capability is application-layer orchestration on top of
these already-existing, already-authorized primitives — structurally
identical to how M5's own coding-loop wrapper (`application/coding/loop.py`)
is new orchestration over `Dispatcher`/`WorkspacePort` left completely
unmodified, not a new port either.

**Two real, honest limitations, named rather than solved
speculatively**, matching this document's own "no design assumed
where none is needed" discipline:

- **No multi-page session.** `open_page` always launches a fresh,
  dedicated browser instance; there is no `navigate(handle, url)` to
  reuse one already-open page for a second URL. A research task
  visiting five sources today means five real, separate browser
  instances, each opened and closed in turn — real resource overhead,
  not a correctness problem, and not a blocking gap for a first, real
  research capability. Reducing that overhead (a real `navigate`
  method on `BrowserAutomationPort`) is genuinely deferred, future
  work, not designed here.
- **No caching.** Nothing in `BrowserAutomationPort` persists a
  fetched page's content between calls; a research task that revisits
  the same source twice fetches it twice, for real, both times. A
  real, deferred optimization question, not a scope gap this document
  resolves now.

No new capability, no new `CapabilityId`, no new `Effect`/`Tier`
question for research: every real research action authorizes through
`kernel/browser.py`'s already-Accepted `browser.open_page`/
`browser.screenshot`/`browser.inspect_dom`/`browser.close_page`,
completely unmodified. Whatever application-layer orchestration a
future work package builds on top is real, separate implementation
work — not designed in this document, the same way M5's own coding-loop
wrapper's exact shape was designed in `m5-browser-coding.md` but not
built there.

## Email: `EmailPort`

```python
@dataclass(frozen=True)
class EmailSummary:
    """One message's own real headers, without its full body."""

    message_id: str
    sender: str
    subject: str
    received_at: str  # ISO-8601, real value from the real server; ClockPort not needed here (server-authoritative, not JARVIS-authoritative time)


@dataclass(frozen=True)
class EmailMessage:
    """One real message's full, real content."""

    message_id: str
    sender: str
    recipients: tuple[str, ...]
    subject: str
    body: str
    received_at: str


class EmailPort(Protocol):
    async def list_messages(self, folder: str, limit: int) -> tuple[EmailSummary, ...]: ...
    async def read_message(self, message_id: str) -> EmailMessage: ...
    async def send_message(self, to: tuple[str, ...], subject: str, body: str) -> None: ...
```

**Amended 2026-09-01 (real gap-hunt pass, before implementation)**:
`send_message`'s own `to` parameter is `tuple[str, ...]`, not a bare
`str` — a real email capability needs to address more than one real
recipient in the ordinary case. This does not weaken ADR-0057's own
classification guarantee, it strengthens the statement of it:
classification runs once, over the whole message, for the entire
call — there is no code path where a `Classification.SECRET` body
sends to some addresses in `to` and not others; the capability
invocation is atomic. See ADR-0057's own "Amendment 2026-09-01" for
the full reasoning.

`domain/email.py` holds `EmailSummary`/`EmailMessage` — plain,
stdlib-only dataclasses, matching `PageHandle`'s own "explicit, typed
fields, not one opaque blob" precedent. `received_at` is a plain `str`
(the real server-reported timestamp, ISO-8601), not a domain
`datetime` object requiring `ClockPort` — the value is authoritative
from the remote IMAP server, not generated by JARVIS itself, the same
reasoning `PageHandle`'s own fields are plain adapter-reported values,
not JARVIS-generated ones.

### Effect/Tier classification for email — the real decision this document's own ADR-0057 records

**Reading** (`list_messages`/`read_message`): `Effect.EGRESS_LOCAL`
(`Tier.ALLOW`), the identical shape `fs.read_file`/`memory.retrieve`/
`browser.screenshot`/`browser.inspect_dom` already established —
"extracting real content out to the caller is an egress even though it
never leaves the machine," and reading one's own already-received
mail needs no per-call confirmation, the same as reading a local file.
The *returned* content is real, adversary-influenced material (anyone
who can email the user can put content in front of JARVIS) — tagged
`Provenance.external(source=message_id, classification=Classification.SENSITIVE)`,
mirroring `browser.screenshot`'s own real tainting exactly (`Trust.UNTRUSTED_EXTERNAL`
implied by `external()`, `Classification.SENSITIVE` since email is, if
anything, more personal than an arbitrary web page). A prompt-injection
attempt embedded in a real email's body is exactly the same real
threat class `browser.screenshot`'s own docstring already names for
web content — this design inherits that precedent, does not invent a
new one.

**Sending** (`send_message`) is a real, structurally different case:
content genuinely *leaves the machine*, addressed to a real, specific
external party who was not already going to receive it. This is
exactly what `Effect.EGRESS_SENSITIVE`/`Effect.EGRESS_SECRET` already
exist to express (`ADR-0038`, `application/reasoning/classification.py`'s
own `egress_effect_for`) — **and, unlike `Effect.MEMORY_WRITE`'s own
real precedent (ADR-0049), reuse is the *correct* call here, not a
taxonomy-blurring shortcut.** ADR-0049's own reasoning for adding a
*new* effect rather than reusing `EGRESS_SECRET` was specific and
narrow: "a memory write never leaves the machine at all — reusing
that name here would make the effect taxonomy actively misleading."
Email genuinely does leave the machine, to a genuine external party —
the exact condition `EGRESS_SENSITIVE`/`EGRESS_SECRET` were built to
name. No new `Effect` is proposed by this document's own ADR.

A real, per-invocation classification function —
`application/communications/classification.py`'s own `egress_effect_for`,
structurally identical to (but a real, separate function from,
matching `application/coding/classification.py`'s own precedent of
mirroring `application/memory/classification.py`'s shape rather than
importing it across milestone-scoped packages) M2's own
`application/reasoning/classification.py::egress_effect_for` — inspects
the outgoing message body's real `Classification` and returns
`Effect.EGRESS_SECRET` for `Classification.SECRET` (unconditional
`Tier.DENY` — an email can never carry a value classified SECRET,
full stop, the same zero-tolerance this project already applies to
cloud-provider egress and memory writes) or `Effect.EGRESS_SENSITIVE`
for everything else (`Tier.CONFIRM` — ask first, every time, matching
this project's own "an ordinary local write already gets a CONFIRM
gate" baseline, applied here to "an ordinary outbound message").

**Real, deliberately deferred question, named rather than assumed
away**: the classification above is a *content* classification (what's
in the body), not a *recipient* classification (who it's going to).
A future refinement might reasonably distinguish "sending known,
already-trusted content to a new recipient" from "sending untrusted,
possibly-synthesized content" — real, separate design work this
document does not invent speculatively, matching every other
`m6-scoping-notes.md`-adjacent deferral in this project's own
discipline.

**Real trust-boundary caveat, made explicit by the 2026-09-01
gap-hunt pass, mirroring `kernel/memory.py`'s own identical caveat for
`authorize_and_remember` word for word**: `egress_effect_for`
*classifies* the body's already-assigned `Classification`; it does not
*detect* anything. Nothing in this mechanism scans the real text for
something that looks like a leaked secret — if whichever real caller
constructs the outgoing body's `Tainted` value assigns it
`Classification.PUBLIC` without genuinely considering whether the text
contains something sensitive, a real secret embedded in otherwise
ordinary prose reaches `Tier.CONFIRM`, not the unconditional `DENY`
this design's own guarantee depends on. This is not a new risk unique
to email — every dynamic-effect capability in this codebase (memory
write, coding-agent write) carries the identical caveat, stated
explicitly at each one's own site. Whichever work package first builds
a real caller (WP-79 onward) is responsible for real, considered
classification at the point the outgoing content is constructed, the
same responsibility `authorize_and_remember`'s own callers already
carry.

**Real, explicit ordering requirement, not merely implied by
"mirrors the existing pattern"**: `egress_effect_for` must be called
and its result used to build the real `CapabilityInvocation`
`AuthorizationOrchestrator.authorize()` evaluates, strictly *before*
`EmailPort.send_message`/`CalendarPort.create_event` is ever invoked
against the real adapter — and only if that call's own `Decision.granted`
is `True`. See ADR-0057's own "Amendment 2026-09-01" for the full
statement; this is now a binding requirement of that ADR's own
Decision, not just a structural resemblance to
`MemoryWriteAuthorizer`/`CodeWriteAuthorizer`.

## Calendar: `CalendarPort`

```python
@dataclass(frozen=True)
class CalendarEvent:
    """One real, existing calendar event."""

    uid: str
    summary: str
    start: str  # ISO-8601, server-authoritative
    end: str
    attendees: tuple[str, ...]


@dataclass(frozen=True)
class CalendarEventDraft:
    """A not-yet-created event's own real content."""

    summary: str
    start: str
    end: str
    attendees: tuple[str, ...]


class CalendarPort(Protocol):
    async def list_events(self, start: str, end: str) -> tuple[CalendarEvent, ...]: ...
    async def create_event(
        self, draft: CalendarEventDraft
    ) -> str: ...  # returns the new event's real uid
```

`domain/calendar.py` holds both dataclasses, same reasoning as
`domain/email.py` above.

### Effect/Tier classification for calendar

**Reading** (`list_events`): `Effect.EGRESS_LOCAL`/`Tier.ALLOW`, same
reasoning as email reads.

**Creating an event with no attendees**: a real, deliberate
`Effect.WRITE_LOCAL`/`Tier.CONFIRM` — **not** `EGRESS_SENSITIVE`,
despite the event physically being written to a remote CalDAV server,
not this machine. Directly grounded in this project's own existing,
already-Accepted precedent, not invented for this document: `git.push`
(`kernel/capabilities.py`) — a real, genuinely network-remote action —
is classified `Effect.WRITE_LOCAL`, with its own real description "An
ordinary fast-forward push to a branch **the user already owns**." A
CalDAV write to the user's own calendar account is the identical
shape: real network egress, but to infrastructure the user themselves
already controls, not a new external party gaining anything. "Local"
in this codebase's own established vocabulary has never meant
"stays on this physical machine" — `git.push` already settled that —
it means "stays within the user's own owned/controlled systems."

**Creating an event *with* attendees**: real, different case — most
real CalDAV servers and calendar clients send invite emails to
attendees automatically on real event creation, meaning this action
has the exact same "reaches a new external party" shape `send_message`
does. Classified the identical way: the same
`application/communications/classification.py::egress_effect_for`
function, applied to the event's own real content (summary is the
closest analog to a message body; a `Classification.SECRET` summary —
implausible in practice, but not structurally impossible — still
floors `DENY`, everything else floors `CONFIRM`). One real
classification function serves both `send_message` and
`create_event`-with-attendees; not two parallel copies.

**Real, named future bypass risk, flagged by the 2026-09-01 gap-hunt
pass**: `CalendarPort` as designed here has no `update_event`/
`add_attendees` method — `create_event` is the only real write — so no
bypass exists in what is designed today. But any future extension
adding one **must** route an attendee-affecting write through the
identical `egress_effect_for` classification `create_event` already
requires, not default it to `Effect.WRITE_LOCAL` on the reasoning that
"updating" is a lesser action than "creating." Adding attendees to an
already-existing event reaches a new external party exactly the way
creating a new event with attendees does — the risk this ADR exists to
close does not depend on whether the event object itself is new. See
ADR-0057's own "Amendment 2026-09-01," finding 4, for the full
statement.

## Package/class layout

```
domain/
    email.py              - EmailSummary, EmailMessage
    calendar.py            - CalendarEvent, CalendarEventDraft
ports/
    email.py                - EmailPort
    calendar.py              - CalendarPort
adapters/
    email.py                  - ImapEmailAdapter (imaplib + smtplib,
                                 both stdlib -- no new third-party
                                 dependency for email specifically).
                                 Real, deliberate naming deviation from
                                 this sketch: kept its original
                                 read-only-era class name rather than
                                 renaming to ImapSmtpEmailAdapter --
                                 renaming would have touched every real
                                 caller/test for no functional benefit
                                 (see the adapter's own module
                                 docstring).
    calendar.py                - CalDavCalendarAdapter (the caldav
                                 library, real RFC4791 client,
                                 evaluated in m6-scoping-notes.md's own
                                 Part 2 research)
application/
    communications/
        classification.py       - egress_effect_for(classification),
                                   mirrors application/reasoning's and
                                   application/memory's own split,
                                   shared by send_message and
                                   create_event-with-attendees
kernel/
    capabilities.py               - extended: EMAIL_LIST_MESSAGES_CAPABILITY_ID/
                                     EMAIL_READ_MESSAGE_CAPABILITY_ID/
                                     CALENDAR_LIST_EVENTS_CAPABILITY_ID
                                     (static, EGRESS_LOCAL) registered
                                     in build_default_registry();
                                     email.send_message/calendar.create_event
                                     are NOT registered there, mirroring
                                     memory.write's own precedent
                                     exactly -- their real Effect
                                     varies per invocation with the
                                     content's own classification,
                                     which a static registry entry
                                     cannot express.
    communications.py              - composition root: authorize_and_*
                                     functions, mirroring
                                     kernel/browser.py's/kernel/memory.py's
                                     own registry/storage/confirmation/
                                     orchestrator wiring exactly. The
                                     two dynamic-effect capabilities
                                     (send_message, create_event) route
                                     through a real
                                     EmailSendAuthorizer/CalendarEventAuthorizer,
                                     the identical shape
                                     MemoryWriteAuthorizer/CodeWriteAuthorizer
                                     already established.
```

No new port needed for research (see above); no new `SecretPort`
capability needed either — IMAP/SMTP/CalDAV credentials resolve
through the existing, unmodified `SecretPort` (ADR-0042), the same way
every credentialed adapter in this codebase already does.

## Confirmation boundary / "always legible"

`ConfirmationPort`/`ManualConfirmationAdapter` and
`PhysicalConfirmationPort`/`Gtk4PhysicalConfirmationAdapter` are reused
completely unmodified — no new confirmation surface, matching every
milestone since M1. `TtsPort`/`ConsolePort` (M1/M5) are the real
mechanisms M6a's own eventual real work package should wire a granted
`send_message`/`create_event` call through, satisfying
`docs/ROADMAP.md`'s own "always legible" standing principle the same
way `browser.open_page` already does — not designed further here,
matching WP-74's own "no specific views" discipline; which specific
capabilities get a console line is real, deferred implementation
detail.

## Acceptance criteria

**Status as of 2026-09-03**: 1–5 and 7 are met, real, and passing.
Only 6 (the real, live, skipif-guarded test) remains unmet — no real
test-account IMAP/SMTP/CalDAV credentials are configured anywhere in
this environment, matching every other network-dependent adapter's
own established precedent in this codebase.

1. **Met.** A real test proves `egress_effect_for` (communications)
   returns `Effect.EGRESS_SECRET` for `Classification.SECRET` and
   `Effect.EGRESS_SENSITIVE` for every other classification —
   mirroring `application/reasoning`'s and `application/memory`'s own
   required classification-function test shape
   (`tests/unit/application/communications/test_classification.py`).
2. **Met.** A real test, through the real `AuthorizationOrchestrator`,
   proves a `Classification.SECRET` email body is denied
   unconditionally when sent — including when
   `physical_confirmation_available=True` — matching ADR-0038/ADR-0049/
   ADR-0056's own required property-test rigor, applied here for a
   fourth time (`tests/property/test_communications_writer.py`).
3. **Met.** The identical property test applies to `create_event` with
   attendees and a `Classification.SECRET` summary (same file).
4. **Met.** A real test proves `list_messages`/`read_message`/
   `list_events` are always granted (`Tier.ALLOW`), regardless of
   confirmation flags, matching `memory.retrieve`'s own equivalent test
   (`tests/unit/test_communications_kernel.py`).
5. **Met.** A real test proves a read email's returned `EmailMessage`
   carries `Trust.UNTRUSTED_EXTERNAL`/`Classification.SENSITIVE`
   provenance, mirroring `browser.screenshot`'s own required tainting
   test (same file).
6. **Not met.** A real, live test (skipif-guarded on real,
   test-account IMAP/SMTP/CalDAV credentials being configured —
   mirroring `test_real_cdp_flow_against_a_local_page`'s own
   real-infrastructure precedent, honestly skipped in CI) proving the
   real adapter can list, read, and send a real message against a real
   mailbox, and list/create a real event against a real calendar. The
   skip-guarded test stubs exist (`test_real_imap_smtp_flow_against_a_configured_mailbox`
   in `tests/unit/adapters/test_email.py`); no real credentials are
   configured anywhere in this environment to actually run it.
7. **Met.** (2026-09-01 gap-hunt amendment) A real test proves a
   `Classification.SECRET` body addressed to multiple real recipients
   (`to` with more than one element) is denied unconditionally — the
   real, direct proof of ADR-0057's own "all-or-nothing, no partial
   send" amendment, not merely asserted from the single-invocation
   shape (`tests/property/test_communications_writer.py`).

**Incomplete, stated plainly rather than padded**: this list does not
cover the real `caldav`-vs-alternative library evaluation (real,
separate work this pass did not revisit), the real console-line wiring
for any M6a capability (WP-74's own "no specific views" discipline
extended here — still open), a real CLI subcommand or voice grammar
for either write capability (no real caller invokes
`authorize_and_send_email`/`authorize_and_create_calendar_event` yet),
or anything from M6b (out of this document's own scope entirely).

## Work-package sketch (objective-level only)

Matching the depth M3/M4/M5's own deliverables were scoped at before
implementation started:

- **WP-76 — `EmailPort`/`CalendarPort` shape.** Contract tests only,
  against fakes — no real IMAP/SMTP/CalDAV client yet, the same
  ordering `BrowserAutomationPort`/`SandboxPort`/`MemoryWritePort` each
  followed.
- **WP-77 — Real IMAP/SMTP adapter.** `ImapSmtpEmailAdapter`, both
  stdlib (`imaplib`, `smtplib`) — no new third-party dependency.
- **WP-78 — Real CalDAV adapter.** `CalDavCalendarAdapter`, real
  evaluation of the `caldav` library specifically (this document's own
  Part 2 research names it as the real, current option, not a
  confirmed final choice).
- **WP-79 — `application/communications/classification.py` and the
  two dynamic-effect authorizers.** The safety-critical piece, landing
  before any composition-root wiring calls it in anger — matching
  WP-70's own "safety-critical piece lands first" ordering.
- **WP-80 — `kernel/communications.py` composition root.** Real,
  invocable capabilities — the first point any of this is actually
  callable.
- **WP-81 — M6a threat-model closeout.** Mirroring WP-64/WP-75's own
  role exactly.

**Not included in this sketch, deliberately**: any work package for
research's own application-layer orchestration (a real, separate,
future decision on whether/when to build it, since item 6's own
resolution above already establishes no new port is needed regardless
of when or whether that orchestration gets built), and anything from
M6b (an entirely separate document, not started).
