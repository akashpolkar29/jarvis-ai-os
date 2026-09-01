# ADR-0056: `Effect.CODE_WRITE`, and an unconditional DENY for protected test paths

## Status

Proposed

**Not yet reviewed by the user in conversation** — drafted from a remotely-reasoned working assumption (`m5-browser-coding.md`'s own header explains the distinction from M4's ADRs, all of which the user confirmed directly). Do not mark Accepted without the user's own direct review of this ADR specifically — see this ADR's own "A real technical correction made while drafting" section below for why that review matters more than usual here.

**Amended 2026-09-01, still Proposed:** two real Consequences added before WP-70's own implementation — a fail-closed default for target repositories whose own test convention this ADR's original Python/pytest-specific defaults cannot detect, and a diff-path-parsing robustness requirement (canonicalization, created-file handling). Neither amendment changes this ADR's own core Decision (`Effect.CODE_WRITE`/`Effect.PROTECTED_PATH_WRITE`, the unconditional DENY floor, or `code_write_effect_for`'s own signature/logic) — see each amendment's own text below for what it actually adds. Still requires the user's own direct review before Accepted.

## Date

2026-08-31 (amended 2026-09-01)

## Source

M5 scoping answer 4 and 5 (relayed to this pass as fixed working assumptions, not confirmed in conversation the way M4's five answers were — see `m5-browser-coding.md`'s own header): *"a new `Effect.CODE_WRITE`, floored at `Tier.CONFIRM` by default for ordinary file writes"* and *"any write path matching a real, configurable 'protected test path' pattern... gets an unconditional `Tier.DENY` floor on `Effect.CODE_WRITE`, no confirmation override, mirroring ADR-0038/ADR-0049's precedent."*

## Context

Checked directly against `domain/capability.py`, not assumed: `_EFFECT_TIER_FLOOR` is a `dict[Effect, Tier]` — **one fixed tier floor per `Effect` member, global across every invocation that declares it.** There is no mechanism anywhere in this table, in `minimum_tier_for()`, or in `CapabilityInvocation.effective_tier` by which the *same* `Effect` value floors at two different tiers depending on which specific argument (e.g. which file path) a given invocation carries.

### A real technical correction made while drafting, not silently smoothed over

The working assumption as given — "an unconditional `Tier.DENY` floor on `Effect.CODE_WRITE`" for protected-path writes specifically, while ordinary writes on the same effect float at `Tier.CONFIRM` — is not directly buildable against the real `_EFFECT_TIER_FLOOR` table: a single dict key cannot hold two different values. Read literally, it would either deny *every* `CODE_WRITE` unconditionally (defeating "ordinary file writes" at `CONFIRM`) or deny none (defeating the protected-path guarantee) — whichever floor got written into the table would win for all invocations, protected path or not.

This is the exact same shape of gap ADR-0049's own Context section names for `Effect.MEMORY_WRITE` and `Classification.SECRET`: *"There is no existing generic mechanism by which a SECRET-classified argument automatically escalates a capability's tier."* ADR-0049 resolved it by adding a **second, distinct effect** (`Effect.MEMORY_WRITE`, `DENY`-floored) alongside the ordinary one (`Effect.WRITE_LOCAL`, `CONFIRM`-floored), with a real, per-invocation classification function (`application/memory/classification.py`'s `memory_effect_for`) choosing which effect a given write declares, called at dispatch time before `AuthorizationOrchestrator` ever evaluates the call.

**Decision, made in this drafting pass, following that precedent rather than inventing a new one**: this ADR adds a **second** effect, `Effect.PROTECTED_PATH_WRITE`, distinct from `Effect.CODE_WRITE`. A real classification function, `code_write_effect_for`, inspects the specific target path a coding-agent write is about to touch and returns whichever effect applies — mirroring `memory_effect_for`'s exact shape, one file-write path at a time, not a batch decision over an entire patch. This is a real, necessary technical resolution of the working assumption as given, not a reinterpretation of its intent: "ordinary writes at CONFIRM, protected-test-path writes at an unconditional DENY" is exactly what results, just implemented the only way this codebase's existing `Effect`/`Tier` mechanism can actually express it. **Flagged here explicitly for the user's own review**: if the user's own intent differs from this resolution once they see it stated precisely, this is the one section of this ADR most likely to need revisiting.

