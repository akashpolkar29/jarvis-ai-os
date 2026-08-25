# JARVIS — M4: Memory & Retrieval

**Status: real design, drafted 2026-08-25, not yet approved.** This
document replaces the placeholder that existed at this path before
this pass, per this project's own rolling-wave planning principle (see
`docs/ROADMAP.md`) -- written only once M4 genuinely became the next
milestone to scope, mirroring exactly how `m3-desktop-control.md`
itself was written only once M3 became the next milestone with M2
complete and tagged, not ahead of that point. Every real decision
below traces back to one of five scoping questions the user answered
directly, cited inline at each site -- this document does not invent
new scope beyond those five answers plus their necessary technical
consequences. **Not yet implemented, not yet Accepted**: the ADRs this
document depends on (ADR-0048 through ADR-0052) are drafted alongside
it, Proposed, not Accepted -- per this project's own ADR process, only
the user marks an ADR Accepted, and no work package below may start
until that happens.

## The five scoping decisions this document builds on

Answered directly by the user, 2026-08-25 (`docs/architecture/m4-scoping-notes.md`
has the original open-question framing each of these resolves):

1. **Vision is out of scope for M4.** "Vision via ScreenCast/PipeWire"
   moves to M5, decided together with CDP-based in-browser vision, as
   one coherent capability rather than split across two milestones.
   This document does not design, and no work package under this
   milestone may build, anything ScreenCast/PipeWire-shaped.
2. **SECRET-classified values are never memorized.** Hard DENY at
   write time, not a CONFIRM prompt -- memory is treated as a real
   persistence/exfiltration surface (a value written once can resurface
   in an unrelated context arbitrarily later), a materially different
   risk than a one-time live SECRET fetch under the existing gate.
   Memory *reads* inherit the tier of what they retrieve: a
   CONFIRM-tier memory re-triggers CONFIRM on recall, not a free pass
   for having come from storage instead of a live source.
3. **Retention: default time-boxed expiry (90 days), with an explicit
   manual "pin" action** for anything the user wants kept longer. Not
   unbounded append-only (indefinite retention is its own privacy
   risk, independent of decision 2) and not silent LRU eviction
   (unpredictable, erodes trust in what the assistant "remembers").
4. **No real-time indicator for memory recall.** ADR-0047's indicator
   exists because a synthetic keystroke is an irreversible,
   externally-visible action the instant it fires; a memory recall
   changes what JARVIS *says*, which the user notices and corrects in
   conversation the same way they'd correct someone who misremembered
   something -- real-time indicators stay reserved for actions with
   real-world side effects, not reads.
5. **Retrofit vs. net-new, confirmed**: `Tainted[T]`, `AuditChain`,
   `SecretPort`, and `WorkspacePort` are reusable as-is. Genuinely new:
   the vector store, the embedding pipeline, the retrieval-query port,
   and deletion mechanics (to implement decision 3's TTL/pinning and
   to enforce decision 2's DENY at write time, not merely at read
   time).

## A real technical gap decision 2 surfaced, resolved here

Checked directly against real code before drafting anything on top of
decision 2, not assumed: `domain/capability.py`'s `CapabilityInvocation.effective_tier`
escalates by exactly one step when `provenance.is_tainted` -- and
`Provenance.is_tainted` (`domain/provenance.py`) is defined purely in
terms of `Trust.UNTRUSTED_EXTERNAL`, with no reference to
`Classification` at all. There is no existing generic mechanism by
which a SECRET-classified argument automatically escalates a
capability's tier -- not to DENY, not at all. ADR-0038's real SECRET/DENY
enforcement for M2's cloud egress does not work through that
mechanism either: `application/reasoning/classification.py`'s real
`egress_effect_for(classification)` is bespoke, per-invocation glue
code M2's router calls at dispatch time to attach `Effect.EGRESS_SECRET`
to a specific call before the Policy Engine ever evaluates it -- not
something "memory write" inherits for free by resembling that pattern.

**Decision, made in this drafting pass, following the existing
precedent rather than inventing a new one**: M4 builds its own,
directly analogous `application/memory/classification.py` with a real
`memory_effect_for(classification: Classification) -> Effect`
function, called at memory-write dispatch time, mirroring
`egress_effect_for`'s exact shape. A **new** effect,
`Effect.MEMORY_WRITE`, is added rather than reusing `Effect.EGRESS_SECRET`
-- `EGRESS_SECRET`'s own name and reasoning (ADR-0038) are specifically
about a value *leaving this machine* to a cloud provider; a memory
write is local, and reusing that name for it would be a real,
misleading taxonomy overload, not a small implementation shortcut.
Full mechanism specified in ADR-0049.

