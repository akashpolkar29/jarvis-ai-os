# M7 code-context design (7 real decisions prompt, Decision 7, 2026-09-05)

## Status

Real design proposal, not yet implemented, not yet reviewed by the
user. Builds directly on `docs/architecture/m7-scoping-notes.md`'s own
real finding (Part 2): `coding.run_task` currently sends a provider no
real repository content at all -- `build_prompt()` never touches the
filesystem, confirmed by reading it directly. That finding is not
repeated in full here, only extended into a real design. **No
`Dispatcher`/`EscalationLadder` code is touched by this document** --
the mechanism proposed below changes what `run_coding_task`/
`Dispatcher.run()`'s own *caller* passes in as the task string, not
`Dispatcher`'s own internals.

## The real question this design answers: which mechanism, and why

`m7-scoping-notes.md`'s own Part 2 already reframed the original
"does this need LSP" question into a more basic one: does
`coding.run_task` give a provider *any* real file content at all. This
document proposes the real, minimal answer to that reframed question.

## Recommendation: minimal, non-LSP file-context injection (scoping notes' own option 2)

**Real mechanism**: a new, small function in `application/coding/`
(not a new port) that, given a task description and a target repo
path, identifies a small, bounded set of real files to include and
reads their real content via the *already-existing*
`WorkspacePort`/`SandboxPort` machinery `run_coding_task` already
constructs a disposable workspace through (ADR-0055's own amendment,
WP-73) -- no new port, no new adapter, no new dependency.

**File-selection heuristic, kept deliberately simple for a first
version**: files the task description names directly (a real,
literal path or filename substring match against the repo's own real
file tree), plus, on a retry climb, files a prior failed attempt's own
validation evidence references (e.g. a pytest traceback naming a real
file and line). No semantic/symbol resolution, no "find every real
caller of this function," no dependency graph -- purely textual,
bounded-file inclusion, exactly as `m7-scoping-notes.md`'s own option
2 described. A real, explicit cap on total included content (e.g. a
fixed byte/line budget across all included files) is required to keep
prompts bounded -- unbounded inclusion of an entire large repo is a
real, separate problem this design does not attempt to solve.

**Why this over full LSP integration (option 1)**: `m5-scoping-notes.md`'s
own already-completed, real, live-checked research into the Python LSP
client landscape found every real candidate library either poorly
maintained or unreviewed -- a real, meaningful cost (a new client
dependency, a new `LspPort`/adapter, a real running
language-server-per-language-per-repo lifecycle to manage) for
capability (symbol/type/reference-aware context) that a much simpler
mechanism can partially substitute for at a fraction of the cost. LSP
remains real, valid future scope if the simpler mechanism proves
insufficient in practice -- this design does not foreclose it, it
sequences the cheaper, real option first, matching this project's
own repeated "prove the simple thing insufficient before building the
complex one" discipline (e.g. brute-force cosine similarity chosen
over `sqlite-vec` for M4's retrieval layer, decided by a real
benchmark, not preference).

## Real, precise taint/provenance treatment for injected file content

**This is the one genuinely new safety question this design
introduces, distinct from LSP-vs-not**: file content read from a
target repository is not automatically `Provenance.user()` just
because the *task description* was user-supplied. A real repository
can contain code the user did not personally write -- a cloned
open-source dependency, a file from an untrusted contributor's PR
branch, etc. Reading it and embedding its content into a prompt sent
to a `ReasoningPort` provider is a real, meaningful egress-classification
question this project's own existing taint model already has the
vocabulary for (`Trust.UNTRUSTED_EXTERNAL`, the same tag
`BrowserAutomationPort`'s own scraped page content already carries),
but no existing capability has had to answer it for *file content*
specifically before.

**Real, proposed default, matching this project's own "fail closed
when uncertain" principle (already stated in `CLAUDE.md`'s own
Privacy model section)**: injected file content is tagged
`Trust.UNTRUSTED_EXTERNAL` by default, not `Trust.USER_DIRECT`, unless
a real, specific signal establishes otherwise (e.g., a file the task
description's own text quotes verbatim, arguably already "seen" by the
user in the act of writing the task). This has a real, concrete
consequence via existing classification rules, not a new mechanism:
`Classification` still comes from the file's own real content (a
`SECRET`-shaped file, e.g. one containing an API key literal, still
floors at unconditional `DENY` to any cloud provider exactly as
today), but the *trust* dimension being `UNTRUSTED_EXTERNAL` means this
content should be treated with the same suspicion this project already
extends to scraped web content or a third-party email body -- not
blindly trusted as if the user typed it themselves.

