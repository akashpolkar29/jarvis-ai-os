# ADR-0055: M5's coding loop wraps the M2 dispatcher, rather than retrofitting it

## Status

Proposed

**Not yet reviewed by the user in conversation** — drafted from a remotely-reasoned working assumption (`m5-browser-coding.md`'s own header explains the distinction from M4's ADRs, all of which the user confirmed directly). Do not mark Accepted without the user's own direct review.

## Date

2026-08-31

## Source

M5 scoping answer 3 (relayed to this pass as a fixed working assumption, not confirmed in conversation): *"does not modify M2's `Dispatcher`/`EscalationLadder` core. Build a new, minimal coding-loop wrapper on top of it (in `application/coding/` or similar) — apply patch, run tests, feed failures back — as net-new orchestration, not a retrofit of M2."* Directly answers the real, open question `m5-scoping-notes.md`'s own Part 1, item 3 posed (checked against `application/reasoning/dispatcher.py`/`ladder.py` directly, not assumed) without yet deciding the deeper sub-question that same item raised.

## Context

Checked directly against `application/reasoning/dispatcher.py` and `domain/evidence.py`, not assumed: `Dispatcher._attempt_rung` calls `ReasoningPort.generate(task, prior_attempts)` once per provider per rung, and each call returns exactly one `Candidate` — a single `str` (`Candidate.content`), produced in one shot, with no notion inside that one call of an interactive, multi-turn session. `WorkspacePort.apply_patch` matches this shape exactly: one unified-diff string, applied once, per accepted candidate. `EscalationLadder.next_rung` climbs at most three rungs total per task (`DETERMINISTIC_FIX` → `SELF_REPAIR` → `SECOND_PROVIDER`), each attempted at most once.

A real coding task — "fix this failing test," "add this feature to this real repository" — plausibly needs more than three total attempts, and plausibly needs the *same* rung's own provider to see a test failure and try again without necessarily escalating to a more expensive provider each time. Neither of these is a design flaw in the existing M2 machinery: `EscalationLadder`'s own docstring names its bound as deliberate ("Escalation is bounded... the ladder must terminate rather than loop or invent one"), matching ADR-0022's own three-phase model (deterministic fixes, self-repair, second-provider consultation) — a real, already-Accepted architectural decision this ADR does not reopen.

**Real options considered, mirroring the shape ADR-0043's own Context section laid out for `WorkspacePort`**:

1. **Modify `EscalationLadder`/`Dispatcher` directly** — add a fourth concept (a bounded retry loop within one rung, say) to the already-Accepted, 100%-branch-coverage-gated (`application/reasoning`, ADR-0041) core of M2. Rejected: this is exactly the "retrofit" the working assumption explicitly declines, and for a real, structural reason beyond just following the given answer — `EscalationLadder`'s own five stated invariants (`application/reasoning/ladder.py`'s own docstring) are a closed, already-tested state machine with no notion of "retry the same rung." Extending it to support that would change what M2's own already-Accepted architecture means for *every* existing and future consumer of the ladder, not just the coding agent — the same "breaking change to the effect's documented meaning going forward" caution ADR-0038's own Consequences section names for a much smaller change.
2. **A new, minimal wrapper that calls the existing `Dispatcher` as a black box, one or more times, adding its own retry/feedback logic around it** — the working assumption's own choice. `application/coding/` (or similar), net-new orchestration, `Dispatcher`/`EscalationLadder`/`Arbiter`/`ReasoningPort` all reused completely unmodified underneath it.
3. **Reuse `Dispatcher` as-is with no wrapper at all**, treating "apply patch, run tests, escalate" as already fully covered by the existing three-rung ladder with no additional machinery. Rejected implicitly by the working assumption's own "run tests, feed failures back" language, which names a real feedback loop the existing `Dispatcher.run()` does not provide on its own beyond `prior_attempts`' own cross-rung role.

The working assumption chose option 2. This ADR records the real technical shape that choice implies, checked against the actual `Dispatcher`/`WorkspacePort`/`ValidationPort` interfaces, not just restates the assumption's own prose.

## Decision

A new, minimal orchestration module, `application/coding/loop.py` (or a small package, `application/coding/`, if the real implementation needs more than one file — not decided here), with roughly this real shape:

- Takes a coding task (a plain-text description, matching `ReasoningPort.generate`'s own `task: str` parameter shape) and a real `WorkspacePort` instance (matching `ValidationPort`'s own existing "each validator gets its own already-injected workspace" convention, ADR-0043).
- Calls the existing, unmodified `Dispatcher.run()` for one real escalation climb per coding attempt — `Dispatcher`/`EscalationLadder`/`Arbiter`/`ReasoningPort`/`ValidationPort` are reused completely as-is, no new parameter, no new method, no subclassing.
- If the winning `Attempt`'s own `Verdict` is `FAILED` (a candidate applied but a real validator — a test run, most plausibly `PytestValidator`, already real per M2's own deliverable #3 — reported failure) and a real, bounded retry budget for *this coding task specifically* has not been exhausted, the wrapper constructs a **new** `Dispatcher.run()` call, seeding its own `prior_attempts`/task framing with the failure just observed — a second, wrapper-level escalation climb, not a continuation of the first `Dispatcher.run()` call's own internal state (which has already terminated, per `EscalationLadder`'s own bounded-and-monotonic invariants).
- The wrapper's own retry budget is real, separate domain vocabulary from `TaskBudget` (`domain/reasoning.py`) — `TaskBudget`'s own docstring already states "one unit is one rung climbed" (`dispatcher.py`'s own decision) is specific to *within* one `Dispatcher.run()` call; a coding task's own "how many full `Dispatcher.run()` climbs may this task attempt before giving up" is a different, wrapper-level concept, real and undecided in its exact shape (a new domain type, a plain integer parameter, something else) — left to whichever work package first implements this wrapper, not fixed here.
- Every real file write the wrapper causes (via `WorkspacePort.apply_patch`, once per accepted, granted candidate) is authorized through `code_write_effect_for`/`Effect.CODE_WRITE`/`Effect.PROTECTED_PATH_WRITE` (ADR-0056) before `apply_patch` is ever called — the same "classify, then authorize, then act only if granted" shape every other real capability in this repo already follows, applied here for a coding-agent write specifically.

**No new domain vocabulary for scoring/evidence** — `Attempt`/`Candidate`/`Evidence`/`Verdict`/`EscalationRung` (`domain/evidence.py`) are reused completely unmodified. A coding task's own multiple `Dispatcher.run()` climbs each still produce ordinary `Attempt`s in the ordinary shape; the wrapper's own real, new concept is *when to call `Dispatcher.run()` again*, not a new kind of evidence or a new kind of candidate.

## Consequences

`application/reasoning/`'s own 100%-branch-coverage gate (ADR-0041) and its existing acceptance criteria are entirely unaffected — no file under that package changes for this milestone. The coding-loop wrapper is new, additional application-layer code, subject to this project's ordinary coverage discipline (not the `application/reasoning`-specific 100% gate, unless a future decision extends that gate to `application/coding/` too — not decided here, real, deferred question for whichever work package first builds this).

**Real, deliberately open question this ADR does not resolve, named rather than silently deferred**: the exact shape of the wrapper's own retry budget (how many full `Dispatcher.run()` climbs a coding task gets, what happens when that budget is exhausted with no `PASSED` verdict — the same "partial results, never silently discarded" discipline `DispatchResult`'s own docstring already requires at the `Dispatcher` level, presumably inherited at the wrapper level too, but not fixed here) is real, necessary design work for the implementing work package, not invented speculatively in this ADR.

**Real, deliberately open question this ADR does not resolve either, inherited directly from `m5-scoping-notes.md`'s own Part 1, item 3**: whether "one candidate = one patch per `Dispatcher.run()` call, with the wrapper re-calling `Dispatcher.run()` on failure" is itself sufficient for real coding-agent work, or whether a genuine coding agent needs iterative, multi-turn editing *inside* what is today one `generate()` call (a provider reading/editing/re-reading files across several exchanges before returning one final patch) — a structurally different, deeper change to `ReasoningPort`'s own contract this ADR does not attempt, and the working assumption itself does not address. This ADR's own decision (a wrapper that retries whole `Dispatcher.run()` climbs) is compatible with either answer eventually — if the deeper, `ReasoningPort`-level change is ever needed, it would be a separate, later ADR, not something this one either builds or forecloses.

**Depends on ADR-0056** for how the wrapper's own file writes are authorized — this ADR does not itself decide the authorization mechanism, only the orchestration shape around it.