### What "protected test path" means, checked against this project's own real convention, not assumed

`pyproject.toml`'s `[tool.pytest.ini_options]` sets `testpaths = ["tests"]` and does not override `python_files` — meaning pytest's own built-in default file-discovery pattern applies unmodified: `test_*.py` and `*_test.py`. Checked directly against every real test file in this repository (140 `.py` files under `tests/`, confirmed by direct enumeration): **123 use the `test_*.py` prefix; zero use the `*_test.py` suffix.** This repository's own real, lived convention is narrower than pytest's own generic default — `test_*.py` only, plus the entire `tests/` directory itself as a real, configured discovery root (`testpaths`).

A real coding-agent capability operates against an arbitrary target repository (`WorkspacePort.root()` returns "this workspace's real filesystem root," not a path hardcoded to this repository) — not necessarily this one. A default drawn only from this repository's own narrower practice (`test_*.py` only) would silently fail to protect a target repository using the wider, still-genuinely-common `*_test.py` convention pytest itself recognizes. This ADR's own default therefore includes both forms, matching pytest's real, documented default exactly, while stating plainly that this repository's own practice (checked directly, not assumed) uses only one of the two.

## Decision

Two new `Effect` flag members, added to `domain/capability.py`'s `Effect` enum:

```python
Effect.CODE_WRITE
Effect.PROTECTED_PATH_WRITE
```

Two new `_EFFECT_TIER_FLOOR` entries:

```python
Effect.CODE_WRITE: Tier.CONFIRM,
Effect.PROTECTED_PATH_WRITE: Tier.DENY,
```

A new, real function, `application/coding/classification.py`'s `code_write_effect_for`, directly mirroring `memory_effect_for`'s own shape and calling convention:

```python
def code_write_effect_for(path: Path, protected_patterns: tuple[str, ...]) -> Effect:
    """Return the Effect a coding-agent file-write CapabilityInvocation must declare for `path`.

    Effect.PROTECTED_PATH_WRITE (floors Tier.DENY) if `path` matches any
    of `protected_patterns` (fnmatch-style glob, matching this
    project's own already-established `git`/patch-adjacent tooling
    conventions rather than inventing a new pattern language) --
    unconditional, no confirmation overrides it, matching
    ADR-0038/ADR-0049's own precedent for "this class of write is
    never allowed, full stop." Effect.CODE_WRITE (floors Tier.CONFIRM)
    for every other path -- ordinary coding-agent writes, gated the
    same way any other local write already is, not specially
    restricted beyond that by this ADR.
    """
    if any(fnmatch(str(path), pattern) for pattern in protected_patterns):
        return Effect.PROTECTED_PATH_WRITE
    return Effect.CODE_WRITE
```

**Real default for `protected_patterns`**, drawn from this project's own checked-directly convention (see Context above), not invented: `("test_*.py", "*_test.py", "tests/*")` — the first two matching pytest's own real, built-in discovery default exactly; the third matching this repository's own real, configured `testpaths` root, generalized as a directory-prefix pattern for an arbitrary target repository. **Configurable, not hardcoded**: a real coding-agent invocation must be able to override this default with whatever convention the actual target repository uses (its own `pyproject.toml`/`pytest.ini`/`setup.cfg` may configure `python_files` differently, or use a non-pytest test runner entirely) — the exact configuration mechanism (a parameter threaded through the coding-loop wrapper from ADR-0055, a per-repository config file, something else) is real, undecided implementation detail for whichever work package first builds `code_write_effect_for`'s real caller, not fixed by this ADR.

