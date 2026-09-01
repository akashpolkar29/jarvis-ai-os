# JARVIS — M5: Browser & Coding

**Status: real design, drafted 2026-08-31, not yet approved — and, unlike
every prior milestone's design doc, resting on answers that were never
confirmed by the user directly.** This document replaces the placeholder
that existed at this path before this pass, per this project's own
rolling-wave planning principle (see `docs/ROADMAP.md`) — written only
once M5 genuinely became the next milestone to scope
(`m5-scoping-notes.md`'s own five questions, drafted immediately
before this pass), mirroring exactly how `m4-memory-retrieval.md` was
written only once M4 became the next milestone with M3 code-complete,
not ahead of that point.

**A real, load-bearing difference from every prior milestone's own
design doc, stated plainly rather than smoothed over**: M0 through M4's
own scoping answers were each confirmed by the user directly, in
conversation, before the corresponding design document was drafted
(`m4-memory-retrieval.md`'s own header: "Every real decision below
traces back to one of five scoping questions the user answered
directly"). **The five answers this document is built on were instead
relayed to this pass as fixed working assumptions, reasoned remotely by
the user's own AI assistant, away from the machine — not confirmed by
the user in this conversation.** They are recorded verbatim below,
exactly as given, and this document does not invent new scope beyond
those five answers plus their necessary technical consequences — the
same discipline `m4-memory-retrieval.md` held itself to. But **this
document's own real provenance is more provisional than M4's was**, and
should be treated that way: **the user should review these five answers
specifically, directly, before anything below is Accepted** — this
design doc is not pre-approved the way `m4-memory-retrieval.md` was
once its own five answers were confirmed. Everywhere one of the two new
ADRs below (0055, 0056) says "Not yet reviewed by the user in
conversation," that is this same caveat, restated at the point it
matters most.

`m5-scoping-notes.md` itself remains untouched, real research and real
open questions, exactly as it was before this document existed — this
document resolves five of that document's questions (via the working
assumptions below) and leaves the rest genuinely open, named explicitly
at each site rather than silently answered by omission.

## The five working assumptions this document builds on

**Relayed as fixed answers for this drafting pass, not confirmed by the
user in conversation — see this document's own header.**
`docs/architecture/m5-scoping-notes.md` has the original open-question
framing each of these resolves:

1. **M5 stays one milestone**, sequenced internally: browser/CDP
   automation first (most self-contained — no dependency on the coding
   loop or reasoning layer), the coding-agent capability second
   (depends on the reasoning layer, M2), the Console UI third. This
   answers `m5-scoping-notes.md`'s Part 1, item 1 (whether the ROADMAP
   row bundles one technical unit or several) by keeping the bundle but
   fixing a real, internal dependency order — it does not itself decide
   whether a future revision might still split the milestone; that
   remains the user's own call.
2. **Vision**: CDP's native screenshot/DOM access fully covers
   browser-content vision — no new port needed for that (the browser-
   automation port from item 1 already carries it, per CDP's own
   `Page.captureScreenshot`/DOM domain, real and native to the
   protocol, confirmed in `m5-scoping-notes.md`'s own Part 1, item 2
   research). **Broader, desktop-wide vision (arbitrary non-browser
   apps) is a genuinely separate capability and is explicitly OUT of
   M5's scope**, deferred to a future milestone — nothing in M5's own
   ROADMAP objective requires it, and `DesktopWindowPort`'s own
   AT-SPI2-based text extraction (a structurally different mechanism,
   per that same research) is not extended or touched by this
   milestone either.
3. **Coding agent**: does not modify M2's `Dispatcher`/`EscalationLadder`
   core. A new, minimal coding-loop wrapper is built on top of it
   (`application/coding/`) — apply patch, run tests, feed failures
   back — as net-new orchestration, not a retrofit of M2. Full
   mechanism specified in ADR-0055.
4. **Authorization**: a new `Effect.CODE_WRITE`, floored at
   `Tier.CONFIRM` by default for ordinary file writes.
