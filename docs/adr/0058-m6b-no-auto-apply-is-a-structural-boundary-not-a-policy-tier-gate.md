# ADR-0058: M6b's "no auto-apply" is a structural boundary — no submission capability exists in scope, not a policy-tier gate

## Status

Accepted (2026-09-02, directly by the user, in conversation — see
below for the real acceptance record)

**Real, load-bearing difference from ADR-0057's own provenance,
stated plainly**: this ADR's core Decision was **not** worked out
remotely by this pass and merely reported to the user afterward. It
was put to the user directly, as `m6-scoping-notes.md`'s own item 5
explicitly named as a genuinely open, two-way question ("a structural
boundary... or... a policy-tier gate"), and the user answered it
directly, in this same conversation, before this document was
written:

> "No auto-apply" is a structural boundary, not a policy-tier gate.
> No capability in M6b's scope may ever submit a job application. The
> mechanism to do so does not exist in this codebase at all — not
> DENY-classified, not MANUAL_ONLY-gated, simply absent. Research and
> drafting only.

This ADR records that real decision, in the user's own words, plus
the real, mechanical consequences it implies for M6b's own package
layout and a real, structural meta-test design (see
`docs/architecture/m6b-job-assistance.md`).

**Acceptance record**: this document was surfaced in full to the user
immediately after being drafted, alongside `docs/architecture/m6b-job-assistance.md`
and the corresponding `m6-integrations.md`/`ROADMAP.md`/`CLAUDE.md`
updates. The user then explicitly instructed "Accept ADR-0058" in a
direct, separate turn — a real, deliberate acceptance of this specific
document's own final written text, not a rounding-up of the earlier
"no auto-apply is a structural boundary" answer alone. This closes the
"still left Proposed" gap this section originally stated at drafting
time, honestly, rather than silently editing that history away.
**Accepting this ADR does not itself authorize any M6b implementation
work** — it authorizes this document's own Decision and Consequences
as the real, binding constraint any future M6b work package (WP-82
onward) must satisfy; building `ports/draft_storage.py`,
`kernel/job_assistance.py`, or anything else under M6b's scope is
still separate, future work, not started by this acceptance alone.

## Date

2026-09-02

## Source

Direct user answer to `docs/architecture/m6-scoping-notes.md`'s own
item 5 ("is 'no auto-apply' enforced as a real, structural boundary...
or... a policy-tier gate"), given in this conversation, immediately
before this pass began drafting M6b's own real design.

## Context

Every destructive/irreversible/credential action this project has
ever gated before now has been gated *by tier* — `Tier.MANUAL_ONLY`
or `Tier.DENY`, evaluated by the same `AuthorizationOrchestrator`
choke point every other capability routes through
(`git.force_push`, `memory.forget`, `docker.build_image`). That
mechanism is real and well-proven, but it is not the same guarantee as
"the code to do this thing does not exist at all" — a `Tier.DENY`
floor is a real, enforced policy decision, checked at every real
invocation, but it presupposes a real `CapabilityDescriptor` exists to
evaluate a tier against in the first place. `m6-scoping-notes.md`'s
own item 5 named this exact distinction as the real, load-bearing
question for M6b, deliberately left open rather than assumed: does
"no auto-apply" mean a `CapabilityId` for submission exists, registered
at `Tier.DENY`/`Tier.MANUAL_ONLY` (a policy-tier gate — reversible by
a future ADR changing the tier), or does it mean no such
`CapabilityId`, port method, or adapter call exists anywhere in this
codebase's M6b scope at all (a structural boundary — reversible only
by writing genuinely new code, not by a policy change)?

This is exactly the class of decision `CLAUDE.md`'s own charter names
as one only the user can make directly, not remotely reasoned while
they are away — unlike ADR-0057's own classification-effect question
(itself a real, but comparatively mechanical, application of an
existing precedent), this is a first-principles product-safety
decision about how strong a guarantee "job assistance never applies to
jobs on your behalf" actually needs to be.

## Decision

**Structural boundary. No submission mechanism exists in M6b's scope
at all — not DENY-classified, not MANUAL_ONLY-gated, simply absent.**

Concretely, this means, and is enforced by, three real, mechanical
consequences (design detail in `docs/architecture/m6b-job-assistance.md`,
not repeated here):

1. **No `CapabilityId` for "submit"/"apply" is ever registered** in
   `kernel/capabilities.py`'s `build_default_registry()`, now or in
   any future M6b work package, without this ADR being superseded
   first by a new one that reopens this exact question.
2. **No port, adapter, or application-layer module under M6b's own
   package path** (`application/job_assistance/`, `kernel/job_assistance.py`,
   `ports/draft_storage.py`, `adapters/draft_storage.py`, and any
   future module sharing that path) **may call, import, or reference**
   any mechanism capable of submitting data to an external system on
   the user's behalf — no raw HTTP client, no browser-automation
   method beyond `BrowserAutomationPort`'s own existing, already-CONFIRM-tier
   `open_page`/`query_dom`/`capture_screenshot`/`close` (none of which
   can fill in or submit a form — the port itself has no such method
   today), and no future `BrowserAutomationPort` method resembling
   form interaction (`submit_form`, `click`, `fill`, `dispatch_form_submit`)
   may ever be called from this package, even if `BrowserAutomationPort`
   itself later grows one for an unrelated, legitimate reason.
3. **A real, structural meta-test** (design specified in
   `docs/architecture/m6b-job-assistance.md`'s own "Structural
   meta-test" section, mirroring `tests/meta/test_no_response_scraping.py`'s
   and `tests/meta/test_terminal_sandboxed_launch_only.py`'s own
   established AST-scan precedent) mechanically enforces (2) — checked
   by the gate suite on every change, the same way `test_speaker_id_isolation.py`
   mechanically enforces ADR-0034's own "audit/UX only" guarantee for
   speaker verification, not merely documented and trusted.

If a real, future product need ever requires actual submission (a
user explicitly asking JARVIS to submit an application on their
behalf), **that is new, undecided scope requiring its own new ADR**,
explicitly superseding this one — not a tier change to an
already-registered capability, because no such capability exists to
change the tier of. This is the real, deliberate asymmetry this
Decision creates: loosening this guarantee later is exactly as much
work as tightening a `Tier.MANUAL_ONLY` gate to `Tier.DENY` was never
meant to be — cheap by design, for the class of action that should
never be casually reopened.

## Consequences

**Makes easier**: no `Effect`/`Tier` combination has to be invented or
argued about for "submit" at all — the strongest possible privacy/safety
argument ("we don't have the DENY button because we don't have the
door") requires no ongoing policy-engine vigilance to stay true, unlike
a `Tier.DENY` floor, which is only as strong as `_EFFECT_TIER_FLOOR`'s
own configuration and every future capability author remembering not
to weaken it. `docs/threat-model/v0.md` gets a real, stronger claim
to make about M6b specifically, once implemented, than it can make
about any `Tier.DENY`-gated capability elsewhere in this codebase.

**Makes harder / real, deliberately accepted limitation**: if a
genuine future product need for auto-apply ever arises, it cannot be
delivered by a policy change alone (flipping a tier) — it requires
new code, a new ADR explicitly superseding this one, and the same
full design scrutiny any other genuinely new write-shaped capability
in this codebase has required (`Effect.MEMORY_WRITE`, ADR-0049;
`Effect.CODE_WRITE`, ADR-0056). This is the point of the Decision, not
an oversight — restated here so it is never read as one.

**Real, deliberately deferred question, not resolved here**: whether
`Classification.SECRET` content used as drafting input (e.g., a user
accidentally including credential-like text while asking JARVIS to
draft a cover letter) deserves the same unconditional-DENY,
never-persisted protection `Effect.MEMORY_WRITE` (ADR-0049) already
gives memory writes, versus the ordinary `Effect.WRITE_LOCAL`/`Tier.CONFIRM`
floor `m6b-job-assistance.md`'s own drafting capability design
currently uses. Named here explicitly as a real, open question for
whichever work package first implements `kernel/job_assistance.py`
(or a future ADR, if the answer turns out to need one) — not silently
decided in either direction by this ADR.

**Depends on nothing new being built yet**: like ADR-0057 before it,
this ADR describes a real decision no code yet implements —
`application/job_assistance/`, `ports/draft_storage.py`,
`adapters/draft_storage.py`, and `kernel/job_assistance.py` do not
exist in this codebase as of this ADR's own drafting. Implementation,
including the real meta-test this Decision requires, is real,
separate, future work (`m6b-job-assistance.md`'s own work-package
sketch, WP-82 onward), not bundled into this ADR's own scope.