**Real, open sub-question, not resolved here**: whether this
classification should be uniform for the whole target repo, or vary
by file (e.g. a file inside a `vendor/`/`node_modules/`-style
third-party directory classified more suspiciously than a file at the
repo's own top level) -- a real, finer-grained policy this document
flags but does not design, since it depends on real, observed patterns
this mechanism hasn't been built long enough to have gathered yet.

## What changes structurally, concretely

- A new, small function (tentatively `_select_context_files(task, repo_path,
  prior_attempts) -> tuple[Tainted[str], ...]`) in `application/coding/`,
  called from wherever `run_coding_task` currently builds its own task
  string before handing it to `Dispatcher.run()`.
- `build_prompt()` itself (`adapters/reasoning/_prompt.py`) gains an
  optional, additional section for included file content, appended
  after the existing task/prior-attempts sections -- a small, additive
  change, not a rewrite of its existing, already-tested logic.
- No new port, no new adapter, no new third-party dependency.

## What this document does not decide

Whether to build this at all, the exact real byte/line budget, the
exact file-selection heuristic's own precise matching rules, and the
open per-file-vs-uniform trust-classification question above are all
the user's own decisions, not pre-empted here. Unlike the task-planning
design's own per-step-authorization property, nothing in this specific
design rises to the level of needing its own dedicated ADR on its
own merits -- the taint-classification default proposed above reuses
existing `Trust`/`Classification` vocabulary and existing rules
without adding a new `Effect` member or changing any existing
capability's tier, so it is recorded here as a real, reasoned design
default for the user's own review, not elevated to a separate ADR the
way the task-planning design's own no-batch-pre-approval property was.

## Real implementation (2026-09-05)

Built the same day, real, direct instruction. `application/coding/context.py`'s
`inject_referenced_file_context` implements the file-selection
heuristic's own first half (files the task text names literally) --
the retry-time, evidence-referenced half remains real, deferred scope,
not built (see that module's own docstring). A real, explicit,
combined-across-all-files budget (8000 characters) bounds inclusion; a
file that cannot be read as UTF-8, or that escapes `target_repo`'s own
real boundary via a `../`-style token, is silently skipped, not
treated as an error.

**A real, deliberate compatibility decision, not silently defaulted
on**: this is wired as **opt-in**, a new `include_referenced_file_context: bool = False`
field on `CodingTaskRequest` (and the matching parameter on
`kernel/coding.py`'s own `authorize_and_run_coding_task`) -- every
existing caller's exact prior behavior is preserved unchanged unless
it explicitly opts in. Feeding real, potentially-`UNTRUSTED_EXTERNAL`
repository content into every coding task's prompt by default would
be a real, meaningful behavior change to an already-shipped,
already-tested feature, not something to flip on silently as a side
effect of adding the mechanism.

Real, end-to-end tests (`tests/integration/test_coding_loop.py`) prove
both directions against a real `Dispatcher`/sandbox/workspace stack: a
granted `include_referenced_file_context=True` call has the real
target file's own current content reach the real provider's own
`generate()` call; the default (unset) leaves the task text completely
unchanged, byte for byte, matching every prior test's own already-
established expectations.