5. **Test-file protection**: any write path matching a real,
   configurable "protected test path" pattern gets an unconditional
   `Tier.DENY` floor, no confirmation override, mirroring
   ADR-0038/ADR-0049's precedent for "this class of write is never
   allowed, full stop." Full mechanism specified in ADR-0056 —
   including a real technical correction this drafting pass had to
   make to answer 4/5 as literally given (a single `Effect` cannot
   float at two different tiers; see ADR-0056's own Context section).

## Real gaps in the given assumptions, flagged rather than silently filled

Mirroring this project's own established discipline (WP-65's own
correction of a stale CLI-precedent claim, stated plainly rather than
quietly reinterpreted) — two real gaps the five assumptions above do
not close, named explicitly rather than invented over:

- **The assumptions say nothing about LSP.** `docs/ROADMAP.md`'s own M5
  objective names "coding capabilities via LSP + git" explicitly;
  working assumption 3 describes the coding-loop wrapper purely in
  terms of the existing `Dispatcher`/`WorkspacePort`/`ValidationPort`
  machinery (patch → test → feedback), which needs no LSP client at all
  to function as described. Whether "coding capabilities" also means
  real LSP-based code intelligence (symbol lookup, diagnostics,
  go-to-definition — the real capabilities `m5-scoping-notes.md`'s own
  Part 2 research surveyed a real client landscape for) is genuinely
  undecided by the given assumptions. This document does not invent an
  LSP design to fill that silence — see "Deferred, not forgotten"
  below.
- **The assumptions say nothing about the browser-automation port's own
  name**, or which real CDP client library to build against.
  `m5-scoping-notes.md`'s own Part 2 left this as a genuinely open
  question (protocol-named vs. fully generic per `DesktopWindowPort`'s
  own broader-than-ADR-0021's-literal-text practice); this document
  picks a working name below (`BrowserAutomationPort`) for concreteness
  in the package-layout sketch, but that specific name is this
  drafting pass's own placeholder, not a fixed decision the user
  confirmed — flagged the same way the vector-store/embedding choice
  was left open in `m4-memory-retrieval.md`.

## Objective

Browser automation via CDP; a coding-agent capability built on M2's
existing reasoning layer; a Console UI satisfying the "always legible"
standing principle's on-screen half. (Desktop-wide vision explicitly
excluded — see working assumption 2. LSP-based code intelligence
genuinely undecided — see "Real gaps" above, not designed by this
document.)

## Entry gate

M3, M4. Both code-complete: M3 (WP-43 through WP-56), not yet tagged
(a real, separate, already-flagged gap this document does not treat as
resolved); M4 (WP-57 through WP-64, plus the WP-65 gap-closure pass),
tagged `v0.4.0`.

## Exit gate

`docs/ROADMAP.md`'s own exit gate, taken directly, unchanged by this
pass: coding agent passes the M2 escalation ladder end-to-end on a real
repo; test files provably write-protected. **"Provably"** is satisfied,
per this document's own acceptance criteria below, by a real, executed
test proving a write to a protected path is rejected at `Tier.DENY`
under every confirmation state — the same "checked directly, not
asserted" standard `m5-scoping-notes.md`'s own Part 1, item 5 named
as the real open question behind this exact wording.

## Complexity

XL, 30–40 ideal-days per `docs/ROADMAP.md`'s own original estimate —
**not re-estimated here**, matching `m4-memory-retrieval.md`'s own
precedent of leaving re-estimation to the user's own review rather than
silently adjusting it in a drafting pass. Working assumption 2's real
scope reduction (desktop-wide vision deferred entirely) and the real
gaps left open above (LSP, browser-port naming/library) both plausibly
affect the real number in opposite directions — neither adjusted here.

## Known risks

`m5-browser-coding.md`'s own placeholder-era risk, unchanged and still
real: CDP automation against Brave will break on browser updates,
needing an ongoing maintenance budget, not just a build budget.
Additionally, real and specific to this drafting pass: **this entire
design rests on five remotely-reasoned answers** (this document's own
header) — a materially higher real risk of needing revision after the
user's own direct review than any prior milestone's design doc carried,
named here as a first-class risk, not just a header caveat. The
`Effect.CODE_WRITE`/`Effect.PROTECTED_PATH_WRITE` mechanism (ADR-0056)
is genuinely new, untested architecture — the first time this project's
tier system has ever needed two different floors for what a working
assumption described as one effect, resolved by adding a second one;
real correctness here (a protected-path write genuinely never reaches
a real workspace, under every code path) needs the same property-
testing rigor ADR-0038/ADR-0049's own required tests used, named as a
real acceptance criterion below, not assumed satisfied by writing the
check once.