## Objective

Memory and hybrid retrieval, with a retrieval eval set the exit gate
measures against. (Not vision -- see decision 1 and "Relationship to
M5" below; this is a real, deliberate narrowing of `docs/ROADMAP.md`'s
original one-line M4 objective, not an oversight.)

## Entry gate

M2, M3. Both complete: M2 tagged `v0.3.0`; M3 code-complete
(WP-43 through WP-56), not yet tagged (a real, separate, already-flagged
gap -- tagging M3 is the user's own action, not a blocker this
document treats as resolved by fiat).

## Exit gate

Retrieval measured against a fixed eval set; brute-force-vs-ANN
decision made by benchmark, not preference -- `docs/ROADMAP.md`'s own
exit gate for this milestone, taken directly, unchanged by this pass.

## Complexity

XL, 25-35 ideal-days per `docs/ROADMAP.md`'s own original estimate --
**not re-estimated here**. Decision 1 (vision moved to M5) is a real
scope reduction from what that estimate originally priced in; whether
that changes the real number is the user's own call when reviewing
this document, not something silently adjusted in a drafting pass.

## Known risks

Retrieval quality is empirical and may need several iterations
(`docs/ROADMAP.md`'s own framing, unchanged). Additionally, real and
specific to this milestone's own scope: the classification-propagation
mechanism above (`memory_effect_for`, ADR-0049) is new, untested
architecture -- unlike M3's ports, which mostly composed already-proven
patterns, this is the first time a *write-time* classification check
gates persistence itself, not just a one-shot egress decision. Real
correctness here (a SECRET value genuinely never reaches the vector
store, under every code path, not just the obvious one) needs the same
property-testing rigor ADR-0038's own required test used ("a
SECRET-classified task never reaches a cloud provider at any rung,
under any circumstance") -- named as a real acceptance criterion below,
not assumed satisfied by writing the check once.

## Relationship to M3

`DesktopWindowPort.read_visible_text` (M3, AT-SPI2-backed) already
answers a narrow slice of "what's on screen" for apps with usable
AT-SPI2 support -- this document does not duplicate or extend that
mechanism. Memory's own retrieval concern (search over *past*,
already-captured content) is a different problem from "read *current*
screen content," and this milestone does not blur the two.

## Relationship to M5

