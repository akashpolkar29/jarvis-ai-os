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

Placeholder — objective and gates only, per this project's
rolling-wave planning. Full architecture-level design is written when
this sub-milestone actually starts, not before (see
`docs/ROADMAP.md`). **Deliberately untouched by M6a's own real design
pass** — see that pass's own report for why: M6b's central open
question (whether "no auto-apply" is a structural boundary or a
policy-tier gate) decides how, or whether, this system can ever submit
a real job application on the user's behalf, which this project's own
charter already names as exactly the kind of decision that must be
answered by the user directly, not remotely reasoned while they are
away.

### Objective

Job assistance: research and drafting only, no auto-apply.

### Entry gate

M5, tagged `v0.5.0`, complete. (M6a is not a real dependency of M6b —
the two were split precisely because they do not need to be built in
any particular order relative to each other, only after M5.)

### Exit gate

Per-plugin conformance to the M0 capability/policy/audit model.

### Complexity

Not specified in any surviving planning material.

### Known risks

Not specified in any surviving planning material.

### Not yet decided

No ports, adapters, package layout, work-package breakdown, or ADRs
exist for this sub-milestone. The real, load-bearing open question —
whether "no auto-apply" is enforced as a structural boundary (no
capability in this sub-milestone's own scope ever submits anything to
a real external system) or as a policy-tier gate (a real `Effect`/`Tier`
combination requiring `MANUAL_ONLY` confirmation for anything
resembling submission) — is named in `m6-scoping-notes.md`'s own item
5 and remains genuinely open, not decided here.

M6b's eventual design must also satisfy the standing "always legible"
principle in `docs/ROADMAP.md`: every action it takes should be
legible to Akash in real time, spoken and shown — reusing M1's `TtsPort`
and M5's `ConsolePort` once its own work package builds against them,
not inventing new voice or display mechanisms specific to M6b. A
constraint M6b's future design must satisfy, not a decision about what
its specific ports, adapters, or UI will look like — those remain
genuinely undecided.
