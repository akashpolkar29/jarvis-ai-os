# JARVIS — M6b: Job Assistance (research and drafting only, no auto-apply)

**Status: real design, drafted 2026-09-02, not yet approved.** Unlike
M5's and M6a's own design docs, this one's single most load-bearing
decision — whether "no auto-apply" is a structural boundary or a
policy-tier gate — was **not** worked out remotely while the user was
away. It was put to them directly, as `m6-scoping-notes.md`'s own item
5 named it, and they answered it directly, in conversation, before
this document was written: **a structural boundary. No submission
mechanism exists in this codebase's M6b scope at all.** See
`docs/adr/0058-m6b-no-auto-apply-is-a-structural-boundary-not-a-policy-tier-gate.md`
for the full, real record of that decision, in the user's own words.
Everything *past* that point — the real port shapes, the reuse of
`UnverifiableTaskHandler`, the meta-test design — is this pass's own
reasoning, the same "remotely-reasoned working assumption" caveat
`m5-browser-coding.md`/`m6a-communications.md` each state for their
own designs. The user should review this document's own real
consequences before ADR-0058 is Accepted; this document is not
pre-approved.

`m6-scoping-notes.md` itself remains untouched — this document
resolves its item 5 (M6a's own document already resolved item 6,
research, for its own scope; this document checks separately below
whether the identical conclusion applies to M6b's own research need,
not assuming it does just because the words are the same).

## M6b's own scope, restated precisely

Job assistance: research (reading real job postings) and drafting (a
real cover letter/tailored resume text, produced as a real file for
the user to review and use themselves) — **and nothing else**. No
capability in this milestone's own scope ever submits, applies,
fills, or transmits anything to a real external system on the user's
behalf. See "The structural boundary" below for exactly how that is
enforced, not merely stated.

## The structural boundary

ADR-0058's own Decision, restated here at the point it constrains this
document's own design, not repeated in full: **no `CapabilityId` for
submission is ever registered; no port, adapter, or module under
M6b's own package path may call, import, or reference any mechanism
capable of submitting data to an external system.**

Concretely, for this document's own real design:

- `BrowserAutomationPort`'s real, existing interface
  (`ports/browser_automation.py`) has exactly four methods —
  `open_page`, `query_dom`, `capture_screenshot`, `close` — **none of
  which can fill in or submit a form**. This is not a restriction this
  document invents; it is already true of the port as M5 built it. If
  a job posting's own application flow is ever relevant to a real
  M6b capability, that capability's only real action is `browser.open_page`
  (already a real, registered, `Tier.CONFIRM` capability) — opening
  the page **for the user to complete themselves**. Nothing past that.
- This document's own real design introduces exactly one new write
  surface (`DraftStoragePort`, below) — saving drafted text to a real,
  new local file. It has one method, `save`, and cannot express
  submission by construction: it takes a filename hint and text
  content, returns a path, and has no network-reaching parameter or
  return value of any kind.
- No raw HTTP client (`requests`, `httpx`, `aiohttp`, `urllib`) is
  imported anywhere in this design, and the structural meta-test below
  mechanically forbids one from ever being imported under M6b's own
  package path in the future, not just today.

## Research: checked against M6a's own resolution, not assumed to match

M6a's own document (item 6) already answered "does research need a new
port" for its own scope: no, `BrowserAutomationPort`'s four existing
primitives (navigate, read DOM, screenshot, close) are sufficient, and
application-layer orchestration (if any) is real, separate,
undesigned future work.

Checked directly against M6b's own real need, not assumed identical
just because the word "research" is the same: reading a real job
posting is, mechanically, identical to reading any other real web
page — navigate to a URL, read its real content via `query_dom`,
optionally capture a screenshot to show the user, close. **The same
conclusion holds, for the same reason.** No new port. No new
`CapabilityId`. Every real research action authorizes through
`kernel/browser.py`'s already-Accepted `browser.open_page`/
`browser.screenshot`/`browser.inspect_dom`/`browser.close_page`,
completely unmodified — the identical, unmodified capabilities M6a's
own research already reuses.

