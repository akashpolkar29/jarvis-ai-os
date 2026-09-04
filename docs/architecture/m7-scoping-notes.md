# M7 scoping notes — two carried-forward gaps, investigated, not decided

**Status: research only. No decision made, nothing built.** This
document does not itself commit the project to an "M7" milestone —
`docs/ROADMAP.md` names no M7 row today, and creating this file is not
the same as creating one. The name mirrors this project's own existing
`mN-scoping-notes.md` convention (`m4-scoping-notes.md`,
`m5-scoping-notes.md`, `m6-scoping-notes.md`) purely as a real,
consistent place to record investigation of two genuine, previously-
named-but-unresolved capability gaps, both explicitly flagged as open
in past reports and both revisited here per direct instruction. Per
this project's rolling-wave planning principle and CLAUDE.md's own
hard rule ("never silently change the architecture... propose a fix
as a new ADR, and wait for approval"), nothing here authorizes writing
`ports/`, `adapters/`, or `application/` code, or an ADR. Written
2026-09-04.

## 1. "Intelligent task planning" — is the Dispatcher/EscalationLadder mapping honest?

### What the charter names, and what's currently claimed

The charter names "intelligent task planning" as a capability.
`docs/threat-model/v0.md`'s own "Overnight Track 6" note (2026-09-04)
currently states this maps to M2's `Dispatcher`/`EscalationLadder`
machinery, with no dedicated kernel module of its own — CLAUDE.md
repeats the same claim. This section checks that mapping directly
against the real code, not by re-reading the claim.

### What `Dispatcher`/`EscalationLadder` actually do, quoted directly

`application/reasoning/ladder.py::EscalationLadder.next_rung()` — the
real state machine:

```python
def next_rung(self, attempts: tuple[Attempt, ...]) -> EscalationRung | None:
    if any(attempt.verdict is Verdict.PASSED for attempt in attempts):
        return None
    if not attempts:
        return EscalationRung.DETERMINISTIC_FIX
    highest_attempted = max(attempt.rung for attempt in attempts)
    if highest_attempted is _HIGHEST_RUNG:
        return None
    return EscalationRung(highest_attempted + 1)
```

Three fixed rungs total (`EscalationRung`: `DETERMINISTIC_FIX`,
`SELF_REPAIR`, `SECOND_PROVIDER`), climbed in one fixed order, for
**one already-specified task** (a single `Tainted[str]`), never
decomposed. `application/reasoning/dispatcher.py::Dispatcher.run()`
loops calling `next_rung`, trying whichever providers are registered
for that rung, and returns the winning `Attempt` once one passes or
the ladder terminates. `application/coding/loop.py::run_coding_task`
wraps this in a retry-budget loop (`DEFAULT_MAX_CLIMBS = 3`) that
re-runs the *same* task, seeded with the prior climb's own failure
evidence (`_seed_next_climb_task`), never a different, decomposed
sub-task.

`application/reasoning/unverifiable.py::UnverifiableTaskHandler.handle()`
— the other real M2 code path — asks every authorized provider the
*same* single task in parallel and hands the results to a human; also
no decomposition.

### The real, honest answer

**The mapping is not accurate as a full charter-capability claim.**
`Dispatcher`/`EscalationLadder` implement **retry/escalation
strategy** for one already-decided, already-scoped unit of work — "how
hard to try, and at what cost tier, before giving up or asking a
human" — never **decomposition of a high-level goal into an ordered
sequence of distinct sub-tasks or capability calls** (e.g., "email the
report, then create a calendar event to review it" — two distinct
capabilities, sequenced, with a dependency between them). Nothing in
this codebase does that today. `coding.run_task`/`job_assistance.draft`
each take one task string and drive one mechanism (`Dispatcher` or
`UnverifiableTaskHandler`) against it; neither ever produces or
executes a real, multi-step plan spanning more than one capability.

This is a real, previously-imprecise claim, not a fabricated new gap
— the underlying machinery genuinely exists and genuinely does
something real and useful (bounded, policy-gated escalation for a
single task), it is just not "task planning" in the sense a reader of
the charter would likely expect (multi-step, cross-capability
orchestration toward a stated goal).

### Real options for closing the gap, not decided here

1. **Narrow the charter-capability's own stated scope** to match what
   actually exists — rename the internal claim from "task planning"
   to "task escalation/retry," and treat multi-step cross-capability
   planning as a real, separate, not-yet-built capability. Cheapest,
   most honest immediately, but leaves the charter's own original
   intent unmet if "task planning" was meant literally.
2. **Build a real, minimal planner** as new `application`-layer code:
   given a natural-language goal, produce an ordered list of
   capability invocations (already-existing `CapabilityId`s only, not
   new ones) with real dependencies between steps, then drive that
   plan through the existing `AuthorizationOrchestrator` one step at a
   time — each step still individually authorized exactly as today,
   planning only decides *order and selection*, never bypasses
   authorization. Real, open sub-questions this option raises: where
   does the plan itself get generated (a `ReasoningPort` call, subject
   to the same EGRESS/taint rules every other cloud-provider call
   already follows)? Does a failed step abort the whole plan or
   retry/replan? Is a plan ever shown to the user before execution
   (mirroring `physical_confirmation`'s existing role) or does each
   step's own tier gate suffice?
3. **Defer indefinitely, named explicitly as deferred** rather than
   quietly left implicit — if the user judges "task planning" was
   always meant loosely (i.e., `Dispatcher`'s own escalation *is* the
   intended scope, just under-specified charter language), record that
   as a real, deliberate scope narrowing in a future ADR rather than
   leaving today's imprecise mapping standing uncorrected.

No option is recommended over another here — this is investigation,
not a proposal ranking.

## 2. LSP-based code intelligence — what would it actually take, and does `coding.run_task` already get enough context without it?

### What was already investigated (M5, not repeated here)

`m5-scoping-notes.md`'s own "Part 2" (written 2026-08-31, before M5
was built) already did substantial, real, live-checked research into
the Python LSP client landscape — `multilspy` (Microsoft Research,
hardcoded language servers, "not very maintained"), `sansio-lsp-client`
(sans-IO, low recent activity), `lsp-client` (newer, unreviewed
elsewhere), explicitly ruling out `pygls`/`python-lsp-server` as
servers, not clients. That research is not repeated here — see that
document directly. **What is new in this section**: M5 has since been
built (code-complete, tagged v0.5.0) *without* LSP — CLAUDE.md's own
M5 status names this plainly ("LSP-based code intelligence — half of
this milestone's own original working assumption — was never answered
or built, real, unresolved scope carried forward, not quietly
dropped"). This section investigates the real, current question that
research alone couldn't answer before real coding-agent code existed:
does the real, now-built `coding.run_task` already receive enough
context without it?

### What `coding.run_task` actually sends to a provider, quoted directly

`adapters/reasoning/_prompt.py::build_prompt()` — the real function
that assembles what a provider actually reads:

```python
def build_prompt(task: str, prior_attempts: tuple[Attempt, ...]) -> str:
    if not prior_attempts:
        return task
    lines = [task, "", "Prior attempts at this task, in order:"]
    for index, attempt in enumerate(prior_attempts, start=1):
        lines.append(
            f"\nAttempt {index} (by {attempt.candidate.author}, verdict: {attempt.verdict.value}):"
        )
        lines.append(attempt.candidate.content)
        for evidence in attempt.evidence:
            lines.append(f"  - {evidence.description}")
    return "\n".join(lines)
```

**No filesystem read happens anywhere in this function, or anywhere
between `CodingTaskRequest.task` and this call.** The only real
content a provider ever receives is: (1) the caller-supplied task
description text, verbatim, and (2) on a retry climb, the prior
attempt's own candidate content (typically the rejected patch text)
and validation-evidence descriptions (e.g. test failure output).
Confirmed directly in `LocalReasoningAdapter.generate()`
(`adapters/reasoning/local.py`) — the one real, live-verified provider
— which calls `build_prompt(task, prior_attempts)` and nothing else
before making the real Ollama API call.

### The real, honest answer

**No — `coding.run_task` does not currently give a provider any real
repository content at all**, LSP-derived or otherwise, beyond whatever
free text the caller happens to type into the task description. A
real task like "fix the bug in `foo.py`" reaches the local provider
today with zero visibility into `foo.py`'s actual contents unless the
caller manually pastes them into the task string. This reframes the
original question: the real, more urgent gap may not be "does this
project need LSP's specific symbol-aware capabilities" so much as
"does `coding.run_task` give a provider *any* real file content at
all" — LSP (semantic, symbol/type-aware) is one real way to close
that, but a much simpler mechanism (reading and embedding relevant
file contents directly into the prompt, no protocol client needed)
would close the more basic version of the same gap at a fraction of
the real, new-dependency cost `m5-scoping-notes.md`'s own client-
landscape research already surfaced.

**One real caveat, not overlooked**: a *cloud-hosted*, genuinely
agentic coding provider (unlike the local Ollama model, which has no
tool-calling of any kind) could plausibly read files itself via its
own tool-use capability, entirely outside anything this codebase
controls — in which case the real gap this section identifies applies
specifically to non-agentic/local providers, not universally. This
project has never configured or tested a real cloud coding provider
(deliberately, per repeated prior instruction), so this remains
untested, not assumed either way.

### Real options for closing the gap, not decided here

1. **Full LSP integration**, per `m5-scoping-notes.md`'s own
   already-researched client landscape (`lsp-client` looks like the
   most actively-maintained real candidate as of that search, but
   needs re-confirming at actual implementation time). Real cost:
   a new client library dependency, a new `LspPort`/adapter, a real
   running language-server-per-language-per-repo lifecycle to manage
   — the heaviest option, but the only one that gives genuinely
   semantic (symbol/type/reference-aware) context, not just raw text.
2. **Minimal, non-LSP file-context injection**: given a task and a
   target repo, read a small, bounded set of real, relevant files
   (e.g. ones the task text names directly, or ones a prior failed
   attempt's evidence references) and embed their real content
   directly into the prompt `build_prompt` already assembles — no new
   port, no new dependency, a much smaller real change confined to
   `application/coding/`. Real limitation: no symbol resolution across
   files, no "find every real caller of this function" — purely
   textual, bounded-file inclusion.
3. **Defer indefinitely, named explicitly as deferred** — if the
   user judges the current, no-file-content behavior acceptable for
   now (e.g. because real cloud providers with their own tool-calling
   are the intended real deployment target, not the local model),
   record that as a real, deliberate scope decision rather than
   leaving "never answered or built" standing as an open question
   forever.

No option is recommended over another here — this is investigation,
not a proposal ranking.
