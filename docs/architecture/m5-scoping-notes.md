# M5 scoping notes — research and questions, not a design

**Status: prep material for a scoping conversation that has not happened
yet.** This is not `m5-browser-coding.md`'s real content, not an ADR,
not a design. Per this project's rolling-wave planning principle
(`docs/ROADMAP.md`) and CLAUDE.md's own hard rule ("never silently
change the architecture... propose a fix as a new ADR, and wait for
approval"), M5's real design starts only once the user has actually
answered the questions below — the same discipline that kept
`m4-memory-retrieval.md` a stub until M4 genuinely became the next
milestone and `m4-scoping-notes.md`'s own five questions got resolved
in conversation before a line of that document was drafted. Nothing
here authorizes writing `ports/`, `adapters/`, or `application/` code,
or an ADR, for M5. Written 2026-08-31 per the user's own explicit
request for scoping prep (immediately after WP-65 closed M4's four
named gaps and tagged v0.4.0), not a scoping decision.

`m5-browser-coding.md` itself remains untouched, gate-only, exactly as
it was before this document existed.

## Why this document exists: the pattern M2, M3, and M4 each needed

No prior milestone got a real design by just expanding its one-line
ROADMAP objective. Each needed a small number of genuine, user-decided
scope questions resolved first:

- **M2** needed the recovered pre-M0 design reconciled against what M0
  actually became — real gaps like "no keyring adapter exists despite
  ADR-0017 presupposing one" (ADR-0042) only surfaced once someone
  tried to implement against the recovered design and found it didn't
  match reality.
- **M3** needed three genuine ambiguities resolved *in conversation,
  before drafting*: Terminal's mechanism (portal+libei vs. AT-SPI2),
  M2-retrofit scope, and M3/M5 overlap (Brave/VS Code: shallow
  ordinary-control now, deep CDP/LSP automation later — the exact
  split this document's own Part 1, item 1 below has to take as its
  starting premise, not re-litigate).
- **M4** needed five questions answered before `m4-memory-retrieval.md`
  could be drafted for real (`m4-scoping-notes.md`), including one this
  document directly inherits: **M4's own Part 1, item 1 asked whether
  "Vision via ScreenCast/PipeWire" was really part of M4 at all, or
  bundled in for planning-table convenience** — it was moved to M5 in
  full (`m4-memory-retrieval.md`'s "Relationship to M5" section,
  resolved 2026-08-25), landing squarely in this document's own scope
  now. The same "planning-table convenience vs. real technical
  dependency" question M4's vision item raised applies again here, one
  level up: does M5's own ROADMAP row bundle two genuinely separate
  milestones (browser automation, coding capabilities) into one XL
  entry for the same reason?