Called by the coding-loop wrapper (ADR-0055) at dispatch time, once per file a candidate's patch would touch, before `AuthorizationOrchestrator.authorize_by_id()` runs for that specific write — the same point in the flow `memory_effect_for`/`egress_effect_for` are already called, not a new architectural position invented for this case. **A patch touching multiple files, at least one of which is protected, must not be split into "the allowed files get written, the protected one doesn't"** — silently applying part of a patch while rejecting the rest is a different, worse failure mode than rejecting the whole candidate outright (a partially-applied patch can leave a workspace in a state no single `Candidate` ever actually described). This ADR requires the coding-loop wrapper to classify every touched path *before* calling `WorkspacePort.apply_patch` at all, and treat any single `PROTECTED_PATH_WRITE` classification among them as grounds to deny the whole write — the real mechanics of extracting "which paths does this patch touch" from a unified diff are real, undecided implementation detail for ADR-0055's own work package, not fixed here.

**No exception path, matching ADR-0038/ADR-0049's own established rule exactly**: `Tier.DENY` is already, unconditionally, an absolute ceiling in `domain/policy.py`'s `evaluate()` — no confirmation, physical or remote, reads either confirmation flag at that tier. This ADR adds no new logic to `evaluate()` itself; `Effect.PROTECTED_PATH_WRITE`'s own floor is sufficient, the same one-entry-table mechanism ADR-0038/ADR-0049 both used.

## Consequences

Any capability declaring `Effect.PROTECTED_PATH_WRITE` floors at an unconditional `DENY` — today, that would mean exactly the real coding-agent write capability this milestone would register, but the effect itself is general enough that a future capability could declare it too, the same way `Effect.EGRESS_SECRET`/`Effect.MEMORY_WRITE` are not hardcoded to their own originating milestone's adapters.

**Required test, mirroring ADR-0038/ADR-0049's own acceptance-criterion shape exactly**: a property/regression test asserting a write to any path matching the real default `protected_patterns` never reaches a real workspace at any rung, under any circumstance — including `physical_confirmation_available=True` — the same standard already applied to cloud egress (ADR-0038) and memory writes (ADR-0049), applied here for the third time, to a *scoped subset of local writes* rather than an entire capability.

