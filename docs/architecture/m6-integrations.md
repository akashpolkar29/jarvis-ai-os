# JARVIS — M6: Integrations

M6's own real scoping (`docs/architecture/m6-scoping-notes.md`,
2026-09-01) split this milestone into two real, separately-scoped
sub-milestones — the user's own direct answer to that document's item
1. This file now covers both; each gets its own section below, at
whatever real depth its own scoping/design has actually reached — per
this project's own rolling-wave planning, a section's own depth here
never gets ahead of what real work has actually happened for it.

Docker and ROS2, both real, named parts of this milestone's original
objective, were both dropped during that same real scoping pass —
Docker because M3 already fully satisfies it, ROS2 because no real
product reason for it was ever found (see
`m6-scoping-notes.md`'s own "Resolved" section for the full reasoning).
Neither appears in either sub-milestone below.

## M6a — Communications & Productivity

**No longer a placeholder.** A real design exists:
[`docs/architecture/m6a-communications.md`](m6a-communications.md) —
email (IMAP read, SMTP send), calendar (CalDAV), and research
(resolved: no new capability, reuses M5's existing
`BrowserAutomationPort` unmodified). One new ADR,
[`docs/adr/0057-email-send-and-attended-calendar-events-reuse-egress-sensitive-egress-secret.md`](../adr/0057-email-send-and-attended-calendar-events-reuse-egress-sensitive-egress-secret.md),
**Accepted (2026-09-03, directly by the user, in conversation, after
direct review of the ADR's own full text)** — the design's own
classification reasoning (`Effect.EGRESS_SENSITIVE`/`Effect.EGRESS_SECRET`,
reused rather than a new effect) is now settled. **Stale as of
2026-09-04, corrected 2026-09-03 already, restated here for real
consistency**: `Effect.EGRESS_SENSITIVE` was ADR-0057's own original
choice for non-`SECRET` content, since amended by ADR-0059 to
`Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`/`Tier.MANUAL_ONLY` — see
this section's own "real gap found and closed" paragraph below for
the full account, not superseded by this earlier paragraph.

**Both halves now implemented and tested, real, invocable code
(WP-76 through WP-80 for reads, WP-79 onward for writes, all
2026-09-03).** `ports/email.py`, `ports/calendar.py`,
`adapters/email.py` (real `ImapEmailAdapter`, stdlib `imaplib` +
`smtplib`), `adapters/calendar.py` (real `CalDavCalendarAdapter`, the
real `caldav` library), `application/communications/` (real
`classification.py`'s `egress_effect_for`/`calendar_effect_for`, real
`writer.py`'s `EmailSendAuthorizer`/`CalendarEventAuthorizer`), and
`kernel/communications.py` (`communications.list_email`/
`communications.read_email`/`communications.list_calendar_events` as
static `Effect.EGRESS_LOCAL`/`Tier.ALLOW` capabilities;
`authorize_and_send_email`/`authorize_and_create_calendar_event` as
dynamic-effect capabilities, mirroring `memory.write`'s own
not-statically-registered precedent) all exist. `EmailPort.send_message`/
`CalendarPort.create_event` are real implementations now — the
structural meta-test that once proved neither existed
(`tests/meta/test_communications_no_send_or_create.py`) has been
retired, its invariant now intentionally superseded by ADR-0057's own
Acceptance, not left stale. See `docs/threat-model/v0.md`'s own
"Milestone 6a additions" and its write-half follow-up note for the
full account, including the real, deliberately conservative scoping
choice the read-only pass made before ADR-0057 was Accepted (even
attendee-less `create_event` was left unimplemented until then, for
exactly one clean boundary rather than a partial write path).

**A real gap found and closed 2026-09-03, after both write
capabilities were built and CLI-wired**: ADR-0057's own original
`Tier.CONFIRM` floor for `send_message`/attendee-bearing `create_event`
did not actually satisfy the project's own founding charter, which
names "sending emails" explicitly among actions requiring "manual
confirmation through the desktop interface," never voice/remote alone
— `Tier.CONFIRM` is remote-satisfiable by design
(`domain/policy.py::evaluate()`). See
[`docs/adr/0059-email-and-attended-calendar-event-confirmation-tier-may-not-satisfy-the-charter.md`](../adr/0059-email-and-attended-calendar-event-confirmation-tier-may-not-satisfy-the-charter.md)
(**Accepted, 2026-09-03, directly by the user, in conversation**) and
`docs/threat-model/v0.md`'s own matching note. **The fix is real, not
just documented**: `egress_effect_for` (`application/communications/classification.py`)
now returns `Effect.DESTRUCTIVE | Effect.IRREVERSIBLE`/`Tier.MANUAL_ONLY`
for non-`SECRET` content, reusing `git.force_push`'s/`memory.forget`'s
own existing effect combination — never remote-satisfiable, proven by
real property tests (`tests/property/test_communications_writer.py`)
asserting `decision.granted == context.physical_confirmation_available`
under every real `PolicyContext`. **Stale as of 2026-09-04**: this
paragraph originally read "voice grammar for either write capability
remains out of scope" — since closed, 2026-09-04 (overnight Track 3),
directly per the user's own already-made decision. `kernel/intent.py`
gained real "send email"/"create event" two-word command keywords;
`kernel/voice_loop.py` gained `email_port`/`calendar_port`, optional
with no safe default. Real tests prove voice does not bypass
ADR-0059's `Tier.MANUAL_ONLY` floor in any way — a denied physical
confirmation never reaches the real port. See
`docs/threat-model/v0.md`'s own "Overnight Track 3" note.

### Entry gate

M5, tagged `v0.5.0`, complete.

### Exit gate

Per-plugin conformance to the M0 capability/policy/audit model
(unchanged from M6's own original objective) — plus, concretely,
`m6a-communications.md`'s own seven real acceptance criteria: six of
seven met (real classification-function tests, real unconditional-DENY
property tests for both email-send and attended-calendar-event
creation, real always-ALLOW tests for reads, real provenance-tainting
tests, and the real all-or-nothing multi-recipient property test); only
the real, skipif-guarded live test against a real mailbox/calendar
remains unmet, honestly skipped, no real test-account credentials
configured anywhere in this environment.

## M6b — Job Assistance

**No longer a placeholder.** A real design exists:
[`docs/architecture/m6b-job-assistance.md`](m6b-job-assistance.md) —
research (resolved: no new port, reuses M5's existing
`BrowserAutomationPort` unmodified, the identical conclusion M6a's own
item 6 reached, checked separately rather than assumed) and drafting
(a real cover letter/resume-text capability, using M2's existing
`UnverifiableTaskHandler` — not `Dispatcher`, checked and rejected for
a stated reason — plus one new, minimal write port,
`DraftStoragePort`). One new ADR,
[`docs/adr/0058-m6b-no-auto-apply-is-a-structural-boundary-not-a-policy-tier-gate.md`](../adr/0058-m6b-no-auto-apply-is-a-structural-boundary-not-a-policy-tier-gate.md),
**Accepted (2026-09-02, directly by the user, in conversation)** —
its own core Decision was already the user's own direct answer, and
this document's own final written text was then surfaced to them in
full before they explicitly accepted it, matching this project's own
"a relayed decision is not the same as reviewing the document" bar,
satisfied here rather than merely noted as still outstanding.

**The central open question `m6-scoping-notes.md`'s own item 5 named
is now resolved, directly by the user**: "no auto-apply" is a
**structural boundary**, not a policy-tier gate. No `CapabilityId` for
submission exists or will exist without a new ADR explicitly
superseding ADR-0058 first; no port, adapter, or module under M6b's
own package path may call, import, or reference anything capable of
submitting data externally — enforced not just by design intent but by
a real, implemented, passing structural meta-test
(`tests/meta/test_job_assistance_no_submission.py`), mirroring
`tests/meta/test_no_response_scraping.py`'s own AST-scan precedent,
landed and proven *before* any real capability code existed.

**Code-complete (WP-82 through WP-85), all gates pass.** `ports/draft_storage.py`,
`adapters/draft_storage.py`, `application/job_assistance/`
(`classification.py`, `drafting.py`), and `kernel/job_assistance.py`
all exist and are real, tested, invocable code — see
`docs/threat-model/v0.md`'s own "Milestone 6b additions" for what was
actually built and verified, including a real, conservative
`SECRET`-input implementation default flagged for the user's own
confirmation (not silently decided) and the structural meta-test's own
real, named limits. WP-86 (this closeout) is the last work package in
the design doc's own sketch. **Tagged `v0.6.0` 2026-09-04**, together
with M6a, out of strict milestone-sequential order (M3 remains
untagged) — see `CLAUDE.md`'s Current Status and the tag message
itself for the full account of what shipped alongside M6a/M6b.

### Objective

Job assistance: research and drafting only, no auto-apply.

### Entry gate

M5, tagged `v0.5.0`, complete. (M6a is not a real dependency of M6b —
the two were split precisely because they do not need to be built in
any particular order relative to each other, only after M5.)

### Exit gate

Per-plugin conformance to the M0 capability/policy/audit model
(unchanged from M6's own original objective) — plus, concretely,
`m6b-job-assistance.md`'s own six real acceptance criteria (the
capability's own real `Effect`/`Tier` test, a denied-invocation
never-calls-the-provider test, a granted-invocation
exactly-one-save test, a never-overwrites test, the three structural
meta-test assertions each with their own "fires on a deliberate
violation" proof, and a test proving `browser.open_page` is the only
real action taken when a job posting's own application page is
relevant).

### Complexity

Not specified in any surviving planning material.

### Known risks

Not specified in any surviving planning material. **One real,
deliberately deferred question, named in `m6b-job-assistance.md`
itself, not resolved here**: whether `Classification.SECRET` content
used as drafting input deserves the same unconditional-DENY,
never-persisted protection `Effect.MEMORY_WRITE` (ADR-0049) already
gives memory writes, rather than the ordinary `WRITE_LOCAL`/`CONFIRM`
floor this design currently uses.

M6b's eventual implementation must also satisfy the standing "always
legible" principle in `docs/ROADMAP.md`: every action it takes should
be legible to Akash in real time, spoken and shown — reusing M1's
`TtsPort` and M5's `ConsolePort` once its own work package builds
against them, not inventing new voice or display mechanisms specific
to M6b, matching M6a's own identical deferral to implementation time.