M5's own ROADMAP objective — *"Browser via CDP. Coding capabilities
via LSP + git. Console UI. Vision via ScreenCast/PipeWire"* — bundles
at least four distinct capability areas in one line, more than any
prior milestone's objective did. The questions below are this pass's
attempt to surface the buried ambiguity now, checked against real code
wherever real code exists to check against (M3's ports, M2's reasoning
layer, M4's own retrieval port), not assumed from the objective's
prose alone.

## Part 1: real scope decisions the user will need to make

### 1. Is M5 genuinely one milestone, or does the ROADMAP row bundle two (or more) for planning-table convenience?

M4's own vision-scope question (above) already established that this
project's ROADMAP rows are not always one coherent technical unit —
sometimes they're a planning-table grouping that a real scoping pass
later splits. M5's row bundles:

- Browser automation via CDP (a real-time, live-page-driving problem —
  network protocol, JavaScript execution, DOM inspection).
- Coding capabilities via LSP + git (a static-analysis-plus-version-
  control problem — no live page, no browser process at all).
- A Console UI (a real, standing "always legible" principle
  dependency — `docs/ROADMAP.md`'s own standing-principle section
  names M5's Console UI as the mechanism that principle's on-screen
  half depends on, not an optional nice-to-have).
- Vision via ScreenCast/PipeWire (moved here from M4, per that
  milestone's own "Relationship to M5" resolution — see item 2 below
  for whether it's actually one thing with CDP's own browser-vision
  capability or a second, separate mechanism).

**Question**: are CDP-browser-automation and LSP-coding-capabilities
genuinely one technical unit (e.g., because a real coding agent needs
to drive a browser too — running a dev server and inspecting rendered
output, say), or are they two independently shippable milestones that
happen to share an entry gate (M3, M4) and got bundled into one XL
row the same way M4's vision component did? If the latter, does
splitting them (M5a: browser: CDP + vision; M5b: coding: LSP + git +
Console UI, or some other real split) produce a cleaner scope than one
XL milestone — mirroring M3's own "keep the milestone scoped to what
it's actually named for" reasoning about declining to let sandboxing
retrofit quietly expand M3 into M2 hardening?

### 2. Where does "Vision via ScreenCast/PipeWire" actually live, checked against both real code paths?

M4's own scoping pass named this question but explicitly left it for
M5's real scoping pass to answer (`m4-memory-retrieval.md`'s
"Relationship to M5" section: "not yet designed, since M5 itself has
not had its own real scoping pass"). Checked directly against the two
real, live mechanisms already in this codebase, not assumed:

- **`DesktopWindowPort.read_visible_text`** (`ports/desktop_window.py`,
  live-verified M3) is accessibility-tree **text** extraction via
  AT-SPI2 — a fundamentally different signal from a pixel-based
  screenshot or a DOM tree. It already has a real, known blind spot
  this session's own overnight audit re-confirmed: Chromium/Electron
  apps' AT-SPI2 trees are thin when the system accessibility bridge is
  off — exactly the case a screenshot-based fallback would help with,
  and exactly the gap "vision" as a ROADMAP word seems aimed at.
- **CDP's own screenshot/DOM-inspection capabilities** (real, native
  to the protocol — `Page.captureScreenshot`, the DOM domain) answer
  "what does this page show" for **browser content only**. Checked
  directly: nothing in `kernel/desktop.py`'s current Brave capability
  (`ports/brave.py`, `open_url` only) or anywhere else in this repo
  touches CDP at all yet — this would be entirely new adapter work
  regardless of which port it lands under.

Neither existing mechanism answers "what does an arbitrary desktop
app's screen currently show, as pixels" — that is a real, third,
distinct capability (`ScreenCast`/`PipeWire`, a different
`xdg-desktop-portal` interface from the `RemoteDesktop` portal
`SyntheticInputPort` already uses for Terminal's synthetic typing;
this document does not propose touching either portal, only naming
which one "vision" would need if built).

**Question**: does M5's vision component (a) reuse/extend
`DesktopWindowPort` with a new, structurally different method (pixel
capture, not AT-SPI2 text — a real port-shape question, not a
one-line addition), (b) stay scoped to CDP's own in-browser
screenshot/DOM capabilities only, treating "desktop vision" as
out-of-scope entirely, or (c) become its own new port
(`ScreenCapturePort` or similar, generic-named per ADR-0021's spirit)
independent of both? And, the narrower question Part 1 item 1 above
already raises at the milestone level: is vision needed for M5's
*browser/coding* objectives at all, or is it a fourth, separable
capability bundled in for the same planning-table reasons as before?

### 3. Does M5's coding agent reuse `application/reasoning/`'s escalation ladder unmodified, or does code generation need a genuinely different shape?

Checked directly against `application/reasoning/dispatcher.py` and
`ladder.py`, not assumed from the ROADMAP's "coding agent passes the
M2 escalation ladder end-to-end" exit-gate wording alone:

- `Dispatcher._attempt_rung` calls `ReasoningPort.generate(task,
  prior_attempts)` **once per provider per rung**, and each call
  returns exactly one `Candidate` — `Candidate.content` is a single
  `str` (a patch/diff or plain-text answer), produced in one shot.
  Feedback across attempts happens only *between* rungs, via
  `prior_attempts` — there is no notion inside one `generate()` call
  of an interactive, multi-turn session where a provider reads a file,
  proposes an edit, observes the result, and edits again before
  returning.
- `WorkspacePort.apply_patch` (`ports/workspace.py`) applies one
  unified-diff `str` to real files in one call — matching
  `Candidate.content`'s own single-`str` shape exactly. Nothing in
  this port or its real adapter (`LocalWorkspaceAdapter`, `git apply`-
  backed) supports an iterative, multi-step file-editing session
  either.
- `EscalationLadder.next_rung` (`ladder.py`) only ever climbs
  `DETERMINISTIC_FIX` → `SELF_REPAIR` → `SECOND_PROVIDER`, at most once
  each, per task — a real, structurally enforced ceiling of three
  attempts total, regardless of how many files or how much iteration a
  real coding task might need to converge.

**Question**: is "one candidate = one patch, escalate across at most
three rungs, `WorkspacePort.apply_patch` once per accepted candidate"
sufficient for a real autonomous coding agent's actual work (a single-
shot diff per attempt, validated, escalated on failure) — or does a
genuine coding agent need something this architecture doesn't have
yet: an iterative, multi-turn editing loop *inside* what today is one
`generate()` call (a provider reading/editing/re-reading files across
several exchanges before returning one final patch), which would be
new application-layer machinery, not a reuse of the existing ladder
as-is? If the latter, does that new machinery still produce one
`Candidate` at the end (compatible with the existing
`Attempt`/`Verdict`/arbiter machinery unchanged) or does it need new
domain vocabulary too?