**Required acceptance criterion, mirroring ADR-0049's own "single-path guarantee" exactly, not yet structurally enforced by this ADR alone**: everything above assumes the coding-loop wrapper is the *only* code path that ever reaches `WorkspacePort.apply_patch` for a coding-agent-authored patch, and that it always calls `code_write_effect_for` for every touched path before `AuthorizationOrchestrator.authorize_by_id()` runs. As drafted, that is true by convention only. Mirroring ADR-0049's own resolution (an AST-based meta-test, not a new import-linter contract, following `tests/meta/test_no_response_scraping.py`'s precedent): a real, required meta-test must scan every module under `src/jarvis` except the coding-loop wrapper's own defining module for any direct reference to `WorkspacePort.apply_patch` (or the real adapter's own concrete `apply_patch` implementation), proving no other code path can reach it unclassified. `tests/` itself is excluded, matching ADR-0049's own precedent — a unit test constructing `WorkspacePort` directly to test it in isolation is the established pattern (`WorkspacePort`'s own existing contract tests already do this), not a violation.

**Real, deliberately narrow scope of this ADR, matching ADR-0049's own stated-limits discipline**: it governs write-time classification only. It does not decide how "which paths does this patch touch" is actually extracted from unified-diff text (a real, separate parsing concern for ADR-0055's own implementing work package), does not decide the real configuration mechanism by which a target repository's own different test-discovery convention overrides the default `protected_patterns` (named above as real, undecided implementation detail), and does not address `SandboxPort`-level containment of whatever a validator's own command execution can do once a candidate is applied — `docs/threat-model/v0.md`'s own "candidate execution is not sandboxed" gap (confirmed, in `m5-scoping-notes.md`'s own Part 1 item 5 research, as still real and still open through M2's own WP-32–WP-40) is a real, separate, broader concern this ADR narrows for the specific case of protected test paths but does not close in general.

**A second, explicit limit, named rather than left implicit, mirroring ADR-0049's own equivalent section**: this ADR's DENY guarantee is only as good as `protected_patterns`' own real, configured contents for whatever target repository a coding-agent invocation is actually running against. A protected-path convention the coding-loop wrapper is never told about (a target repository using an unconventional test-file layout, with no override supplied) is a real, structural blind spot this ADR cannot close by construction — the same "trusts its own input" limitation ADR-0049's own Consequences section already states plainly for `Classification`, restated here for path-pattern configuration instead.

**Amendment 1 (2026-09-01) — the "second, explicit limit" above is worse than originally stated, and needed a real fix, not just a caveat**: the default `protected_patterns` (`test_*.py`, `*_test.py`, `tests/*`) are Python/pytest-specific, but a real coding-agent invocation targets an arbitrary repository — most of which will not be Python/pytest projects at all. A target repository using Go's `*_test.go`, JavaScript's `*.test.js`, Ruby's `*_spec.rb`, or a `__tests__/`/`spec/` directory convention would get *zero* real test-file protection under the original defaults — the DENY floor would silently never fire, while every real observer (the user, a future coding-loop wrapper's own logs) would have no reason to believe anything was wrong. Unlike ADR-0049, where `Classification` comes from this project's own existing, consistently-applied `Tainted[T]` system, nothing here ensured the right patterns got supplied for a repository this project has never seen before — a real, structural gap this ADR's own original text only named as a caveat, not fixed.

**Real fix, not just a stronger caveat: fail-closed on an unrecognized repository.** Before a coding-loop wrapper (ADR-0055) is allowed to write to any target repository, it must either (a) detect the repository's own real test convention and derive `protected_patterns` from it, or (b) if no recognized convention is detected, require an explicit, user-supplied `protected_patterns` configuration before any write is authorized at all — refusing to proceed with a real, clear error rather than silently defaulting to Python patterns that do not apply. This ADR does not decide detection logic in exhaustive detail — real, bounded detection work for the implementing work package, checked against real, documented signals rather than invented speculatively: Python/pytest (`pytest.ini`, `pyproject.toml`'s `[tool.pytest.ini_options]`, `setup.cfg`'s `[tool:pytest]`, `tox.ini`'s `[pytest]`), Go (a real `go.mod` — Go's own tooling, `go build`/`go test` themselves, treats `_test.go`-suffixed files specially, not just community style), Ruby/RSpec (a real `.rspec` file, or a `Gemfile` mentioning `rspec`), and JavaScript/TypeScript (`package.json` naming a known test framework — jest, vitest, mocha). Real, named, *not* detected by this bounded research, falling back to the fail-closed requirement instead of a guess: plain Python `unittest` with no pytest config, Java/Maven/Gradle, and Rust — whose own real test convention is largely *inline* `#[cfg(test)]` code a filename pattern cannot protect at all, a real limitation of pattern-based protection itself, not just a detection gap. **What this ADR does require, unconditionally**: no target repository is ever silently treated as "protected by default patterns that don't actually match its own convention" without the user knowing that is what is happening — the fail-closed refusal itself, not any specific detection heuristic, is the real, binding part of this amendment.

**Amendment 2 (2026-09-01) — diff-path-parsing robustness requirement.** Whatever parses "which paths does this patch touch" from a real diff (named above as real, undecided implementation detail for ADR-0055's own work package) must canonicalize paths (resolve `.`/`..`/symlinks) before checking them against `protected_patterns` — an uncanonicalized path (`src/../tests/test_widget.py`, or a symlink whose real target is a protected path) could otherwise fnmatch-compare against the wrong literal string and silently miss a real protected-path write. It must also classify a file being *created* (not just modified) by a patch identically to one being modified — a patch that creates a brand-new file at a protected-looking path is exactly as real a bypass risk as one that modifies an existing protected file, and this ADR's own guarantee must not have a "only pre-existing files are protected" loophole. Added as a required, explicit acceptance criterion in `m5-browser-coding.md`'s own acceptance criteria list, alongside the existing ones for this ADR — not decided here in implementation detail (the real diff-parsing mechanics remain ADR-0055's own work package's responsibility), but required as a real, binding constraint on whatever that mechanism turns out to be.
