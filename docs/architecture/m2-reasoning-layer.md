# JARVIS — M2: Multi-Model Reasoning Layer

**Status: recovered from the original approved design conversation,
NOT yet re-validated against what M0 actually became.** This document
was genuinely designed and approved before implementation started, but
the source file was never persisted into this repository — confirmed
absent by a full-tree search on 2026-08-18 (see `docs/architecture/README.md`
and `docs/ROADMAP.md`'s M2 row). What follows is reconstructed from
recovered fragments of that original conversation, not invented.

**This reconciliation is explicitly incomplete.** Checking this content
against what M0 actually built — real port shapes, the real policy
engine, the real capability/registry model, real ADR numbers where they
apply — is separate, upcoming work (a WP-28 planning pass), not done
here. Where the recovered fragments already reference old-scheme
two-digit ADR numbers, none are carried forward, because none of them
match this repo's real four-digit ADR scheme. Nothing below should be
treated as more settled than "designed once, not yet checked against
reality," except where explicitly noted otherwise.

**Entry gate:** M1. **Exit gate, complexity, and risks:** not part of
the recovered fragments; not stated here rather than invented.

---

## 1. Summary judgement

The original design conversation's own verdict on the initial M2
spec, recovered verbatim:

> "Your spec contains one genuinely load-bearing correct idea, one
> design choice that the research literature specifically vindicates,
> and four mechanisms that will burn tokens without improving
> outcomes."

**Keep**: validation-over-agreement; the generate → validate → repair
loop; cross-vendor heterogeneity; "neither model is the permanent
authority."

**Cut or restructure**: confidence-score thresholds; multi-round
cross-review ping-pong; merging implementations; the learning system
(for now); the assumption that one loop fits all task categories.

## 2. Core principle: validation over agreement

> "Passing validation is stronger evidence than agreement between
> models... Two models agreeing is weak evidence, because their errors
> are correlated — similar training data, similar architectures,
> similar failure modes. A passing test suite is ground truth about
> behaviour. The architecture should make it structurally impossible
> to confuse the two."

This is the single load-bearing idea the summary judgement names. It
is consistent with `CLAUDE.md`'s already-committed architecture
summary ("Passing validation (build/test/lint/execution) is always
stronger evidence than model agreement") and with real, already-decided
ADRs from M0's own reasoning-adjacent principles (ADR-0022 through
ADR-0025) — those exist and are accepted today, even though the
detailed M2 architecture that would implement them does not yet.

## 3. Cross-vendor heterogeneity: checked, not assumed

The claim that using genuinely different model families (not just
different prompts to the same family) reduces correlated error was
"checked against actual multi-agent-debate and LLM-calibration
research before being written up as a design principle, not assumed
from intuition." The original design session's own framing, recovered
directly: this was flagged as *"exactly the kind of intuitive-sounding
idea that often fails to replicate,"* and was checked rather than
trusted before being kept.

Stated honestly: this document cannot verify or reproduce that
literature check — no specific papers or citations survive in the
recovered fragments, and none are invented here. What is recorded is
that the claim was treated as needing evidence, not granted by
default, in the original design process. Re-verifying it (or citing
real sources) is part of the M2 reconciliation pass, not resolved by
this document.

## 4. Cost model — worked example

Task: *"Fix the failing test in my ROS2 package,"* root cause a
missing `package.xml` dependency.

**As originally spec'd** (before revision): 7 model calls across two
vendors — generate, validate-fail, other-vendor-review, other-vendor-generates-alternative,
first-vendor-reviews-feedback, planner-merges, re-validate-with-mutual-critique
— ending in a **merged** output that neither model itself validated.

**Revised ladder**: rung 0 (deterministic — the build output already
names the missing dependency) fails to resolve the issue alone; rung 1
(self-repair, the error appended to context) succeeds. **Total: 1
call, ~3 seconds, validated.** Rungs 2–5 never execute for this class
of task.

| | Calls | Result validated? | Rungs used |
|---|---|---|---|
| Original spec | 7 | No — merged, unvalidated | all |
| Revised ladder | 1 | Yes | rung 1 of 5 |

This worked example is the concrete justification for "select, never
merge" (matches real ADR-0023, "Select, never merge: the arbiter picks
one candidate unmodified") and for trying cheap deterministic fixes
before escalating (matches real ADR-0022, "Escalation ladder:
deterministic fixes, then self-repair, before a second provider").
Both of those ADRs are already real and accepted in this repo, from
M0 — this worked example is the reasoning that produced them, recovered
after the fact, not new content justifying something not yet decided.

## 5. Scope: deliverables

Recovered from the original implementation roadmap's M2 entry, listed
in full, not summarized:

1. `ReasoningPort` + `ProviderProfile` + adapters (two cloud provider
   families, one local) + shared contract test suite
2. `Evidence` / `EvidenceKind` domain types with weighting
3. `ValidationPort` + validators: build, unit, integration, static,
   runtime, user script
4. `EscalationLadder` — pure state machine, five stated invariants
5. `Arbiter` — selection only, author-exclusion rule (never merges
   implementations)
6. `TaskBudget` + enforcement at the dispatcher
7. Unverifiable-task regime: parallel heterogeneous drafting + user
   selection UI (escalation OFF by default here)
8. Classification-gated rung availability (reuses the M0 policy
   engine)
9. Test-file protection in the coding agent's resource scope
10. Record/replay cassette harness (also functions as a regression
    corpus — replay every historical task when ladder logic changes)
11. Structured outcome logging for future analysis — explicitly **no**
    adaptation/learning in M2 itself

## 6. Acceptance criteria

Recovered fragments name at least these 8. This document does not
assert these are the complete, final set — only that no more than
these 8 survived recovery, and none are invented to round the list out:

1. Ladder invariants hold under property-based testing over arbitrary
   evidence and budgets
2. Arbiter output is byte-identical to one input candidate, always —
   property test
3. A test authored by provider X contributes zero weight when scoring
   X's own candidate — unit test
4. `MODEL_OPINION` evidence can never change a selection — property
   test
5. Budget exhaustion terminates and surfaces partial results, never
   silently continues
6. A `SENSITIVE`-classified task never reaches a cloud provider at any
   rung, including escalation (reuses M0 policy tests)
7. Full ladder replays deterministically from cassettes with the
   network disabled
8. Escalation is OFF by default for unverifiable tasks — asserted by
   test, not just documented

## 7. Package/class layout (recovered, not yet reconciled)

From the original implementation roadmap's M2 entry, recorded as-is —
**not checked against real M0 package conventions yet**, which is
exactly the kind of reconciliation this document defers to the WP-28
planning pass:

```
domain/evidence.py          - EscalationRung, Evidence, EvidenceKind, Verdict, Candidate, Attempt
ports/validation.py         - ValidationPort
application/reasoning/      - ladder, arbiter, router, classification
adapters/reasoning/         - family_a, family_b, local
adapters/validation/        - build, pytest, static, runtime, user_script
tests/cassettes/
```

Key classes: `EscalationLadder` (pure state machine) — `Arbiter`
(selection only) — `ModelRouter` (classification-gated) —
`ProviderProfile` — `CassetteRecorder`/`CassettePlayer` —
`OutcomeLogger` (instrumentation only, no adaptation).

Acceptance also includes a structural check already in the spirit of
this project's real, existing meta-tests (`tests/meta/`, which do
exactly this kind of AST/grep-based structural enforcement elsewhere
in the real codebase today): `git grep -iE "openai|anthropic|chatgpt|claude"
src/jarvis/application/` must be empty — vendor names must never leak
into the application layer. This matches real, already-accepted
ADR-0021 ("No vendor names in domain, application, or ports") exactly,
and this repo already has a real, working pattern for this class of
check (`tests/meta/test_source_invariants.py` and friends) that a real
M2 implementation should reuse the *pattern* of, not necessarily the
literal grep command above.

## 8. Deferred, from the original design conversation itself

Recovered directly, and cited here because it supports this project's
own already-adopted rolling-wave principle (see `docs/ROADMAP.md`) —
this is the *original* design conversation independently reaching the
same conclusion this repo's M3–M6 stub files already reflect, not this
document inventing new justification for them:

> "Individual agent capability sets (M5+). Designing the Email Agent's
> capabilities before the plugin ABI has survived three real plugins
> would be designing against an untested interface."
>
> "Console UI views. Interface frozen; views deliberately not. You
> will know what you want after six months of using the HUD."
>
> "Cross-device sync: genuinely hard — conflict resolution, key
> distribution, trust between instances. Worth its own document, much
> later."
