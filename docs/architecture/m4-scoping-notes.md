# M4 scoping notes — research and questions, not a design

**Status: prep material for a scoping conversation that has not happened
yet.** This is not `m4-memory-retrieval.md`'s real content, not an ADR,
not a design. Per this project's rolling-wave planning principle
(`docs/ROADMAP.md`) and CLAUDE.md's own hard rule ("never silently
change the architecture... propose a fix as a new ADR, and wait for
approval"), M4's real design starts only once the user has actually
answered the questions below — the same discipline that kept
`m3-desktop-control.md` a stub until M3 genuinely became the next
milestone and its own three real ambiguities got resolved in
conversation before a line of that document was drafted. Nothing here
authorizes writing `ports/`, `adapters/`, or `application/` code, or an
ADR, for M4. Written during an overnight autonomous pass (2026-08-25)
per the user's own explicit request for scoping prep, not a scoping
decision.

`m4-memory-retrieval.md` itself remains untouched, gate-only, exactly
as it was before this document existed.

## Why this document exists: the pattern M2 and M3 each needed

Neither prior milestone got a real design by just expanding its
one-line ROADMAP objective. Each needed a small number of genuine,
user-decided scope questions resolved first:

- **M2** (per `m2-reasoning-layer.md`'s own recovered framing and the
  real WP-28 reconciliation pass) needed the recovered pre-M0 design
  reconciled against what M0 actually became -- real gaps like "no
  keyring adapter exists despite ADR-0017 presupposing one" (ADR-0042)
  and "nothing decided how a Candidate's content becomes real files a
  validator can check" (ADR-0043) only surfaced once someone tried to
  implement against the recovered design and found it didn't match
  reality.
- **M3** (per `m3-desktop-control.md`'s own header) needed three
  genuine ambiguities resolved *in conversation, before drafting*:
  Terminal's mechanism (portal+libei vs. AT-SPI2 -- resolved partly
  wrong at first, per WP-43's own spike finding libei's binding
  absent, then corrected for real via ADR-0047), M2-retrofit scope
  (should M3's sandboxing retrofit onto M2's already-shipped
  unsandboxed validators? decided: no, tracked as a real, separate
  follow-up instead), and M3/M5 overlap (Brave/VS Code: shallow
  ordinary-control now, deep CDP/LSP automation later, resolved as an
  explicit split once real, already-installed CLI tooling was checked
  on the actual machine).

M4's own ROADMAP objective -- *"Memory, hybrid retrieval, retrieval
eval set. Vision via ScreenCast/PipeWire"* -- has at least as much
buried ambiguity as M3's one-line objective did. The questions below
are this pass's attempt to surface it now, the same way M3's three
were surfaced before any design work started, so the eventual scoping
conversation can move fast instead of re-deriving each question from
scratch.

## Part 1: real scope decisions the user will need to make

### 1. Is "Vision via ScreenCast/PipeWire" actually part of M4, or does it belong to M3 or M5?

The ROADMAP's own M4 objective bundles two things that don't obviously
belong together: memory/retrieval (a storage and search problem) and
vision (a screen-capture-and-understand problem). Real, concrete
tension worth naming explicitly, mirroring M3/M5's own overlap
resolution:

- M3 already has a real, live-verified mechanism for reading on-screen
  content -- `DesktopWindowPort.read_visible_text` (AT-SPI2). Vision
  via screenshot would be a second, structurally different way to
  answer a similar question ("what's on screen") for apps AT-SPI2
  can't read cleanly (this session's own overnight audit re-confirmed
  Chromium/Electron apps' AT-SPI2 trees are thin when the system
  accessibility bridge is off -- exactly the case a screenshot-based
  fallback would help with).
  - **Question**: does M4's vision component reuse/extend
    `DesktopWindowPort`, become its own new port, or get pulled out of
    M4 into a future M3 follow-up entirely?
- M5's own ROADMAP row is browser automation via CDP -- a real
  browser screenshot/DOM-inspection capability that CDP already
  provides natively, with no separate ScreenCast/PipeWire mechanism
  needed for in-browser content specifically.
  - **Question**: is M4's vision scope meant for *desktop* content
    broadly (any app, not just the browser), making it genuinely
    distinct from M5's browser-specific CDP access? If so, say that
    explicitly the way M3/M5's split document says it, rather than
    leaving the boundary implicit.