**One real, honest difference from M6a's own research use, named
rather than smoothed over**: a job posting's own real content
(title, company, requirements, salary) is more naturally *structured*
than an email or calendar event's own read content. Whether a future
M6b work package needs a real, dedicated parsing/extraction step on
top of `query_dom`'s raw HTML — and if so, where that step lives — is
real, separate, undesigned work, the same category M6a's own "no
multi-page session"/"no caching" limitations already are: a real,
deferred question, not invented an answer for here. It changes nothing
about the structural boundary above: parsing already-fetched HTML
into structured fields is exactly as submission-incapable as reading
the raw HTML was.

## Drafting: `UnverifiableTaskHandler`, not `Dispatcher` — checked, not assumed

The working instruction for this pass named M2's reasoning layer
generically ("`Dispatcher`/`ReasoningPort`, if that fits"). Checked
directly against both of M2's own real, existing orchestration
primitives before choosing, not assumed:

- **`Dispatcher`** (`application/reasoning/dispatcher.py`, WP-37) is
  built for *verifiable* tasks: an `EscalationLadder` climbs rungs,
  a `ValidationPort` scores each candidate against a real pass/fail
  signal (a build, a test suite), and self-repair feeds a failure back
  as a new `Attempt`. **This does not fit drafting.** A cover letter
  has no build, no test suite, no pass/fail signal at all — there is
  nothing for a `ValidationPort` to check it against. Forcing this
  shape onto drafting would mean inventing a fake validator with
  nothing real to validate, exactly the kind of "designing ahead of
  a real need" this project's own rolling-wave discipline exists to
  avoid.