## Relationship to M3

`m3-desktop-control.md`'s own "Relationship to M5" section already
drew the real, binding split this document inherits rather than
re-decides: M3 gets *ordinary* Brave/VS Code control (launch, focus,
navigate to a URL, open a file) via `BravePort`/`VscodeAppPort`
(real, live-verified, unchanged by this milestone); M5 gets the *deep*,
CDP/LSP-driven automation neither of those M3 ports touches at all.
This document's own browser-automation deliverable is exactly that
deep half, built as new, separate infrastructure alongside the
unmodified M3 ports, not a replacement for them — a coding/browser
capability that merely needs to *launch or focus* Brave still uses
M3's existing `BravePort`, not the new one.

`git.status`/`git.create_branch`/`git.commit`/`git.push`/
`git.force_push` (`kernel/desktop.py`, M3) already exist, real, typed,
tested, policy-gated — confirmed directly in `m5-scoping-notes.md`'s
own Part 3 technical map. The "+ git" half of this milestone's own
"coding capabilities via LSP + git" objective is **already
substantially built**; this document does not re-design or duplicate
it. Whether the coding-loop wrapper needs any *additional* git
capability beyond what already exists (a real `git diff`/`git stash`
read, say) is real, small, genuinely open implementation detail for
the work package that builds `application/coding/loop.py`, not decided
here.

## Relationship to M4

`RetrievalPort` (ADR-0048, M4) is real, tested, and — per
`docs/threat-model/v0.md`'s own M4 closeout — has "no real consumer...
the first real consumer (plausibly an M5 coding-assistant capability)
is what will actually test whether \[ADR-0050's provenance carry-
forward\] discipline holds in practice." This document does not build
that consumer (no work package below wires `RetrievalPort` into the
coding-loop wrapper) — a real, plausible, already-anticipated future
extension, not fixed scope for this milestone's own first pass.

## Non-goals

**No desktop-wide vision** — see working assumption 2. Only CDP's own
browser-content screenshot/DOM access is in scope; an arbitrary
non-browser app's on-screen content is explicitly out of scope,
deferred to a future milestone.

**No modification to M2's `Dispatcher`/`EscalationLadder`/`Arbiter`
core** — see working assumption 3 and ADR-0055. The coding-loop wrapper
is net-new orchestration, reusing that machinery completely unmodified.

**No general browser-automation platform, no headless-scraping
service.** This milestone builds JARVIS's own bounded capability to
drive the user's real, already-installed Brave browser on the user's
own behalf — not infrastructure sized or designed for unrelated,
third-party, or unattended-at-scale use, the same bounded-scope
discipline M3's own Claude/ChatGPT non-goal and M4's own "no general
retrieval-as-a-platform" non-goal already established for this project.

**No LSP-based code intelligence design in this document** — see "Real
gaps in the given assumptions" above. Named as a real, still-open
ROADMAP requirement, not designed or scoped further here.

**No sandboxing of the coding-loop wrapper's own validator execution
is *decided* by this document**, though it is named as a real,
plausible deliverable below (WP-73) — `SandboxPort` already exists
(ADR-0044, M3) and closing `docs/threat-model/v0.md`'s own
"candidate execution is not sandboxed" gap for the coding-agent's own
real, new use case is a genuinely different question from whether M2's
own already-shipped validators get retrofitted (a question M3's own
scoping explicitly declined to answer, tracked as separate follow-up)
— this document does not reopen that M3-era decision, only names the
real opportunity M5's own new use case presents.

## Scope: deliverables

Foundational-to-application-specific, matching M3/M4's own ordering
principle.

### Foundational