- **A real, narrower question inside this one**: is vision even needed
  for M4's *retrieval* objective at all, or was it bundled into this
  row for planning-table convenience (one XL milestone, not two
  M-sized ones) rather than a real technical dependency? If retrieval
  doesn't actually need vision to ship a real eval-set-measured
  result, splitting it out (its own future milestone, or folded into
  M3/M5) may be the cleaner scope, matching M3's own "keep the
  milestone scoped to what it's actually named for" reasoning about
  not quietly expanding into M2 hardening.

### 2. What gets memorized, and what doesn't -- a real classification question, not just a storage question

This project's `Tainted[T]`/`Provenance` system (ADR-0008–0011) already
answers "how trusted/sensitive is this value" for every value that
flows through a capability today. Memory is the first system whose
entire purpose is to make old values available again later, which
raises real questions those ADRs don't yet answer:

- Does a `SECRET`-classified value ever get memorized at all? ADR-0014
  says SECRET is DENY to any cloud provider, unconditionally, no
  exception path -- does an on-device memory store count as "reaching
  a cloud provider" (no) or does the *retrieval* of a memorized SECRET
  back into a prompt that later reaches a cloud-bound `ReasoningPort`
  call count (very plausibly yes, and this is exactly the kind of gap
  ADR-0038 closed for M2's own direct egress path -- memory could
  become a second, unguarded egress path for exactly the same class of
  value if this isn't decided explicitly).
- Does memorizing a value change its own `Trust`/`Classification`, or
  does the memorized copy inherit the original's provenance
  unconditionally? A `SENSITIVE` value recalled six months later and
  fed into a fresh cloud-bound prompt still needs the same CONFIRM
  gate ADR-0015 already requires for a live one -- does retrieval
  re-run that gate, or was it only ever checked once, at write time,
  which would be a real, silent weakening?
- Is "write to memory" itself a capability the Policy Engine evaluates
  (an `Effect.WRITE_LOCAL`-shaped decision, audit-logged like every
  other capability invocation per this project's own "every capability
  invocation is logged" principle), or an internal mechanism outside
  that choke point? The whole architecture's own core principle (ADR-0005:
  "a single Policy Engine as the sole authorization choke point") argues
  strongly for the former -- but M4 is the first system whose actions
  are genuinely internal book-keeping (nothing external happens when a
  memory gets written) rather than an effect on the outside world,
  which is a real, new shape this architecture hasn't had to classify
  before.

### 3. Retention and deletion -- does JARVIS forget anything, ever, and who decides?

Real, user-facing product questions with real architectural
consequences, not yet answered anywhere in this repo:

- Is there a real, callable "forget X" capability, or is memory
  append-only until a size/age-based eviction policy prunes it
  automatically? These have very different real designs (the former
  needs a real deletion path through whatever storage/index M4 picks;
  the latter needs an eviction policy that itself needs deciding).
- Does memory ever get a TTL, or is "personal, evolving memory" meant
  to be permanent by default (the more common product framing for
  memory-feature competitors) -- and if permanent by default, does
  that sit comfortably next to this project's own privacy-first
  identity, or does it need an explicit, stated tension the way
  M1's "always-on listening is a new, permanent privacy surface"
  section names its own real, unresolved consent gap plainly rather
  than assuming it away?
- Real prior art worth the user's own review before deciding (see
  Part 2 below for the actual landscape) -- comparable local-first
  tools generally pick one of: explicit user-triggered deletion only
  (no automatic forgetting), a visible, editable memory list the user
  can prune directly (closer to a real UI feature than a policy), or
  time-boxed retention with explicit renewal. Which of these (or a
  genuine fourth option) fits this project is a real product decision,
  not a technical one this pass can make.

### 4. Does memory retrieval get its own real-time-legibility indicator, matching ADR-0047's own precedent?

`docs/ROADMAP.md`'s own "always legible" standing principle already
requires every JARVIS action be legible to the user in real time, and
ADR-0047 just built a real, concrete precedent for what that looks
like when a capability's own safety story depends on it (the
sandboxed terminal's real-time visual/audible indicator). Memory
retrieval silently injecting old, possibly-stale or possibly-wrong
personal context into a live conversation is a real, plausible
failure mode a user might never notice without some equivalent
signal.