- **`UnverifiableTaskHandler`** (`application/reasoning/unverifiable.py`,
  deliverable #7, already built, ADR-0040) is built for exactly this
  shape: **no escalation, no ladder, no arbiter — every authorized
  provider is asked once, in parallel, and a human picks the winner**
  via the already-existing `CandidatePresentationPort`. This is a
  precise, structural match for "draft a cover letter": there is no
  automated way to judge which of several drafts is best, so a human
  does, exactly the regime this class already implements, unmodified.
  **This fits. No new orchestration primitive is designed here** —
  `UnverifiableTaskHandler.handle(task, context) -> Candidate` is
  called directly, exactly as it already exists.

Every real provider call `UnverifiableTaskHandler.handle()` makes
already routes through `ModelRouter.authorize_provider_call` — the
same `Effect.EGRESS_SENSITIVE`/`Effect.EGRESS_SECRET` classification
gate every other reasoning-provider call in this codebase already
uses (recall's own carry-forward consumer, the coding loop). **No new
`Effect`/`Tier` decision for the generation step itself** — this part
was already solved, generically, by M2, and needs no M6b-specific
reasoning at all.

### From `Candidate` to a real file: `WorkspacePort` does not fit either — checked, not assumed

`WorkspacePort.apply_patch(patch: str)` (ADR-0043) is `git apply`-backed
and expects `patch` to be real unified-diff text against an existing
repository — it exists to let a coding-agent candidate's own diff
modify real files it is validating against. A drafted cover letter's
`Candidate.content` is plain prose, not a diff, and there is no
existing repository to apply anything against. **Forcing this into a
"diff that creates a new file from `/dev/null`" shape would be a real,
awkward mismatch for what is fundamentally "write this text to a new
file," not a genuine reuse.** Named plainly rather than forced.

**A new, minimal port is the honest answer**: `DraftStoragePort`
(`ports/draft_storage.py`), one real method:

```python
@runtime_checkable
class DraftStoragePort(Protocol):
    def save(self, filename_hint: str, content: str) -> Path:
        """Persist `content` as a new, real file, named from `filename_hint`.

        Returns the real path the content was written to. Never
        overwrites an existing file with the same hint -- a real,
        adapter-level uniqueness guarantee (e.g. a timestamp or
        counter suffix), the same "never silently clobber" discipline
        `adapters/audit_storage.py`'s own append-only file handling
        already follows for a different real file.
        """
        ...
```

Mirrors `MemoryWritePort`'s own "one new port per genuinely new write
shape" precedent (ADR-0048) — a drafted document being saved to disk
is exactly as new a write shape as a memorized value or a code patch
each were when their own ports were introduced. `adapters/draft_storage.py`
(a real, local-filesystem-backed adapter) is real, separate,
implementation-time work, not designed further here — the same depth
`m6a-communications.md`'s own `ImapSmtpEmailAdapter`/`CalDavCalendarAdapter`
entries are named at before their own work packages build them.

### The drafting capability's own `Effect`/`Tier`

`job_assistance.draft` — a new, real, **static** capability (fixed
effect, not dynamic like `memory.write`'s own per-invocation
classification): `Effect.WRITE_LOCAL`, floor `Tier.CONFIRM` — the
same, already-Accepted, ordinary local-write floor `memory.pin`/
`memory.forget` (WRITE_LOCAL effect) already reuse rather than
inventing a new one. **No new `Effect`/`Tier` decision required**:
saving a drafted document to a new local file never leaves the
machine, the identical "does it leave the machine" test ADR-0049 and
ADR-0057 each already applied to their own write-shaped decisions,
answered the same way here.

**A real, deliberately deferred question, not silently resolved
either way — see ADR-0058's own "Consequences" section for the full
statement**: whether `Classification.SECRET` content used as drafting
input deserves the same unconditional-DENY, never-persisted
protection `Effect.MEMORY_WRITE` (ADR-0049) gives memory writes,
rather than the ordinary `WRITE_LOCAL`/`CONFIRM` floor this design
currently uses. A real, legitimate future safety question — flagged
for whichever work package or future ADR actually decides it, not
quietly picked in either direction by this document.

## Structural meta-test (design specified now, written at implementation time)

Mirrors `tests/meta/test_no_response_scraping.py`'s (identifier
ban-list, AST-based, docstring-blind) and
`tests/meta/test_terminal_sandboxed_launch_only.py`'s (structural
call-shape assertions, "predicate fires on a deliberate violation"
requirement) own established precedent exactly — reusing
`tests/meta/helpers.py`'s existing `iter_py_files`/
`referenced_code_identifiers`, no new scanning machinery.

**Scope**: every `.py` file under `src/jarvis/application/job_assistance/`,
plus `src/jarvis/kernel/job_assistance.py`, `src/jarvis/ports/draft_storage.py`,
and `src/jarvis/adapters/draft_storage.py` — the complete, real set of
modules M6b's own package layout (below) introduces.

**Assertion 1 — no raw HTTP-client identifier anywhere in real code**:
`referenced_code_identifiers()` applied to every file in scope must
never contain any of a fixed, named ban-list: `requests`, `httpx`,
`aiohttp`, `urlopen`, `urlretrieve`, `Request` (the `urllib.request`
class), `post` (catches `requests.post`/`httpx.post`/`session.post`-shaped
attribute calls, the same way `test_no_response_scraping.py` bans the
bare attribute name `read_visible_text`). **A real, honest, named
limitation of this check, stated now rather than discovered later**:
`post` is a common short word; a hypothetical, entirely unrelated
future method or variable literally named `post` inside this package
(e.g. a blog-post-shaped domain concept, however unlikely for this
milestone) would false-positive. Accepted deliberately, matching this
project's own "some false positives are the acceptable cost of a real,
mechanical guarantee" precedent (`test_source_invariants.py`'s own
vendor-name grep has the identical, already-accepted trade-off) —
narrower ever needed later, not looser.