1. **`Effect.CODE_WRITE` / `Effect.PROTECTED_PATH_WRITE`**
   (`domain/capability.py`) plus `application/coding/classification.py`'s
   `code_write_effect_for` (ADR-0056) — the real authorization
   mechanism for every coding-agent file write, built and gate-verified
   against fakes before any real coding-loop wrapper exists, the same
   "safety-critical piece lands first" ordering M4's own WP-58 followed
   for `Effect.MEMORY_WRITE`.
2. **A new browser-automation port** (working name
   `BrowserAutomationPort` — see "Real gaps" above for why the real
   name is not fixed here), `Protocol`-only, no logic, mirroring every
   other port in this repo. Real method shape (open a page, capture a
   screenshot, inspect the DOM, evaluate JavaScript) sketched at
   objective level only in the package layout below — not fixed in
   detail, the same "port exists and is tested structurally before any
   real technology is chosen" ordering `DesktopWindowPort`/`SandboxPort`
   followed in M3 and `MemoryWritePort`/`RetrievalPort` followed in M4.

### Application-specific

3. **`application/coding/loop.py`** (or a small package) — the
   coding-loop wrapper (ADR-0055): apply patch (via the existing,
   unmodified `WorkspacePort`), run tests (via the existing, unmodified
   `ValidationPort`), feed failures back into a new `Dispatcher.run()`
   climb, bounded by a real, new, wrapper-level retry concept (exact
   shape not fixed by ADR-0055, real implementation work).
4. **A real CDP adapter** underneath the new browser-automation port —
   real client-library choice made by real evaluation against this
   project's own constraints (dependency weight, maintenance signal,
   sans-IO vs. bundled-transport shape), not decided in this document,
   mirroring the exit gate's own "benchmark/evaluate, don't just
   assume" discipline M4's own vector-store deliverable already
   established. `m5-scoping-notes.md`'s own Part 2 research
   (`python-cdp`, `PyCDP`, `pychrome`, Playwright's lower-fidelity
   `connect_over_cdp()`) is the real candidate list to evaluate against,
   not a pre-made choice.
5. **`kernel/browser.py`** and **`kernel/coding.py`** — composition
   roots, mirroring `kernel/memory.py`'s own `authorize_and_*` pattern:
   real capabilities registered in `build_default_registry()`,
   authorized through the unmodified `AuthorizationOrchestrator` choke
   point, no second authorization path.
6. **A minimal Console UI** — sequenced third (working assumption 1).
   Per this milestone's own placeholder-era recovered fragment (quoted
   verbatim in the pre-existing `m5-browser-coding.md`, now superseded
   by this document but the quote's own instruction still binding):
   *"Console UI views. Interface frozen; views deliberately not. You
   will know what you want after six months of using the HUD."* This
   document does not design specific views — only that a real, minimal
   mechanism must exist satisfying `docs/ROADMAP.md`'s own standing
   "always legible" principle's on-screen half (currently unmet: no
   code exists anywhere in `src/jarvis/ui/` today beyond M0's
   confirmation dialog, confirmed directly in `m5-scoping-notes.md`'s
   own Part 3).

## Acceptance criteria

1. `code_write_effect_for` has a real test proving a path matching the
   default `protected_patterns` (`test_*.py`, `*_test.py`, `tests/*` —
   ADR-0056) returns `Effect.PROTECTED_PATH_WRITE`, and every other
   path returns `Effect.CODE_WRITE`.
2. A real test, through the real `AuthorizationOrchestrator`, proves a
   `Effect.PROTECTED_PATH_WRITE`-classified write is denied
   unconditionally — including when `physical_confirmation_available=True`
   — matching ADR-0038/ADR-0049's own required property-test rigor,
   applied here for the third time.
3. A real, required meta-test (AST-based, mirroring
   `tests/meta/test_no_response_scraping.py`'s precedent, per ADR-0056's
   own Consequences section) proves no module outside the coding-loop
   wrapper's own defining module ever calls `WorkspacePort.apply_patch`
   for a coding-agent-authored patch.
4. A real, end-to-end test proves the coding-loop wrapper, given a task
   description and a real target repository with one real failing
   test, produces a passing `Attempt` after at least one real
   `Dispatcher.run()` retry — the exit gate's own "passes the M2
   escalation ladder end-to-end on a real repo," proven, not asserted.