- **Question**: does M4 need its own version of "here's what I just
  recalled and used," spoken or shown, before/while a memorized value
  is used -- or is silent retrieval acceptable because (unlike
  ADR-0047's synthetic keystrokes) a wrong memory recall is
  self-correcting in conversation (the user can just say "that's not
  right") rather than an unrecoverable real-world action?

### 5. What does M4 retrofit onto vs. build net-new? (Part 3 below has the concrete technical map to inform this, not decide it)

Mirroring M3's own explicit "does this retrofit onto M2" decision:
does M4 reuse `SecretPort` (for any credentials an embedding
API/vector-store service might need, if a local-only choice isn't
made), `WorkspacePort` (if memory ever materializes retrieved content
as real files for a validator-like consumer), or
`CandidatePresentationPort` (if retrieval results ever need human
review before use, the same shape M2's unverifiable-task surface
already established)? Or does M4 need enough genuinely new
infrastructure (a vector index, an embedding pipeline, a retrieval
query port) that framing it as a "retrofit" onto existing ports
undersells how much of M4 is really new? Part 3's technical map below
is meant to make this an informed question, not to answer it.

## Part 2: research, not a recommendation baked into any decision

### Local-first vector store landscape (as of general knowledge; worth re-confirming current state before deciding, not treated as freshly verified here)

Real constraints on this actual development machine, checked live
this pass (informs the tradeoffs below, doesn't decide them): 305GB
free disk, an RTX 5070 Laptop GPU with 8GB VRAM (real, but modest --
a real constraint on embedding-model size if local GPU inference is
wanted for the embedding step, not just the vector index itself).

- **`sqlite-vec`** (successor to the now-archived `sqlite-vss`) --
  a SQLite extension, not a separate service. Real advantages for this
  project specifically: zero new daemon/process to run or sandbox, no
  new network-facing surface at all (fits "privacy-first, local"
  cleanly), and this project's own audit chain (`JsonFileAuditStorageAdapter`)
  already establishes a precedent for plain-file, no-external-service
  persistence. Real tradeoff: brute-force or basic-index search only
  at real scale, not a production-grade ANN index -- fine for a
  personal-assistant-scale memory store (thousands to low tens of
  thousands of entries), a real question mark at much larger scale.
- **LanceDB** -- an embedded, local-first vector database (Rust core,
  Python bindings), file-based like SQLite but purpose-built for
  vector search with real ANN indexing. Heavier dependency footprint
  than `sqlite-vec`, but a real, more scalable option if retrieval
  quality at larger real memory sizes matters more than minimal
  dependency weight.
- **Qdrant / Milvus (embedded/lite modes)** -- both have local,
  embedded deployment modes (not just server-only), real production
  ANN indexing. Real tradeoff: meaningfully heavier dependencies and
  operational surface than `sqlite-vec`/LanceDB for what may be a
  single-user, laptop-scale memory store -- worth real benchmarking
  against actual eval-set numbers (per M4's own exit-gate criterion:
  "brute-force-vs-ANN decision made by benchmark, not preference")
  before assuming the heavier option is warranted.
- **FAISS** -- a library, not a database (no persistence/query
  layer of its own) -- real option only paired with something else
  handling storage/metadata, more integration work than the above.
- **Plain brute-force cosine similarity over an in-memory/`numpy`
  array, backed by SQLite for persistence** -- genuinely worth
  real, first-class consideration, not a strawman: M4's own exit
  gate already names "brute-force-vs-ANN decision made by benchmark"
  as the real bar, and for a single-user memory store that may never
  exceed tens of thousands of entries, brute-force cosine similarity
  is fast enough in practice that an ANN index may add real complexity
  for no measurable retrieval-latency benefit -- this needs the real
  benchmark the exit gate already calls for, not an assumption either
  way.

Real, not-yet-answered technical question this list surfaces: what
generates the embeddings themselves? A local model (real GPU
constraint: 8GB VRAM is real but modest -- most small/medium local
embedding models fit comfortably; large ones may not) vs. a
cloud-provider embedding API (would need `SecretPort` for a real
credential, and would raise the exact SECRET/SENSITIVE egress
questions Part 1's item 2 above already names) is itself a real scope
question, not decided by the vector-store choice alone.

### Retention/deletion prior art from comparable local-first, privacy-first tools

Real, general patterns worth the user's own review (not a survey of
specific named competitor products, since this project's own "no
vendor names" discipline in `domain`/`application`/`ports` is a real
architectural principle worth honoring in spirit even in a research
document, and because pinning specific product claims without live
verification would be exactly the kind of unverified assertion this
engagement has consistently avoided elsewhere):

- **Append-only with explicit, user-triggered deletion only** -- the
  simplest real model: nothing is ever auto-pruned; the user must
  explicitly ask to forget something. Real tradeoff: memory can grow
  unbounded over real time, and "explicit deletion" only works if the
  user actually knows what's stored -- pairs naturally with a real,
  visible/reviewable memory list (a genuine UI/UX question, not purely
  a backend one).
- **Visible, editable memory as a first-class UI surface** -- treating
  memorized facts as user-owned, reviewable, individually-deletable
  records (closer to a settings page than a hidden cache) is a common
  real pattern specifically in privacy-conscious tools, since it makes
  the "what does this system know about me" question answerable by
  inspection rather than trust alone.
- **Time-boxed retention with renewal** -- memories expire after a
  fixed window unless "refreshed" by being recalled/reused again.
  Real tradeoff: naturally bounds storage growth and staleness risk,
  but adds real complexity (a real renewal/expiry mechanism) for a
  benefit (bounded growth) that append-only-with-manual-deletion may
  already get for free at personal-assistant scale, where total
  memory volume is unlikely to be large in absolute terms regardless
  of retention policy.

None of the above is a recommendation; each is real prior art the
eventual scoping conversation can weigh against this project's own
stated identity ("privacy-first" in `CLAUDE.md`'s own opening line) and
against Part 1's own retention question.

## Part 3: what this project's existing infrastructure already provides M4 for free, vs. what's genuinely net-new

A real technical map, useful regardless of which Part 1 answers the
user eventually gives -- checked against the actual current codebase,
not assumed:

**Already exists, real, reusable as-is:**

- `Tainted[T]`/`Provenance` (`domain/provenance.py`) -- the exact
  vocabulary needed to carry a memorized value's original
  `Trust`/`Classification` forward. M4 doesn't need a new provenance
  system; it needs a real decision (Part 1, item 2) about how
  retrieval interacts with the *existing* one.
- `AuditChain`/hash-chained audit log (ADR-0026/0027) -- if memory
  writes/reads become real, Policy-Engine-gated capability invocations
  (Part 1, item 2's open question), this project's existing audit
  infrastructure logs them for free, with the same tamper-evidence and
  digest-only-never-raw-values guarantee every other capability
  already gets. No new logging mechanism needed.
- `SecretPort` (ADR-0042, with `set_secret` added in WP-56/ADR-0047) --
  if a cloud embedding API or any credentialed remote service is ever
  chosen over a fully local embedding model, the credential-handling
  story is already solved, read and write both.
- `AuthorizationOrchestrator`/the four-tier Policy Engine
  (ADR-0005/0006) -- if memory read/write become real capabilities,
  authorization is the existing choke point, not a new one to build.
- `WorkspacePort` (ADR-0043) -- if retrieved memory content ever needs
  to become real, on-disk files for some downstream consumer (e.g., a
  future coding-agent capability that wants memorized context as a
  real file a validator can check), this already exists.
- The `SandboxPort`/`bwrap` mechanism (ADR-0044) -- reusable
  general-purpose infrastructure if any part of M4's own pipeline
  (e.g., running an untrusted or resource-heavy local embedding/
  indexing process) ever wants blast-radius containment; not
  presumed needed, just available.

**Genuinely net-new, no existing precedent to build on:**

- The vector store / index itself (Part 2's own landscape).
- The embedding pipeline (model choice, real GPU/CPU inference path,
  matching this project's own established "real, injectable,
  untested-by-design real-hardware seam" pattern every other
  hardware-dependent adapter in this repo already uses).
- A real retrieval-query port/capability shape -- nothing in this
  codebase today answers "search past context for something relevant,"
  a genuinely new kind of read operation distinct from
  `FileSystemPort.read_file`'s single-known-path shape.
- Retention/deletion mechanics themselves (Part 1, item 3) -- no
  existing port in this codebase deletes anything at all today; this
  would be a first.
- Whatever the vision/ScreenCast component turns out to need (Part 1,
  item 1) -- entirely contingent on that scope question's own answer.
