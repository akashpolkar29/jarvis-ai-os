# Charter-conformance audit (10-phase combined pass, Phase 6)

## Status

Real, evidence-based audit -- every claim below was checked directly
against the current codebase (grep, direct file reads, real test
runs), not carried forward from a prior report's own wording. Date:
2026-09-05.

## Scope

This pass's own instruction named one specific thing to check
("specifically checking speaker verification") inside a broader
"rigorous, evidence-based charter-conformance audit." Speaker
verification got the deepest treatment below; the rest of CLAUDE.md's
own "Core principles" section (the closest thing this repo has to a
single, current, in-repo charter -- the original founding charter text
itself is not fully reproduced verbatim anywhere in-repo, only quoted
in fragments across ADRs/ROADMAP.md) got a real, direct, but
necessarily narrower spot-check, prioritizing principles not already
independently re-verified very recently.

**Hard scope boundary honored**: this pass builds nothing. Speaker
verification specifically was confirmed conforming, not built further,
per this prompt's own explicit instruction not to build it even if a
gap were found (none was).

## 1. Speaker verification (ADR-0012/ADR-0034) -- the named focus

**Claim being checked**: "Voice/speaker verification is a convenience
filter, never an authorization boundary... Physical interaction with
the machine is the real auth boundary" (CLAUDE.md's own principle).

**Real evidence, checked directly, not assumed:**

1. `src/jarvis/adapters/speaker_id.py` -- read in full.
   `UnverifiedSpeakerIdAdapter.score()` still, today, unconditionally
   returns `SpeakerScore(verified=False, confidence=0.0)`, ignoring its
   `audio` argument entirely. No real speaker-embedding model exists
   anywhere in this codebase. Unchanged since WP-23 (M1).
2. `tests/meta/test_speaker_id_isolation.py` run directly:
   `test_policy_context_has_no_speaker_related_field`,
   `test_no_module_under_src_references_both_policy_context_and_speaker_id`,
   `test_the_scan_predicate_actually_detects_a_violation`,
   `test_the_scan_predicate_does_not_fire_on_policy_only_code`,
   `test_the_scan_predicate_does_not_fire_on_speaker_id_only_code`,
   `test_the_scan_predicate_ignores_docstrings_that_merely_discuss_the_guarantee`
   -- all six pass. Critically, the predicate is proven to actually
   fire against a deliberately-crafted violation, not merely to find
   today's tree clean by coincidence.
3. **Independent, redundant check, not relying on the meta-test
   alone**: `grep -rn "PolicyContext(" src/jarvis/` finds exactly one
   real construction site in the entire codebase --
   `adapters/confirmation.py::ManualConfirmationAdapter.get_context()`
   -- built purely from two constructor-supplied booleans that trace
   back to a CLI flag or `Gtk4PhysicalConfirmationAdapter`'s real
   keypress/click. `grep`ing that adapter and `ui/confirm/dialog.py`
   for `speaker`/`score`/`verified` finds zero matches.
4. `kernel/voice_loop.py`: `speaker_id.score()` is called exactly once
   per utterance, its result used only in one `_logger.info(...)` call
   (line 479-481) -- never read again, never passed to anything that
   constructs a `PolicyContext`.

**Verdict: conforms, fully, with real mechanical enforcement, not just
documentation.** No drift found since ADR-0034 was written in M1,
across five subsequent milestones' worth of new code.

## 2. Spot-checked, remaining "Core principles" (CLAUDE.md)

Each checked with fresh, direct evidence this pass, not by re-reading
a prior claim:

- **"Nothing in domain/application/ports names a specific
  integration... no vendor names"**: `grep -rniE
  "openai|anthropic|chatgpt|claude|\bgpt\b" src/jarvis/{domain,application,ports}/`
  returns zero matches. Conforms.
- **"A single Policy Engine evaluates effects against a Tier at one
  choke point"**: every one of the 36 real `authorize_and_*`/
  `authorize_*` composition functions in `src/jarvis/kernel/*.py` makes
  exactly one `orchestrator.authorize(...)`/`.authorize_by_id(...)`
  call -- confirmed by counting both (36 functions, 36 call sites, a
  real 1:1 correspondence, not merely "most of them"). No capability
  action is performed without going through the orchestrator first.
- **"Audio is never persisted to disk, ever, unless an explicit
  temporary debug mode is enabled"**: grepped
  `adapters/`/`application/`/`kernel/` for any audio/segment/chunk
  write path -- none found. A real finding, stated precisely: no
  "temporary debug mode" audio-persistence mechanism exists anywhere
  in this codebase either, so that clause's carve-out has nothing to
  check -- audio is unconditionally never persisted today, a stronger
  guarantee than the charter's own conditional wording requires, not a
  gap.
- **"SECRET data... is DENY to any cloud provider, always"**:
  `application/reasoning/classification.py` maps
  `Classification.SECRET` to `Effect.EGRESS_SECRET`
  (`domain/capability.py::_EFFECT_TIER_FLOOR` floors this at
  `Tier.DENY`, unconditionally). Confirmed directly in the source, not
  assumed from the earlier M2 gate description.

## 3. Previously-named charter fragments -- status re-confirmed, not re-litigated

These were already investigated in dedicated passes; this audit
re-confirms each is still accurately described where currently
documented, rather than re-doing the investigation:

- **"Intelligent task planning"**: `docs/architecture/m7-scoping-notes.md`
  (2026-09-04) already found the "maps to `Dispatcher`/
  `EscalationLadder`" claim is not a full capability match (no real
  goal decomposition into a multi-step, cross-capability plan exists).
  Confirmed this finding is still accurate: `application/reasoning/ladder.py`
  is unchanged since that investigation.
- **Email/calendar confirmation tier (ADR-0059)**: confirmed
  `Tier.MANUAL_ONLY` for `communications.send_email`/attendee-bearing
  `create_calendar_event` still holds in
  `application/communications/classification.py` -- matches
  CLAUDE.md's own current claim.

## 4. Real drift found, deliberately NOT fixed here (scope discipline)

**`README.md` is severely stale** -- still describes Milestone-0-only
state ("pre-alpha, Milestone 0 complete... two real capability
families... no dynamic plugin loading, no IPC transport, no real
physical-presence detection yet"), while the real, current state is
M0 through M6 code-complete, `v0.6.0` tagged, 36 statically-registered
capabilities, a real `Gtk4PhysicalConfirmationAdapter` for physical
presence, and dozens of features README.md never mentions. A real,
significant, directly-confirmed finding (`wc -l README.md`: 129 lines,
last meaningfully describing work packages 1-16).

**Deliberately not fixed in this pass**: the already-queued, separate
"5 mixed real tasks" prompt explicitly names "README accuracy audit"
as its own first task, scoped to start only after this 10-phase
prompt's own final cumulative summary. Fixing it here would duplicate
that task and violate this project's own hard rule against doing
future work packages "while you're at it." Flagged here, with full
evidence, for that later pass to act on.

## Conclusion

Speaker verification -- the one item this phase specifically named --
conforms fully, with real, mechanically-enforced isolation, unchanged
across five milestones of subsequent development. The broader
principle spot-check found no other real gap. One real, significant
drift was found (README.md) and deliberately left for the pass already
scoped to fix it, rather than absorbed here.