### 4. What real authorization tier does an unscoped coding-agent file write get — checked against the actual Effect/Tier table and `WorkspacePort`'s real scope story?

Checked directly against `domain/capability.py`'s `_EFFECT_TIER_FLOOR`
table and `ports/workspace.py`/`adapters/workspace.py`, not assumed:

- The existing four-tier model has exactly one "ordinary local write"
  effect, `Effect.WRITE_LOCAL` (floors `Tier.CONFIRM`) — the same
  effect `git.create_branch`/`git.commit`/`git.push`/`memory.pin` all
  declare today. None of those existing `WRITE_LOCAL` capabilities
  writes to a file path the user didn't explicitly name or a path
  outside a narrow, already-understood scope (a new branch name, a
  commit of already-tracked files, a memory record by its own
  identifier).
- `fs.read_file` (`kernel/files.py`) is the one existing capability
  that touches arbitrary user-adjacent paths, and it enforces a real,
  explicit scope check (`_resolve_within_scope`/`allowed_root`,
  default `Path.home()`) *before* authorization ever runs — a
  mechanism `WorkspacePort.apply_patch` has no equivalent of today.
  Checked directly: `LocalWorkspaceAdapter.apply_patch` applies
  whatever paths the patch text itself names, with no allowlist, no
  scope boundary, nothing — confirmed as a real, already-accepted gap
  in `docs/threat-model/v0.md`'s "candidate execution is not
  sandboxed" section (WP-32–WP-40 never restricted which files a
  Candidate's patch may touch, and no sandboxing of the patched
  workspace's own command execution exists either).
- A real coding agent writing to files the user never named (any file
  a diff happens to touch, potentially outside the working tree
  entirely if the patch text says so) is a materially different risk
  shape from every existing `WRITE_LOCAL` capability's own narrow,
  already-bounded scope.