5. A real test proves a patch touching both an ordinary file and a
   protected-path file is rejected as a whole (ADR-0056's own
   "all-or-nothing" requirement) — not partially applied.
6. The real browser-automation adapter, given a real URL, proves it can
   open the page (reusing or paralleling M3's own already-verified
   `brave-browser <url>` launch mechanism where applicable) and capture
   at least one real screenshot and one real DOM query — the real,
   minimal proof that working assumption 2's "CDP fully covers
   browser-content vision" claim actually holds for real, not merely
   asserted from the protocol's own documented capabilities.
7. A real, minimal Console UI mechanism exists and is exercised by at
   least one real coding-agent or browser-automation action, satisfying
   `docs/ROADMAP.md`'s own "always legible" standing principle's
   on-screen half for the first time in this codebase — checkable the
   same way M4's own "no indicator was built" criteria were checkable
   (by direct reading/verification, since no generic "Console UI
   exists" abstraction exists yet to test against more mechanically).
8. **(ADR-0056 amendment, 2026-09-01)** A real test proves whatever
   parses "which paths does this patch touch" from a real diff
   canonicalizes each path (resolving `.`/`..`/symlinks) before
   checking it against `protected_patterns` — an uncanonicalized path
   must not be able to fnmatch-compare against the wrong literal
   string and silently evade a real protected-path match. A second
   real test proves a file being *created* by a patch at a
   protected-looking path is classified identically to one being
   *modified* at that same path — creation is not a real loophole this
   ADR's own guarantee has. Both required for ADR-0055's own
   diff-parsing mechanism specifically, not decided here in
   implementation detail (see ADR-0056's own Amendment 2).

**Incomplete, stated plainly rather than padded, mirroring
`m4-memory-retrieval.md`'s own precedent**: this list does not cover
LSP-based code intelligence (genuinely undecided, see "Real gaps"
above), the real CDP client-library choice (real, separate evaluation
work), the coding-loop wrapper's own exact retry-budget shape
(ADR-0055's own deferred question), or the Console UI's own specific
views (deliberately, per the recovered fragment quoted above).

## Package/class layout proposal

```
domain/
    capability.py            - extended: Effect.CODE_WRITE,
                                Effect.PROTECTED_PATH_WRITE (ADR-0056)
    coding.py                - possible new, minimal domain vocabulary
                                for the wrapper's own retry-budget
                                concept (ADR-0055 leaves the exact shape
                                undecided -- may not need its own file
                                if a plain parameter suffices)
ports/
    browser_automation.py    - BrowserAutomationPort (working name --
                                see "Real gaps" above), Protocol-only:
                                open_page, capture_screenshot,
                                query_dom, evaluate_script (exact
                                method set real implementation work,
                                not fixed here)
adapters/
    browser_automation.py    - real CDP-backed adapter, client library
                                TBD by real evaluation (deliverable 4)
application/
    coding/
        loop.py               - the coding-loop wrapper (ADR-0055),
                                 wraps Dispatcher/EscalationLadder/
                                 WorkspacePort/ValidationPort unmodified
        classification.py     - code_write_effect_for() (ADR-0056),
                                 mirrors application/memory/classification.py
                                 exactly
kernel/
    capabilities.py           - extended: new CapabilityId constants
                                 for browser automation and coding-agent
                                 writes, registered in the same
                                 build_default_registry()
    browser.py                 - composition root, mirrors
                                  kernel/memory.py's authorize_and_*
                                  pattern
    coding.py                   - composition root, same pattern
ui/
    console/                    - a real, minimal Console UI mechanism
                                   (deliverable 6); no specific views
                                   designed here, per the recovered
                                   fragment's own "interface frozen,
                                   views deliberately not" instruction
```

No collision with M2/M3/M4: `ReasoningPort`, `WorkspacePort`,
`ValidationPort`, `SandboxPort`, `DesktopWindowPort`, `BravePort`,
`VscodeAppPort`, `MemoryWritePort`, `RetrievalPort` all stay exactly as
those milestones left them, none modified by this milestone — every one
of them is either reused unmodified (per the deliverables above) or
untouched entirely.

## Worked example

*"Fix the failing test in `tests/test_widget.py`."* Resolved: the
coding-loop wrapper receives the task, calls `Dispatcher.run()` once.
Say the winning `Attempt` at `SELF_REPAIR` produces a `Candidate` whose
patch touches both `src/widget.py` (a real fix) and, incorrectly,
`tests/test_widget.py` itself (the provider tried to "fix" the test by
editing it instead of the real code). Before `WorkspacePort.apply_patch`
is ever called, the wrapper classifies every touched path:
`code_write_effect_for("src/widget.py", ...)` returns
`Effect.CODE_WRITE` (`Tier.CONFIRM`); `code_write_effect_for("tests/test_widget.py",
...)` returns `Effect.PROTECTED_PATH_WRITE` (`Tier.DENY`, unconditional,
per ADR-0056). The whole candidate is rejected — not partially applied
— and the wrapper records this as a real `Attempt` with `Verdict.FAILED`
(a policy denial, not a validator failure), feeding that back into a
new `Dispatcher.run()` climb with the denial itself as part of the
next attempt's own framing (the real "feed failures back" mechanism
working assumption 3 names).

Second climb: a `Candidate` touching only `src/widget.py`. Classified
`Effect.CODE_WRITE` (`Tier.CONFIRM`) — granted (matching this project's
own ordinary local-write confirmation gate, unchanged). `WorkspacePort.apply_patch`
applies it for real; `PytestValidator` (existing, M2) runs the real
test suite; `Verdict.PASSED`. The wrapper's own retry loop stops (a
real `PASSED` verdict, the same "only a PASSED verdict halts
escalation" invariant `EscalationLadder` already enforces one level
down, mirrored at the wrapper level).

## Confirmation boundary

`ConfirmationPort`/`ManualConfirmationAdapter` and
`PhysicalConfirmationPort`/`Gtk4PhysicalConfirmationAdapter` are reused
completely unmodified — no new confirmation surface, matching M3/M4's
own precedent exactly. `Effect.PROTECTED_PATH_WRITE`'s `DENY` floor
(ADR-0056) is, per ADR-0038/ADR-0049's own already-established
reasoning, reused here without modification, an absolute ceiling: no
confirmation, physical or remote, overrides it — a protected test file
cannot be overwritten even with the user standing at the keyboard
actively trying to approve it.

## "Always legible"

A real, minimal Console UI mechanism (deliverable 6) exists for the
first time in this codebase specifically to satisfy this standing
principle's on-screen half — reusing M1's existing `TtsPort` for the
spoken half, unmodified, the same reuse every prior milestone's own
"always legible" discussion has already established. No specific view
is designed by this document, per the recovered fragment's own
instruction quoted above.

## Work package sketch (WP-67 through WP-75)

Objective-level only, matching the depth M3/M4's own deliverables were
scoped at before implementation started — no code, no premature
commitment to exact class/method names beyond what this document
already fixes above. Real dependency ordering (working assumption 1's
own browser-first, coding-second, Console-UI-third sequence), not a
fixed sequence the implementing session must follow rigidly if it
finds a genuine reason to reorder.

- **WP-67 — Browser-automation port shape.** `ports/browser_automation.py`
  (real name TBD, see "Real gaps"), contract tests only, against fakes
  — no real CDP client yet, the same ordering `DesktopWindowPort`/
  `SandboxPort` (M3) and `MemoryWritePort`/`RetrievalPort` (M4) both
  followed.
- **WP-68 — Real CDP client evaluation and adapter.** The one real
  spike-shaped work package, mirroring WP-43's (M3) and WP-61's (M4)
  own role: evaluate the real candidates `m5-scoping-notes.md` names
  against this project's own real constraints, build the real, chosen
  adapter, including deliverable 4's screenshot/DOM capabilities
  (working assumption 2's own vision coverage).
- **WP-69 — Browser-automation composition root.** `kernel/browser.py`,
  new `CapabilityId` constants, real capability registration through
  the unmodified `AuthorizationOrchestrator` — the first point real,
  end-to-end browser-automation calls exist as actual, invocable
  capabilities.
- **WP-70 — `Effect.CODE_WRITE`/`Effect.PROTECTED_PATH_WRITE` and the
  required single-path structural enforcement.** ADR-0056's full
  mechanism, including the required property test (a protected-path
  write never reaches a real workspace, at any confirmation state) and
  the required AST-based meta-test — the safety-critical piece lands
  first, before the coding-loop wrapper that will call it exists,
  matching M4's own WP-58 ordering.
- **WP-71 — The coding-loop wrapper.** `application/coding/loop.py`
  (ADR-0055): wraps the unmodified `Dispatcher`/`EscalationLadder`,
  real patch-apply-run-tests-feed-back mechanics, the real, new
  retry-budget concept (exact shape decided during this work package,
  not fixed by ADR-0055).
- **WP-72 — Coding-agent composition root.** `kernel/coding.py`, new
  `CapabilityId` constants for coding-agent writes, wiring
  `code_write_effect_for` (WP-70) and the coding-loop wrapper (WP-71)
  through the unmodified `AuthorizationOrchestrator`.
- **WP-73 — Real sandboxing for coding-agent validator execution.**
  Closes, for this milestone's own new use case specifically,
  `docs/threat-model/v0.md`'s own "candidate execution is not
  sandboxed" gap — reuses `SandboxPort`/`bwrap` (ADR-0044, M3)
  unmodified; does not retrofit M2's own already-shipped validators
  (that remains the separate, still-untaken follow-up M3's own scoping
  already declined to fold in).
- **WP-74 — Minimal Console UI.** A real, minimal mechanism satisfying
  the "always legible" standing principle's on-screen half — no
  specific views designed ahead of real use, per the recovered
  fragment's own instruction (deliverable 6).
- **WP-75 — M5 threat-model closeout.** `docs/threat-model/v0.md` gains
  a real "Milestone 5 additions" section; `CLAUDE.md`/`docs/ROADMAP.md`
  status updated to reflect what was actually built and verified —
  mirroring WP-64's own role for M4 exactly, including the same
  discipline of stating real, explicitly-accepted gaps plainly rather
  than rounding up to "done." **Must explicitly restate this document's
  own remote-reasoning provenance** in whatever it says about how M5's
  design was arrived at — not smoothed into "the user decided" language
  M4's own closeout could honestly use.

**Not included in this sketch, deliberately**: any work package for
LSP-based code intelligence (a real gap in the given assumptions, not
resolved by this document — see "Real gaps" above) and any work
package for desktop-wide vision (working assumption 2, explicitly out
of scope, deferred to a future milestone) — matching M4's own
"vision... belongs to a future M5 work package, not this milestone's
own numbering" precedent, applied here one milestone later for the
piece that stayed out even now.

## Deferred, not forgotten

- **LSP-based code intelligence** — genuinely undecided by the given
  assumptions (see "Real gaps" above). Not designed here; a real,
  separate scoping question the user should resolve directly before
  any work package attempts it.
- **The real browser-automation port's own name and its real CDP
  client-library choice** — both left open (see "Real gaps" above and
  deliverable 4); `BrowserAutomationPort` and no fixed library are this
  drafting pass's own working placeholders, not confirmed decisions.
- **The coding-loop wrapper's own exact retry-budget shape** — real,
  necessary design work for WP-71, not invented speculatively by
  ADR-0055.
- **Whether `RetrievalPort` (M4) ever becomes a real input to the
  coding-loop wrapper** — a real, plausible, already-anticipated future
  extension (see "Relationship to M4" above), not built by this
  milestone's own first pass.
- **Whether M2's own already-shipped validators ever get retrofitted
  onto `SandboxPort`** — a real, separate, still-untaken follow-up M3's
  own scoping already declined to fold into any single milestone; WP-73
  above closes the gap for the coding agent's own new use case only,
  not the older validators.

**A real, standing instruction for whoever reviews this document,
restated once more at the end rather than left only in the header**:
this design rests on five answers reasoned remotely, not confirmed by
the user directly, unlike every prior milestone's own design doc. Read
the two new ADRs (0055, 0056) and this document itself before accepting
anything — and treat that review as more necessary here than it was for
`m4-memory-retrieval.md`, not equally routine.
