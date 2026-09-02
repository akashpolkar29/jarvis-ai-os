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
**Proposed, not Accepted** — the real design's own classification
reasoning (`Effect.EGRESS_SENSITIVE`/`Effect.EGRESS_SECRET`, reused
rather than a new effect) needs the user's own direct review before
acceptance, matching M5's own "accept only once built and proven"
discipline.

**Not yet implemented.** No `ports/email.py`, `ports/calendar.py`,
`adapters/email.py`, `adapters/calendar.py`,
`application/communications/`, or `kernel/communications.py` exist in
this codebase yet — `m6a-communications.md`'s own work-package sketch
(WP-76 through WP-81) is real, objective-level planning, not a
completed or started implementation.

### Entry gate

M5, tagged `v0.5.0`, complete.

### Exit gate

Per-plugin conformance to the M0 capability/policy/audit model
(unchanged from M6's own original objective) — plus, concretely,
`m6a-communications.md`'s own six real acceptance criteria (real
classification-function tests, real unconditional-DENY property tests
for both email-send and attended-calendar-event creation, real
always-ALLOW tests for reads, real provenance-tainting tests, and a
real, skipif-guarded live test against a real mailbox/calendar).

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
**Proposed, not Accepted** — even though its own core Decision was the
user's own direct answer, in conversation, not remotely reasoned; the
document's own final written text and consequences still need the
user's own direct review before acceptance, matching M6a's/M5's own
"a relayed decision is not the same as reviewing the document" precedent.

**The central open question `m6-scoping-notes.md`'s own item 5 named
is now resolved, directly by the user**: "no auto-apply" is a
**structural boundary**, not a policy-tier gate. No `CapabilityId` for
submission exists or will exist without a new ADR explicitly
superseding ADR-0058 first; no port, adapter, or module under M6b's
own package path may call, import, or reference anything capable of
submitting data externally — enforced not just by design intent but by
a real, specified (not yet implemented) structural meta-test, mirroring
`tests/meta/test_no_response_scraping.py`'s own AST-scan precedent.

**Not yet implemented.** No `ports/draft_storage.py`,
`adapters/draft_storage.py`, `application/job_assistance/`, or
`kernel/job_assistance.py` exist in this codebase yet —
`m6b-job-assistance.md`'s own work-package sketch (WP-82 through
WP-86, continuing M6a's own shared, sequential numbering) is real,
objective-level planning, not a completed or started implementation.

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