**Question**: does this need a new `Effect` (something narrower than
`DESTRUCTIVE` but stricter than the existing, unscoped `WRITE_LOCAL`
— e.g. an effect specifically meaning "write to a path not explicitly
named by the user"), or does the existing four-tier model already
cover it correctly as long as a real scope-check mechanism (mirroring
`fs.read_file`'s own `allowed_root` pattern) is layered onto
`WorkspacePort` itself, the same way `fs.read_file`'s real protection
is the scope check, not the tier? ADR-0004 is on record closing the
`Effect` taxonomy to ad hoc extension — a new `Effect` here would be a
real, explicit ADR decision for whichever work package first builds
this, not something this scoping pass decides.

### 5. Test-file protection: what real mechanism enforces this today (none, confirmed), and what would need to exist?

The ROADMAP's own M5 exit gate states "test files provably write-
protected" as a real, named requirement — checked directly against
existing precedent rather than assumed absent:

- `m2-reasoning-layer.md`'s own recovered scope-deliverables list
  (section 5, item 9) already names **"Test-file protection in the
  coding agent's resource scope"** — recovered material, not invented
  here, meaning this gap has a real name and a real place in this
  project's own design history already.
- `docs/threat-model/v0.md`'s "A real, explicitly-accepted gap:
  candidate execution is not sandboxed" section confirms directly:
  deliverable #9 was **explicitly deferred to M5** during M2's own
  implementation (WP-32 through WP-40), and no work package in that
  range restricts which files a Candidate's patch or a validator's
  command may touch. **There is no real mechanism anywhere in this
  codebase today that enforces test-file write-protection** — not a
  partial one, not a soft convention, genuinely none — confirmed by
  checking the actual `adapters/validation/` and `adapters/workspace.py`
  code, not assumed from the gap's mere existence in a doc.
- Real, existing building blocks that *could* be pressed into this
  role, without this document deciding which one should be (Part 3
  below maps these more fully): `SandboxPort.run`'s `bind_paths`
  parameter (real, kernel-enforced containment, but scoped to *process*
  isolation, not selective read-only file access within a shared
  bind); `WorkspacePort` itself, if it grew a real allow/deny path
  list before ever calling `apply_patch`; or a `git`-level check
  (`git diff --name-only` against a protected-paths list, checked
  before `git apply` runs).

**Question**: which real mechanism (or combination) actually closes
this gap for real — a `WorkspacePort`-level path allowlist/denylist, a
`SandboxPort`-level read-only bind for test directories specifically,
a git-hook-style pre-check, or something else — and does "provably"
in the exit gate's own wording imply a specific kind of evidence (a
real test that proves a write to a protected path is rejected,
mirroring this project's own "checked directly, not asserted" a
discipline) that should shape which mechanism is chosen?

## Part 2: research, not a recommendation baked into any decision

### The real Python CDP client landscape (checked live this pass, not general knowledge alone)

Real, current findings, not a recommendation:

- **`python-cdp`** (HMaker, `github.com/HMaker/python-cdp`) — a
  sans-IO client and types generator for CDP, currently tracking a
  real, recent CDP revision (r1179426, Chrome 117 at last check).
  Generates its own types/commands/events from the real protocol spec,
  the same "generated from the real spec, not hand-maintained" shape
  this project already trusts for its own tooling precedent
  (`import-linter` contracts, not a generated client, but the same
  "spec-driven, not vibes-driven" instinct). Sans-IO means it handles
  no actual network transport itself — a real, separate async/network
  layer would need pairing with it, matching this project's own
  "adapter owns the real I/O, the port stays a pure boundary" shape.
- **`PyCDP`** (HyperionGray, the original project this and other forks
  descend from) — also sans-IO, Python wrappers generated from the CDP
  spec. Real, older lineage; HMaker's fork appears to be the more
  actively maintained descendant as of this search, worth
  re-confirming at actual implementation time rather than trusted as
  still current by the time M5 starts for real.
- **`pychrome`** — a lower-level CDP transport handler, appears to be
  in an unmaintained/legacy state as of this search (listed among
  "alumni/old projects" in community trackers) — a real signal against
  choosing it fresh, not a final verdict.
- **Playwright's `connect_over_cdp()`** — a real, different shape
  entirely: Playwright is a full browser-automation framework (its own
  higher-level API, typically manages/bundles its own browser
  binaries) that can *also* attach to an existing browser instance
  over CDP. Real, explicitly documented tradeoff from Playwright's own
  docs: this connection mode is "significantly lower fidelity" than
  Playwright's native protocol connection, and using it against a
  browser Playwright didn't launch itself (this project's own case —
  M3 already launches/focuses a real, already-installed Brave via
  `brave-browser <url>`, not a Playwright-managed instance) can break
  Playwright functionality that assumes matching launch arguments.
  Real, separate tradeoff worth naming: Playwright itself is a much
  heavier dependency (its own browser-management layer, its own async
  runtime conventions) than a raw CDP client, the same
  heavier-vs-lighter shape M4's own vector-store research weighed
  (`sqlite-vec` vs. Qdrant/Milvus).
- **Raw `CDPSession`-style direct protocol speech** — some real,
  publicly-documented teams have moved *away* from Playwright/Puppeteer
  specifically to speak CDP directly, citing that the higher-level
  frameworks obscure real details about the underlying browser this
  project's own "checked against actual behavior, not assumed" instinct
  would likely also value.

Real, not-yet-answered technical question this list surfaces, mirroring
M4's own embedding-model question: does M5 attach to the same real,
already-installed Brave instance M3 already launches/focuses (this
project's own established pattern — one real, already-installed
browser, not a separately-managed automation-only browser process), or
does CDP automation need its own, separately-launched browser instance
with remote debugging enabled from the start? This is a real
architectural fork the library choice alone doesn't resolve.

### The real Python LSP client landscape (checked live this pass, not general knowledge alone)

Real, current findings — and a real, important distinction this
project's own "check real code before assuming" discipline caught:
**`pygls`, despite being the most commonly-known Python LSP package
name, is a language-*server* framework (for building one), not a
client** — the wrong direction entirely for "JARVIS talks to an
already-running language server for VS Code's own project," which is
what "coding capabilities via LSP" actually needs.

