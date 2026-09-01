# M6 scoping notes — research and questions, not a design

**Status: four of six real scope questions answered directly by the
user in conversation (2026-09-01); two remain genuinely open, deferred
to whichever future pass begins each surviving sub-milestone's own real
design.** This is not `m6-integrations.md`'s real content, not an ADR,
not a design. Per this project's rolling-wave planning principle
(`docs/ROADMAP.md`) and CLAUDE.md's own hard rule ("never silently
change the architecture... propose a fix as a new ADR, and wait for
approval"), each surviving sub-milestone's own real design starts only
once its own turn genuinely arrives — the same discipline that kept
`m3-desktop-control.md`/`m4-memory-retrieval.md`/`m5-browser-coding.md`
each a stub until their own milestone genuinely started. Nothing here
authorizes writing `ports/`, `adapters/`, or `application/` code, or an
ADR, for M6a/M6b. **See "Resolved, 2026-09-01" at the bottom of this
document for the real answers** — read that section first if only
reading one.

`m6-integrations.md` itself remains untouched, gate-only, exactly as
it was before this document existed.

## Why this document exists: the pattern every prior milestone needed

No milestone got a real design by just expanding its one-line ROADMAP
objective. Each needed a small number of genuine, user-decided scope
questions resolved first — M2 needed the recovered pre-M0 design
reconciled against real M0 state; M3 needed three real ambiguities
resolved in conversation before drafting (Terminal's mechanism, the
M2-retrofit question, the M3/M5 Brave/VS Code overlap); M4 needed five
real questions answered (vision's real home, what gets memorized,
retention, a legibility indicator, retrofit-vs-net-new); M5 inherited
a real, still-unresolved question from M4's own scoping (the
LSP-code-intelligence split) that was never actually answered, carried
forward and still open today (see `docs/threat-model/v0.md`'s
"Milestone 5 additions").

M6's own ROADMAP objective — *"Email, calendar, research, job
assistance (research + drafting only, no auto-apply), Docker, ROS2"* —
has **more** buried ambiguity than any milestone before it, for a
structural reason worth naming plainly rather than working around:
this is not one coherent capability domain the way M3 (desktop
control), M4 (memory), and M5 (browser/coding) each were. It reads as
six loosely related, real-world integration targets bundled under one
milestone name. The questions below surface that bundling explicitly,
the same way M4's own Part 1, item 1 surfaced "is vision even part of
M4, or was it bundled for planning-table convenience" before assuming
the ROADMAP's own grouping was load-bearing.

## Part 1: real scope decisions the user will need to make

### 1. Is "M6" one milestone, or does this bundle need splitting the way M5's own scoping split browser/coding?

M3 and M5 each resolved a real internal-overlap question by
splitting explicitly (M3/M5's Brave/VS Code split; `m5-scoping-notes.md`'s
own considered-but-not-taken M5a/M5b browser-vs-coding split). M6's
own bundle is looser than either of those: email/calendar/research are
plausibly one coherent "personal productivity" surface; job assistance
is a distinct, higher-stakes real-world-consequence domain (see item 5
below); Docker and ROS2 share almost nothing in common with the first
four or with each other beyond "not yet covered by M0–M5."

- **Question**: does M6 stay one milestone covering all six items, or
  does it split (e.g., M6a: communications/productivity — email,
  calendar, research; M6b: job assistance; M6c: robotics/ROS2), the
  same way M5's own scoping considered and declined an M5a/M5b split
  but for a bundle that was actually more coherent than this one?

### 2. Docker is not a real M6 gap — it was already fully built in M3. Does this ROADMAP line just need correcting?