**Assertion 2 — no unlisted `BrowserAutomationPort`-shaped method
call**: any call whose attribute name matches a fixed, named set of
hypothetical future form-interaction methods — `submit_form`, `click`,
`fill`, `fill_form`, `dispatch_form_submit`, `press_key`, `type_text`
— must never appear anywhere in scope, **even though none of these
methods exist on `BrowserAutomationPort` today.** This is the same
"named future bypass risk, flagged before it can be built past
unnoticed" shape ADR-0057's own finding 4 already used for a
hypothetical future `CalendarPort.update_event` — if `BrowserAutomationPort`
ever legitimately grows one of these methods for an unrelated reason,
this package must still never call it without this ADR being
reopened first.

**Assertion 3 — no function/method signature under this scope accepts
a submission-shaped parameter name**: an AST scan of every
`FunctionDef`/`AsyncFunctionDef` argument name in scope must never
match `submit`, `apply_to`, `application_payload`, or
`credentials_for_submission` (case-insensitive substring match on the
parameter name) — catching a capability that structurally *could*
submit even if it never calls anything named `post`/`submit_form`
today (e.g. a future signature like `def handle_application(self,
answers: dict) -> None`, which this check would flag for review even
before its own body is written).

**Per this project's own Meta-tests convention (`CLAUDE.md`)**: each
of the three assertions above must ship with its own "the predicate
actually fires on a deliberate violation" test, proving the check is
real and not merely passing on a currently-clean tree — the identical
requirement `test_no_response_scraping.py`/`test_terminal_sandboxed_launch_only.py`
already satisfy for their own checks. This is a **design specification
for a real test the M6b implementation work package must write**, not
a claim that the test exists yet — no `application/job_assistance/`,
`ports/draft_storage.py`, or `adapters/draft_storage.py` exist in this
codebase as of this document, so there is nothing yet for the real
test to scan.

## Package/class layout

```
ports/
    draft_storage.py           - DraftStoragePort (NEW)
adapters/
    draft_storage.py            - LocalDraftStorageAdapter (NEW, real
                                   local-filesystem write, uniqueness-
                                   safe file naming)
application/
    job_assistance/
        drafting.py              - orchestration: authorize -> build
                                    the real UnverifiableTaskHandler
                                    (providers/router/presentation,
                                    all pre-existing M2 types) ->
                                    .handle() -> DraftStoragePort.save()
                                    only if the outer job_assistance.draft
                                    decision is granted -- mirrors
                                    kernel/coding.py's own
                                    "orchestrator.authorize_by_id()
                                    first, the real side effect only
                                    ever inside if decision.granted"
                                    shape exactly.
kernel/
    capabilities.py               - extended: JOB_ASSISTANCE_DRAFT_CAPABILITY_ID
                                     (static, Effect.WRITE_LOCAL)
                                     registered in build_default_registry()
    job_assistance.py              - composition root:
                                      authorize_and_draft_document(),
                                      mirroring kernel/coding.py's/
                                      kernel/memory.py's own registry/
                                      storage/confirmation/orchestrator
                                      wiring exactly.
```

**No new module for research** — mirroring M6a's own item 6
resolution exactly: whatever real application-layer orchestration a
future work package builds on top of `browser.open_page`/`query_dom`
for job-posting research is real, separate, undesigned implementation
work, not designed in this document. No `application/job_assistance/research.py`
is speculatively created here.

**No new domain type.** `domain/evidence.py`'s existing `Candidate`
(`author`, `content`) already carries a drafted document's own real
shape — the identical type `UnverifiableTaskHandler.handle()` already
returns, unmodified. No `domain/job_assistance.py` is introduced.

## Confirmation boundary / "always legible"