- **`multilspy`** (Microsoft Research, `github.com/microsoft/multilspy`)
  — a real, working LSP client library, originating from a NeurIPS 2023
  research paper (static-analysis-augmented code-LM decoding), with
  built-in support for several language servers (Python, Rust, Java,
  Go, JavaScript, Ruby, C#, Dart). Real, honestly-reported tradeoff
  from independent review found during this search: "a wonderful API
  but... hardcoded language servers and... not very maintained" — a
  real signal worth weighing against how actively this project would
  need to extend it, not a disqualifying one on its own.
- **`sansio-lsp-client`** (`PurpleMyst`/community forks) — a real,
  sans-IO client-side LSP implementation (the same "protocol logic
  separate from I/O" shape as the CDP options above). Real, current
  finding: no new PyPI release in the past 12 months as of this
  search, low recent PR/issue activity — a real, low-maintenance
  signal, not confirmed abandoned.
- **`lsp-client`** (`github.com/lsp-client/lsp-client` /
  `github.com/observerw/lsp-client`, PyPI `lsp-client`) — a newer,
  real project describing itself as "production-ready, async-first,"
  fully typed, with composable capability mixins and real container-
  aware workspace support (real, potentially relevant given this
  project's own `SandboxPort`/`bwrap` precedent for contained
  execution). Real caveat: found via this search as apparently new and
  not independently reviewed elsewhere yet — its real maturity needs
  re-confirming at actual implementation time, not trusted as
  established from one search pass.
- **`python-lsp-server`** and similar — real, but these are language
  *servers* (the same wrong-direction issue as `pygls`), not clients;
  named here only to rule them out explicitly, not as candidates.

### How ADR-0021's "no vendor names" discipline applies here, checked against its literal text and M3's own broader practice

ADR-0021's literal, enforced text forbids exactly five strings —
`"openai"`, `"anthropic"`, `"chatgpt"`, `"claude"`, `"gpt"` — in
`domain`/`application`/`ports`. Read literally, `"CDP"`, `"LSP"`,
`"Chrome"`, and `"Brave"` are not on that list at all: CDP and LSP are
open protocol standards (not vendors), and this project's own
`DesktopWindowPort` docstring already names AT-SPI2 (a real,
standardized accessibility protocol) directly at the port layer
without violating anything.

But `DesktopWindowPort`'s own docstring goes further than the literal
ADR-0021 grep list in practice: it explicitly states "No vendor names
appear in this module, per ADR-0021" while still naming Brave/VS Code
as real target applications *only in its own docstring's prose*, never
in the port's actual method/type names — the real, live pattern this
project has already established is broader than the ADR's own literal
enforcement mechanism, a spirit-over-letter discipline worth naming
explicitly rather than assuming the literal grep list is the only real
constraint.

**Question left genuinely open, not decided here**: should M5's real
port(s) be named after the open protocols themselves (e.g. a
`CdpPort`, matching how `AtSpi2`-style naming already appears in
`DesktopWindowPort`'s own docstring prose), or should they stay fully
generic at the port-name level too (`BrowserAutomationPort`,
`CodeIntelligencePort`), with "CDP"/"LSP" mentioned only in adapter-
layer docstrings and code — the same shallow/deep, port-level/adapter-
level split `m3-desktop-control.md`'s own "Relationship to M5" section
already draws for *application* naming ("Brave," "VS Code" never
appear in `DesktopWindowPort` itself, only in `kernel/desktop.py`'s
capability descriptions and `adapters/brave.py`'s own module)?

## Part 3: what this project's existing infrastructure already provides M5 for free, vs. what's genuinely net-new

A real technical map, useful regardless of which Part 1 answers the
user eventually gives — checked against the actual current codebase,
not assumed.

**Already exists, real, reusable as-is:**

- `AuthorizationOrchestrator`/the four-tier Policy Engine
  (ADR-0005/0006) — whatever new capabilities M5 registers, this is
  still the one real choke point, unchanged.
- `AuditChain`/hash-chained audit log (ADR-0026/0027) — every new M5
  capability invocation gets tamper-evident logging for free, the same
  way M3/M4's own new capabilities did.
- `git.status`/`git.create_branch`/`git.commit`/`git.push`/
  `git.force_push` (`kernel/desktop.py`, M3) — the "+ git" half of
  M5's "coding capabilities via LSP + git" objective already has real,
  typed, tested, policy-gated capabilities for the ordinary git
  operations a coding agent would need. Not extended or touched by
  this scoping pass; named here only as a real fact worth the user
  knowing before assuming git support is greenfield for M5.
- `WorkspacePort`/`LocalWorkspaceAdapter` (ADR-0043, M2) — the real
  patch-application mechanism (`git apply`-backed) already exists and
  is already exactly what a coding agent's `Candidate.content` (a
  diff) needs to become real files. Real, load-bearing caveat, not a
  clean reuse: see Part 1, item 4 — this port has no scope/allowlist
  mechanism today, a real gap a coding-agent use case would make load-
  bearing in a way M2's own validator-focused use case never did.
- `ReasoningPort`/`EscalationLadder`/`Dispatcher`/`Arbiter`
  (`application/reasoning/`, M2) — the real "propose, validate,
  escalate, select without merging" machinery already exists, fully
  tested (100%-branch-coverage gate, ADR-0041), and is exactly the
  shape the ROADMAP's own M5 exit gate ("coding agent passes the M2
  escalation ladder end-to-end on a real repo") expects reused, not
  rebuilt. See Part 1, item 3 for the real, open question of whether
  it's reused *unmodified* or needs a genuinely new capability layered
  on top for multi-turn editing.
- `SandboxPort`/`bwrap` (ADR-0044, M3) — real, kernel-enforced
  containment already exists and is exactly the mechanism
  `docs/threat-model/v0.md`'s own "candidate execution is not
  sandboxed" gap names as still missing for M2's validators. M5,
  building the coding agent that makes this gap load-bearing for the
  first time in a genuinely new way (an LLM-authored patch, executed
  against real test/build commands), is a real, plausible place this
  finally gets closed — not decided here, but the infrastructure to
  close it already exists and needs no new invention, only real
  wiring.
- `RetrievalPort` (ADR-0048, M4) — real, tested, already flagged in
  M4's own threat-model closeout as having "no real consumer... the
  first real consumer (plausibly an M5 coding-assistant capability) is
  what will actually test whether \[ADR-0050's provenance carry-
  forward\] discipline holds in practice." A coding agent recalling a
  memorized fact ("prefers tabs," a past architectural decision) as
  context for a new task is a real, plausible, already-anticipated M5
  consumer of M4's own infrastructure — not decided or built here, but
  the port and its carry-forward discipline are already real and
  waiting.
- `DesktopWindowPort` (ADR-0021, M3) — the real, live-verified
  *shallow* Brave/VS Code control (launch/focus/navigate-to-URL/open-
  file) already exists exactly as `m3-desktop-control.md`'s own
  "Relationship to M5" section describes: ordinary control now, deep
  CDP/LSP automation later. Not directly reusable *for* the deep
  automation itself (a structurally different mechanism, per Part 1
  item 2), but the existing shallow layer is real, live-verified
  infrastructure M5 does not need to rebuild for the cases it already
  covers.

**Genuinely net-new, no existing precedent to build on:**

- A real CDP client/adapter (Part 2's own landscape) and whatever new
  port shape hosts it (Part 2's own open naming question).
- A real LSP client/adapter (Part 2's own landscape) and its own port
  shape.
- The Console UI itself — no code exists anywhere in this repo today
  (`src/jarvis/ui/` contains only `ui/confirm/dialog.py`, M0's
  confirmation dialog, not a console/HUD view of any kind).
- Whatever the vision/ScreenCast component turns out to need (Part 1,
  item 2) — entirely contingent on that scope question's own answer,
  the same "contingent, not pre-built" position M4's own technical map
  already stated for this exact capability before it moved here.
- A real scope/allowlist mechanism for `WorkspacePort`, if Part 1 items
  4–5 land on that as the real fix — no existing port in this codebase
  restricts *which* files a write may touch the way `fs.read_file`
  restricts *which* files a read may touch; `WorkspacePort` would be
  the first write-side port to need this.
- A new `Effect`, if Part 1 item 4 decides the existing four-tier model
  doesn't already cover unscoped coding-agent writes correctly — a
  real ADR decision for whichever work package first needs it, not
  pre-invented here.
- Any real iterative, multi-turn editing machinery, if Part 1 item 3
  decides the existing single-candidate-per-rung shape is insufficient
  for real coding-agent work.