Checked directly against the real codebase, not assumed: M3 already
shipped four real, typed, capability-gated Docker capabilities
(`docker.list_containers`, `docker.run_container`, `docker.stop_container`,
`docker.build_image` — `kernel/capabilities.py`, `DockerAdapter`,
`docs/architecture/m3-desktop-control.md`'s own deliverable 8). Every
one of them is real, tested, and — per `docs/threat-model/v0.md`'s
"Milestone 3 additions" — `list_containers` has even been live-verified
against a real daemon. `docs/architecture/m6-integrations.md`'s own
placeholder text already says material from earlier planning
conversations "predate[s] this repo's real ADR numbering and are not
carried forward" — Docker's presence in the ROADMAP's own M6 one-liner
looks like exactly that kind of stale carry-forward, not a real,
remaining gap.

- **Question**: is there a real, *different* Docker scope M6 is
  actually meant to add (e.g., `docker-compose`-level orchestration,
  a plugin-host use of containers rather than a user-facing
  capability, something M3 didn't cover), or should "Docker" simply be
  dropped from M6's own objective as already satisfied?

### 3. Does ROS2 actually belong in this project's own scope at all?

The only two mentions of ROS2 anywhere in this repo's own docs are
`docs/ROADMAP.md`'s single "end goal" line and one *worked example*
task string in `m2-reasoning-layer.md` ("fix the failing test in my
ROS2 package") — used there purely as an illustrative coding-task
example, not evidence of any real robotics-integration intent. Nothing
in M0 through M5's own real design docs, ADRs, or scoping notes ever
mentions robotics, hardware control, or ROS2 again. This project's own
stated identity (`CLAUDE.md`'s opening line: "Privacy-first,
plugin-based agent kernel for Linux") is silent on robotics
specifically.

Real, live-checked context (not general knowledge alone): `rclpy`
(ROS 2's own Python client library) is actively maintained as of 2026,
so a real integration is technically feasible if wanted — but
feasibility isn't the open question here.

- **Question**: is ROS2 a real, deliberate target for this project (in
  which case: what would JARVIS controlling/monitoring a ROS2 system
  even mean product-wise — is there a real robot/simulated environment
  this is meant to work with?), or is this a leftover from an earlier,
  broader vision for the project that never got re-examined against
  what JARVIS actually became (a Linux desktop agent) by the time M6's
  own turn arrived? If the latter, dropping it (or deferring it to a
  genuinely separate, much-later milestone) may be the honest scope,
  the same way M4's own vision component nearly got split out for not
  being load-bearing to that milestone's real objective.

### 4. Email/calendar: vendor-neutral protocols (IMAP/CalDAV), or specific provider APIs?

This project has a real, hard architectural rule: no vendor names in
`domain`/`application`/`ports` (ADR-0021, enforced by
`tests/meta/test_source_invariants.py`'s repo-wide grep) — the exact
discipline M2's `ReasoningPort` already established for reasoning
providers ("family_a"/"family_b", never real vendor names). Email and
calendar access has a real, structurally clean vendor-neutral option
most personal email/calendar providers still support: IMAP (email) and
CalDAV (calendar), both open, long-standing protocols with mature
Python libraries (`imaplib` in the standard library; `caldav`, a real
RFC4791 client library — see Part 2). A specific-provider API (a
Gmail/Outlook-specific SDK) would be both a real vendor-naming problem
for this project's own architecture and a real, separate OAuth/
credential-flow integration per provider, not one shared mechanism.

- **Question**: does M6's email/calendar scope target IMAP/CalDAV
  specifically (vendor-neutral, works with self-hosted/Nextcloud/most
  real providers, fits this project's own architectural rule cleanly),
  or is there a real reason to need a specific provider's own API
  (e.g., features IMAP/CalDAV genuinely can't reach)? If the latter,
  how does that square with ADR-0021's own no-vendor-names rule —
  a real, new tension neither M2 nor any later milestone has had to
  resolve, since M2's own multi-provider reasoning abstraction never
  needed a provider-specific *port* shape, only provider-specific
  *adapters* behind one shared interface.

### 5. "Job assistance (research + drafting only, no auto-apply)" is a real, named product boundary — what does it concretely include?

The ROADMAP's own parenthetical is already a real, deliberate safety
boundary (no auto-apply — matches this project's own "destructive/
irreversible actions always require MANUAL_ONLY" principle in spirit,
even before any real capability is designed). But "research and
drafting" itself is not yet a scoped capability:

- Does this mean searching real job postings (would need a real
  search/listing source — job-board APIs are themselves vendor-specific
  the same way email providers are) and drafting a cover letter/resume
  edit (a real-document-editing capability, structurally similar to
  M5's own coding-loop "generate a candidate, let a human review it"
  shape, or closer to `CandidatePresentationPort`'s existing "human
  reviews before use" pattern from M2)?
- Is "no auto-apply" enforced as a real, structural boundary (no
  capability in this milestone's own scope ever submits anything to a
  real external system on the user's behalf), or as a policy-tier
  choice (a real `Effect`/`Tier` combination requiring `MANUAL_ONLY`
  confirmation for anything resembling submission)? The former is a
  stronger, more honest guarantee — matching how this project treats
  DESTRUCTIVE/IRREVERSIBLE actions as absolute rather than merely
  gated — but is a real scope decision, not obvious from the ROADMAP
  line alone.

### 6. "Research" — is this a new capability, or does it fold into M5's already-built browser automation?

M5 already shipped a real, live-verified `BrowserAutomationPort`
(open a page, screenshot, query the DOM). "Research" as a standalone
M6 item could mean: (a) nothing new at all — M6's "research" is just
*using* M5's existing browser automation for a different purpose, with
no new port/adapter needed; (b) a higher-level capability that
searches/reads multiple sources and synthesizes a result, which would
be new application-layer orchestration (structurally similar to M5's
own coding-loop wrapper: a real orchestration layer on top of
already-existing primitives) but no new *port*; or (c) something
requiring real new infrastructure this scoping pass hasn't identified
yet.

- **Question**: which of these is meant? This materially changes
  whether "research" is real, new M6 work at all, or a documentation/
  usage question resolved by pointing at M5's own existing capability.

## Part 2: research, not a recommendation baked into any decision

### Email/calendar: real, vendor-neutral protocol landscape (checked live this pass, not general knowledge alone)

- **IMAP** — Python's own standard library (`imaplib`) already
  provides `IMAP4`/`IMAP4_SSL` classes for secure connection, mailbox
  access, message search, and download. No new third-party dependency
  needed for the email-reading half at all.
- **CalDAV** — `caldav` (a real RFC4791 client library, PyPI
  `caldav`) is the real, current Python option: fetches/generates
  Event/Todo/Journal objects, includes async/await support via its own
  `caldav.aio` module. A second library,
  `CalDAVClientLibrary`, exists but is a lower-level HTTP/WebDAV/CalDAV
  protocol stack, not obviously preferable to `caldav`'s own
  higher-level API — a real evaluation question for whichever work
  package first builds this, not decided here.
- **Combining the two**: real, existing prior art
  (`mail2caldav`/`email-to-calendar` on PyPI/GitHub) already solves
  "parse a calendar invite out of an email and create/update the
  matching CalDAV event," confirming IMAP+CalDAV together cover a real,
  meaningful slice of "email and calendar" without any vendor-specific
  API.
- **Real, honest limitation, not smoothed over**: IMAP/CalDAV coverage
  depends on the user's own real provider actually exposing those
  protocols (most self-hosted, ProtonMail-with-bridge, iCloud, and many
  corporate/Exchange-via-CalDAV setups do; some consumer webmail
  providers restrict or deprecate raw IMAP access over time) — this is
  a real, live fact to re-confirm against whatever the user's own real
  accounts are, not assumed to cover 100% of real-world providers.

### ROS2: real, current status (checked live this pass)

`rclpy` (ROS 2's own canonical Python client library) is actively
maintained and released as of 2026 — real, ongoing development
activity (open issues/PRs, recent commits), bindings to the underlying
ROS 2 C++ libraries via `pybind11`. Real, live-checked, not assumed
stale — but this says nothing about whether integrating it is the
right scope for *this* project; that is Part 1, item 3's own question,
a product-fit question research cannot answer.

### Job-search sourcing: a real, live capability already available in this session's own tool surface, not this project's own code

Separately from anything `m6-integrations.md` would build, this
session's own environment already has a real job-search tool
(`mcp__claude_ai_Indeed__search_jobs`) available to Claude directly —
worth noting as context for Part 1, item 5's own "what does job
research concretely include" question, though whether *JARVIS itself*
(the deployed agent, not this planning session) should integrate
something equivalent, and how, is a real, separate design question,
not resolved by this tool merely existing in an unrelated context.

## Part 3: what this project's existing infrastructure already provides M6 for free, vs. what's genuinely net-new

**Already exists, real, reusable as-is:**

- `SecretPort` (ADR-0042) — IMAP/CalDAV credentials, and any job-board
  API key if item 5 needs one, are exactly the kind of credential this
  port already exists to resolve at point of use, never stored as a
  value.
- `AuthorizationOrchestrator`/the four-tier Policy Engine — every real
  M6 capability (send an email? draft a cover letter? query a
  calendar?) authorizes through the same, unmodified choke point every
  capability since M0 has.
- `AuditChain` — every real M6 capability invocation gets the same
  tamper-evident logging for free.
- `BrowserAutomationPort` (M5) — directly reusable for item 6's
  "research" question if the answer is (a) or (b) above; no new port
  needed for at least the browsing/reading half of research.
- `CandidatePresentationPort` (M2) — the existing "a human reviews a
  generated artifact before it's used" shape already fits "draft a
  cover letter, let the user review it before anything is sent" (item
  5) structurally, without new domain vocabulary.
- `TtsPort`/`ConsolePort` (M1/M5) — the "always legible" standing
  principle's own two existing mechanisms; M6 reuses them unmodified,
  the same way every milestone since M1 has, per `docs/ROADMAP.md`'s
  own standing text.
- `WorkspacePort` (ADR-0043) — if a drafted document (a cover letter,
  a resume edit) ever needs to become a real file for the user to
  open/edit further, this already exists.
- The Docker capabilities themselves (`docker.*`, M3) — see Part 1,
  item 2: likely means M6 does not need to build anything here at all.

**Genuinely net-new, no existing precedent to build on:**

- An IMAP/CalDAV port and adapter (nothing in this codebase reads or
  writes email/calendar data today).
- Whatever real capability shape "send an email" or "create a calendar
  event" takes, and its own real `Effect`/`Tier` classification —
  a first for this project the same way memory write (M4) and
  coding-agent write (M5) each were "first of their kind" write
  capabilities needing their own new `Effect`.
- A real job-listing source, if item 5's answer needs one beyond
  research/drafting on already-open pages via M5's `BrowserAutomationPort`.
- Whatever ROS2 integration would concretely mean, entirely contingent
  on Part 1, item 3's own answer — no design assumed here.
- A real "research synthesis" capability, if item 6's answer is (b) or
  (c) rather than (a).

## Resolved, 2026-09-01 — real answers, given directly by the user in conversation

Four of Part 1's six questions were put to the user directly and
answered — not inferred, not assumed, not a remotely-reasoned working
assumption the way M5's own two ADRs were. All four were the option
this pass itself had recommended; each is a real, deliberate choice
the user made, not a default that went unquestioned.

- **Item 2 (Docker)**: **Dropped.** Confirmed already fully satisfied
  by M3's own real `docker.*` capabilities — M6 does not build
  anything Docker-related. The ROADMAP's own M6 objective line is
  stale on this point and gets corrected, not carried forward.
- **Item 3 (ROS2)**: **Dropped.** No real robot/simulated environment
  or product reason was ever named for it; treated as a stale
  carry-forward from earlier planning material that predates this
  repo's real structure, the same category `m6-integrations.md`'s own
  placeholder text already warned about. Not part of M6a/M6b's own
  scope; not deferred to a later milestone either — genuinely dropped,
  unless a real reason to reopen this surfaces later.
- **Item 4 (email/calendar protocol)**: **IMAP/CalDAV only** —
  vendor-neutral, matching ADR-0021's own no-vendor-names rule with no
  new tension or exception needed. A specific provider's own API is
  out of scope unless a real, separate future decision reopens this.
- **Item 1 (split)**: **M6 splits.** Two real, separately-scoped
  sub-milestones replace the single M6 bundle: **M6a** (communications/
  productivity — email, calendar, research) and **M6b** (job
  assistance — research and drafting only, no auto-apply). Each gets
  its own real design doc, written only once its own turn genuinely
  arrives, per this project's own rolling-wave discipline — this
  document does not draft either one now.

**Two of Part 1's six questions remain genuinely open, deliberately not
resolved here** — deferred to whichever future pass begins M6a's or
M6b's own real design, not resolved prematurely just because the other
four were answered in the same conversation:

- **Item 5 (job-assistance boundary)** — M6b's own real design must
  still decide whether "no auto-apply" is a structural boundary (no
  capability in scope ever submits anything to a real external system)
  or a policy-tier gate (a real `Effect`/`Tier` requiring
  `MANUAL_ONLY`), and what "research and drafting" concretely includes.
- **Item 6 (research capability shape)** — M6a's own real design must
  still decide whether "research" needs any new port at all, or folds
  entirely into M5's already-built `BrowserAutomationPort`.

`docs/ROADMAP.md`'s own M6 row is updated to reflect the real M6a/M6b
split and the Docker/ROS2 drops (see that document); this document
itself is not further rewritten — the six original questions and the
real research behind them stay in place above, as the real record of
how these four answers were reached.