`ConfirmationPort`/`ManualConfirmationAdapter`,
`PhysicalConfirmationPort`/`Gtk4PhysicalConfirmationAdapter`, and
`CandidatePresentationPort`/its own existing adapter are reused
completely unmodified — no new confirmation or presentation surface.
`TtsPort`/`ConsolePort` (M1/M5) are the real mechanisms a future
`job_assistance.draft` work package should wire a granted draft
through, satisfying `docs/ROADMAP.md`'s own "always legible" standing
principle the same way `browser.open_page` already does — not
designed further here, matching M6a's own identical deferral.

## Acceptance criteria

1. A real test proves `JOB_ASSISTANCE_DRAFT_CAPABILITY_ID` is
   registered with `Effect.WRITE_LOCAL`, floor `Tier.CONFIRM`.
2. A real test, through the real `AuthorizationOrchestrator`, proves a
   denied `job_assistance.draft` invocation never calls
   `UnverifiableTaskHandler.handle()` at all — mirroring
   `test_coding_kernel.py`'s own `provider.call_count == 0` proof for
   `coding.run_task`'s identical "denied means never even tried" shape.
3. A real test proves a granted `job_assistance.draft` invocation
   calls every authorized provider in `UnverifiableTaskHandler`'s own
   real, parallel-generation shape, and that `DraftStoragePort.save()`
   is called exactly once, with the human-selected `Candidate`'s own
   content — never an unselected candidate's.
4. A real test proves `DraftStoragePort.save()` never overwrites an
   existing file for a repeated `filename_hint` — the real uniqueness
   guarantee this port's own docstring requires.
5. **The three structural meta-test assertions specified above**, each
   with its own real "fires on a deliberate violation" companion test
   — the real, mechanical proof this ADR's own structural-boundary
   Decision holds, not merely documented.
6. A real test proves `browser.open_page` is the only real action a
   job-posting-research flow takes when a job's own application page
   is relevant — no further capability is ever invoked past opening
   the page.

**Incomplete, stated plainly rather than padded**: this list does not
cover the real job-posting-source evaluation (which real, vendor-neutral
listing sources are usable at all — a real, separate research question
this document does not resolve, matching `m6-scoping-notes.md`'s own
"job-search sourcing" note that this session's own environment has a
job-search tool unrelated to what JARVIS itself would use), the real
console-line wiring for `job_assistance.draft` (M6a's own identical
"no specific views" deferral), or the real drafted-content-quality
question research/prompting design would need (a real, separate,
undesigned concern this document treats as out of scope, the same way
`m6a-communications.md` never designed email body content quality
either).

## Work-package sketch (objective-level only)

Continuing the same shared, project-wide, sequential work-package
numbering `m6a-communications.md`'s own sketch already claimed through
WP-81 (real WP numbers are assigned once a real design names them,
regardless of which sub-milestone actually implements first — M6a
remains blocked on the user's own review of ADR-0057, M6b on this
document's own review):

- **WP-82 — `DraftStoragePort` shape.** Contract tests only, against
  fakes — no real filesystem adapter yet, matching every other port's
  own established ordering.
- **WP-83 — Real `LocalDraftStorageAdapter`.** The real, local-filesystem
  write, including its own uniqueness-guarantee behavior (acceptance
  criterion 4).
- **WP-84 — `kernel/job_assistance.py` composition root + the
  structural meta-test.** Landing together, deliberately: the real
  capability and the real, mechanical proof of its own structural
  boundary are not sequenced apart — mirroring WP-70's own
  "safety-critical piece lands first, proven, not assumed" ordering,
  except here the safety-critical piece *is* the absence of a
  mechanism, proved by a test that a submission path was never added,
  not by a tier check that one is gated.
- **WP-85 — Real job-posting research usage** (application-layer
  orchestration on top of unmodified `browser.*` capabilities, if any
  real orchestration turns out to be needed beyond direct use — see
  "Research" above).
- **WP-86 — M6b threat-model closeout.** Mirroring WP-64/WP-75/WP-81's
  own role exactly.