**Vision via ScreenCast/PipeWire moves to M5 in full**, per decision 1
-- bundled with M5's own CDP-based in-browser vision as one coherent
capability, not split across two milestones with two different
mechanisms answering overlapping "what does the screen/page show"
questions. `docs/ROADMAP.md`'s M5 row does not currently mention vision
at all (`"Browser via CDP. Coding capabilities via LSP + git. Console
UI."`) -- **a real, direct consequence of decision 1 this document
surfaces but does not act on**: `docs/ROADMAP.md`'s M4 and M5 rows both
need a real edit reflecting this move (M4's row still says "Vision via
ScreenCast/PipeWire" today). Flagged here for the user's own review
alongside this document, not silently changed as a side effect of
drafting M4's own design -- that edit touches M5's row too, which is
outside this pass's own scope of "M4's row only."

## Non-goals

**No general retrieval-as-a-platform, no RAG service.** This milestone
builds JARVIS's own bounded, personal-assistant-scale memory -- not a
general-purpose vector-search feature other capabilities query for
unrelated purposes, and not infrastructure sized or designed for
multi-tenant or third-party use. Scope stays "what did the user tell
JARVIS, or what did JARVIS observe on the user's behalf, that's worth
recalling later" -- the same bounded-scope discipline M3's own
Claude/ChatGPT non-goal already established for this project (declining
to let a real capability quietly become a different, larger kind of
system).

**No vision/screen-capture component** -- see decision 1 and
"Relationship to M5" above.

**SECRET-classified content is never memorized, full stop** -- see
decision 2. No future work package under this milestone may add an
override, exception path, or "trusted context" carve-out to this rule
without a fresh, explicit ADR revisiting it -- the same
no-exception-path discipline ADR-0014/ADR-0038 already established for
cloud egress applies here by the same reasoning, not a weaker version
of it because the destination is local disk instead of a cloud
provider.

## Scope: deliverables

Six deliverables, foundational-to-application-specific, matching M3's
own ordering principle:

### Foundational

1. **Domain types** (`domain/memory.py`) -- kept minimal, reusing
   `Tainted[T]`/`Provenance`/`Classification` as-is (decision 5): a
   `MemoryRecord` (the stored, provenance-tagged unit) and a
   `RetrievalQuery`/`RetrievalResult` pair. No new provenance
   vocabulary -- classification/trust stay exactly what `domain/provenance.py`
   already defines.
2. **`MemoryWritePort`** -- one real method, write a `Tainted[T]`
   value to memory. Internally resolves `memory_effect_for` (ADR-0049)
   before the write is authorized, so a SECRET-classified value is
   denied by the real Policy Engine choke point, not by a check
   the write path could route around.
3. **`RetrievalPort`** -- one real method, given a query, return
   ranked `MemoryRecord`s. Per decision 2, each returned record's own
   `Classification` re-enters the normal tier calculus at the point
   the *caller* uses it (ADR-0050 specifies exactly where and how) --
   this port itself does not gate anything; it returns real records
   with real, unmodified provenance attached, the same "port returns
   real data, application layer decides what's authorized" split
   every other port in this repo already follows.
4. **Retention/deletion mechanics** (ADR-0051) -- a real TTL
   (90-day default) plus a real, callable "pin" action extending an
   individual record's life indefinitely. The first real deletion
   path this codebase has ever had -- no existing port deletes
   anything today (confirmed in `m4-scoping-notes.md`'s own technical
   map), so this is genuinely new infrastructure, not an extension of
   an existing pattern.

### Application-specific

5. **Vector store + embedding pipeline** -- real, local-first
   (matching this project's own privacy-first identity), choice made
   by benchmark against the real eval set the exit gate names, not
   preference -- `m4-scoping-notes.md`'s own researched landscape
   (`sqlite-vec`, LanceDB, Qdrant/Milvus embedded modes, plain
   brute-force cosine similarity) is the real candidate list; **not
   decided in this document** which one wins, consistent with the
   exit gate's own "benchmark, not preference" bar and with this
   pass's own boundary (research and scoping, not implementation).
   Real, already-known constraint on this development machine (checked
   live during scoping): 8GB VRAM, 305GB free disk -- a real, modest
   bound on local embedding-model size if GPU inference is wanted for
   the embedding step itself, not just the vector index.
6. **`kernel/memory.py`** -- composition root, mirrors
   `kernel/music.py`'s/`kernel/desktop.py`'s own
   `authorize_and_run_*`/`authorize_and_*` pattern: real memory
   write/read capabilities registered in `build_default_registry()`,
   authorized through the unmodified `AuthorizationOrchestrator`
   choke point, no second authorization path.

## Acceptance criteria

1. `MemoryWritePort` has a real adapter that, given a `Tainted[T]`
   value carrying `Classification.SECRET`, is proven -- by a real test
   through the real `AuthorizationOrchestrator`, not merely documented
   -- to be denied unconditionally, matching ADR-0038's own required
   property-test rigor: a SECRET-classified value never reaches the
   vector store at any rung, under any circumstance, including when
   `physical_confirmation_available=True`.
2. `RetrievalPort` has a real adapter/test proving a recalled
   `Classification.SENSITIVE` (or higher) record re-triggers the same
   `CONFIRM`-or-stronger gate a live value of that classification would
   require -- not silently returned as if it were `PUBLIC`.
3. The retention mechanism has a real, executed test proving a record
   past its TTL is genuinely unreachable via `RetrievalPort` (not
   merely flagged), and a real test proving a pinned record survives
   past what its TTL alone would have allowed.
4. The vector-store/ANN-vs-brute-force decision is made and recorded
   with real benchmark numbers against the real eval set the exit gate
   names -- not asserted from general knowledge of the landscape
   (`m4-scoping-notes.md`'s own research is explicitly not a
   recommendation, per that document's own text).
5. No real-time indicator is built for memory recall, and no future
   work package under this milestone adds one without a fresh,
   explicit decision revisiting decision 4 -- checkable the same way
   ADR-0046's "no other capability may cite Terminal as precedent" is
   checkable: by a human reading this document, not (yet) a mechanical
   test, since there is no generic "indicator" abstraction in this
   codebase to grep for the absence of.

**Incomplete, stated plainly rather than padded**: this list does not
yet cover the real eval set's own contents (what queries/expected
results it contains is real, separate work, not decided by this
scoping pass), the exact embedding model choice, or a numeric
retention default other than the 90-day starting point decision 3
names (whether 90 days is right in practice is real, empirical
follow-up, not fixed permanently by this document).

## Package/class layout proposal

```
domain/
    memory.py              - MemoryRecord, RetrievalQuery, RetrievalResult;
                              reuses Classification/Trust/Provenance/Tainted[T]
                              as-is, no new provenance vocabulary
ports/
    memory_write.py         - MemoryWritePort
    retrieval.py              - RetrievalPort
adapters/
    memory/
        vector_store.py     - real adapter, technology TBD by benchmark
        embedding.py          - real embedding pipeline, local model
application/memory/
    classification.py       - memory_effect_for(), mirrors
                               application/reasoning/classification.py
                               exactly (ADR-0049)
    retention.py              - TTL/pin enforcement (ADR-0051)
kernel/
    capabilities.py          - extended: new CapabilityId constants for
                                memory write/retrieval, registered in the
                                same build_default_registry()
    memory.py                  - composition root, mirrors
                                  kernel/music.py's authorize_and_run_*
                                  pattern
```

No collision with M2/M3: `WorkspacePort`, `CandidatePresentationPort`,
`SecretPort`, `OutcomeSinkPort`, `DesktopWindowPort`, `SandboxPort`
all stay exactly as those milestones left them, none reused or
extended by this milestone.

## Worked example

*"Remember that I prefer tabs over spaces."* Resolved:
`memory.write` capability, argument classified `Classification.PERSONAL`
(a real preference, not a secret) by whatever upstream classification
this project already applies to user utterances. `memory_effect_for`
(ADR-0049) maps `PERSONAL` to `Effect.WRITE_LOCAL` (unchanged from
today's floor, `CONFIRM`) -- not `Effect.MEMORY_WRITE`'s `DENY` floor,
since that's reserved for `SECRET` specifically. `AuthorizationOrchestrator`
evaluates the real `Decision` through the existing choke point, same
shape as every other capability. If granted: the value is embedded and
written to the real vector store, tagged with its own real provenance,
TTL set to the 90-day default (decision 3).

Later: *"How do I like my code formatted?"* Resolved: `memory.retrieve`
capability, `Effect.READ_LOCAL`/`ALLOW` for the retrieval call itself
-- but the record it returns carries `Classification.PERSONAL`
provenance, which the *caller* (e.g. a future coding-capability
consumer) must itself re-evaluate before using it in a context that
would require `CONFIRM` for a live equivalent (ADR-0050). If the
90-day TTL had expired and the record was never pinned: `RetrievalPort`
returns nothing for that query, the same "denied capability, nothing
happened" shape every other gated action in this repo already has --
not a silent, still-findable-with-effort deletion, a real one.

## Confirmation boundary

`ConfirmationPort`/`ManualConfirmationAdapter` and
`PhysicalConfirmationPort`/`Gtk4PhysicalConfirmationAdapter` are reused
completely unmodified -- no new confirmation surface, matching M3's
own precedent exactly. `Effect.MEMORY_WRITE`'s `DENY` floor (ADR-0049)
is, per ADR-0038's own established reasoning already reused here
without modification, an absolute ceiling: no confirmation, physical
or remote, overrides it -- a SECRET-classified value cannot be
memorized even with the user standing at the keyboard actively trying
to approve it, the same unconditional guarantee ADR-0038 already
established for cloud egress.

## "Always legible"

No new indicator is built for memory recall -- decision 4, ADR-0052
records the full reasoning. `TtsPort` remains available, unmodified,
for any memory-related action a future work package decides is worth
announcing (e.g., a real memory *write* succeeding, which does carry
a form of real-world consequence -- something is now durably stored
that wasn't before -- a real, open question this document does not
resolve, flagged in ADR-0052 rather than silently decided either way).

## Work package sketch (WP-57 through WP-64)

Objective-level only, matching the depth M3's own deliverables were
scoped at before implementation started -- no code, no premature
commitment to exact class/method names beyond what this document
already fixes above. Real dependency ordering, not a fixed sequence
the implementing session must follow rigidly if it finds a genuine
reason to reorder.

- **WP-57 — Domain types and port shapes.** `domain/memory.py`
  (`MemoryRecord`, query/result types), `ports/memory_write.py`,
  `ports/retrieval.py` (ADR-0048). No real adapter yet -- contract
  tests only, against fakes, the same "port exists and is tested
  structurally before any real technology is chosen" ordering
  `DesktopWindowPort`/`SandboxPort` followed in M3.
- **WP-58 — SECRET write-time denial.** `Effect.MEMORY_WRITE`,
  `application/memory/classification.py`'s `memory_effect_for`
  (ADR-0049), and the required property test (a SECRET-classified
  value never reaches a real adapter at any rung). Built and fully
  gate-verified against fakes before any real vector store exists --
  the safety-critical piece lands first, not last, matching this
  project's own established discipline of proving the dangerous case
  before the happy path.
- **WP-59 — Retrieval-time re-evaluation discipline.** The real
  convention plus meta-test (ADR-0050) proving no code path discards a
  `MemoryRecord`'s own provenance when constructing a new
  `CapabilityInvocation` from it. Depends on WP-57's types existing;
  does not depend on a real vector store existing yet either.
- **WP-60 — Retention and deletion mechanics.** `expires_at`/pin
  fields, `application/memory/retention.py` (ADR-0051), real
  `ClockPort`-based expiry (never `datetime.now()`), and the real
  tests proving an expired-unpinned record is genuinely unreachable
  via `RetrievalPort` and a pinned one survives past its own original
  TTL.
- **WP-61 — Real vector store and embedding pipeline.** The one real
  spike-shaped work package, mirroring WP-43's own role for M3: check
  the real candidates `m4-scoping-notes.md` names
  (`sqlite-vec`/LanceDB/embedded Qdrant-or-Milvus/brute-force) against
  this real machine's actual constraints (8GB VRAM, confirmed live
  during scoping), and build the real, chosen adapter underneath
  `MemoryWritePort`/`RetrievalPort`. Local-first, no cloud embedding
  API considered unless a real, later work package makes that case
  explicitly (per this project's own privacy-first default).
- **WP-62 — Real eval set and the brute-force-vs-ANN benchmark
  decision.** Builds the actual eval set the exit gate names, runs the
  real benchmark, and records the real numbers -- the exit gate's own
  "made by benchmark, not preference" bar, satisfied for real, not
  asserted from `m4-scoping-notes.md`'s own general research.
- **WP-63 — Composition root and real capability registration.**
  `kernel/memory.py`, new `CapabilityId` constants in
  `build_default_registry()`, real `authorize_and_*`-shaped functions
  wiring everything above through the unmodified
  `AuthorizationOrchestrator` choke point -- the first point real,
  end-to-end memory write/retrieve calls exist as actual, invocable
  capabilities, not just isolated, tested-in-parts infrastructure.
- **WP-64 — M4 threat-model closeout.** `docs/threat-model/v0.md` gains
  a real "Milestone 4 additions" section; `CLAUDE.md`/`docs/ROADMAP.md`
  status updated to reflect what was actually built and verified --
  mirroring WP-55's own role for M3 exactly, including the same
  discipline of stating real, explicitly-accepted gaps plainly rather
  than rounding up to "done."

**Not included in this sketch, deliberately**: any work package for
vision/ScreenCast (decision 1 -- that scope now belongs to a future M5
work package, not this milestone's own numbering), and any live,
unattended verification step touching a real, irreversible action --
matching this project's own established pattern (WP-56's own real
portal call stayed unattempted until a session with the user
physically present) of drawing that line explicitly rather than
leaving it implicit until an agent runs into it mid-implementation.

## Deferred, not forgotten

- The exact vector-store/embedding-model choice (deliverable 5) --
  real, benchmark-driven follow-up work, not decided here.
- The real eval set's own contents -- separate, real work.
- Whether a memory *write* succeeding deserves its own "always legible"
  signal (distinct from decision 4's recall-specific answer) -- named
  as a real open question in ADR-0052, not pre-answered.
- `docs/ROADMAP.md`'s M4 *and* M5 row text both need updating to
  reflect decision 1 (vision's move) -- flagged under "Relationship to
  M5" above; only M4's own status cell is touched by this pass (see
  that file's own diff), not the objective text of either row.
