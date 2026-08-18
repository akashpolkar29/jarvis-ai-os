# ADR-0043: WorkspacePort -- materializing a Candidate for real validators

## Status

Accepted

## Date

2026-08-18

## Source

Work package WP-33 implementation finding (build/pytest/static/runtime validators need a real working directory, not just a string, to check a Candidate against)

## Context

`Candidate.content` is a plain `str` -- "a patch, a diff, a plain-text answer" per its own domain docstring (WP-30), deliberately generic. `ValidationPort.validate(candidate)` (WP-31) says nothing about how that string becomes something a real build, test run, or static analyzer can actually act on. A build or a `pytest` run needs a real directory full of real files, not one bare string. Nothing in this repo has ever needed to write files before: `FileSystemPort` only has `read_text` (WP-9's own scoping: "only what the real caller needs"), and `m2-reasoning-layer.md` is silent on this entirely -- it names validator *kinds* (deliverable #3) but never how a Candidate reaches one.

Flagged during WP-33, before any validator adapter was written, per CLAUDE.md's hard rule. Three options were put to the user: (1) treat `Candidate.content` as one complete file for this pass, no new port; (2) a new `WorkspacePort`, validators applying the candidate into a real, already-checked-out directory; (3) change `ValidationPort.validate()`'s already-committed WP-31 signature to take an explicit `workspace` argument. The user chose (2).

## Decision

Add `jarvis.ports.workspace.WorkspacePort`, a two-method `Protocol`:

```python
def root(self) -> Path: ...
def apply_patch(self, patch: str) -> None: ...
```

Method-only, matching every other port in this repo (no `@property`, same reasoning as `ReasoningPort`'s rejection of a `profile` property in WP-31: no precedent for a data attribute on a Protocol here). `Candidate.content` is treated as unified-diff text for any validator backed by a real workspace -- the most standard, well-defined shape for "content that changes files in a directory," and the shape real coding-agent output naturally takes (matches the worked example in `m2-reasoning-layer.md` section 4: fixing a failing test in an existing package, not authoring one from scratch). `PatchApplicationFailedError` is defined on the port module, raised when `patch` does not apply cleanly, mirroring `NoMediaPlayerRunningError`'s "defined on the port, not the adapter" reasoning.

`jarvis.adapters.workspace.LocalWorkspaceAdapter` implements it for real via `git apply`, run as a subprocess against a real directory given at construction. Verified live during WP-33 (not merely assumed from documentation): `git apply` accepts a real unified diff against a plain directory that is **not** a git repository at all -- confirmed by generating a real patch in one git-initialized temp directory and applying it to a second, non-git temp directory with only the pre-patch file copied in. No workspace-must-be-a-git-repo requirement follows from this choice; `git` itself is the only real dependency, and it is a reasonable one for a coding-agent validation layer to assume is present.

Each validator adapter (`adapters/validation/*.py`) is constructed against its own `WorkspacePort` instance and calls `apply_patch(candidate.content)` itself, as the first step of `validate()`, before running its real check. This is why `ValidationPort.validate(candidate)`'s existing signature did not need to change (the user's option 2, not option 3): `candidate` is not vestigial -- each validator genuinely materializes it, using its own already-injected workspace, rather than trusting some upstream caller already did so. Multiple validators judging the same `Candidate` in the same escalation rung each need their own separate `WorkspacePort` instance (typically a fresh copy of some base checkout); how that copy gets made, and how many validators run per rung, is the dispatcher's problem (WP-37), not this ADR's or this port's.

A patch that does not apply cleanly is not the same failure as code that applies but fails its check: `apply_patch` raising is caught by each validator and reported as `Verdict.UNVERIFIABLE` with `Evidence` describing the patch failure -- "no way to judge this candidate at all" is exactly `UNVERIFIABLE`'s own documented meaning (domain/evidence.py, WP-30), not a stand-in for `FAILED`.

## Consequences

Every validator built in WP-33 depends on a real, already-prepared working directory, which nothing in M2 constructs yet -- WP-37's dispatcher (or whatever first calls a real validator in anger) is responsible for producing one (checking out a base revision, copying it per validator instance) before constructing a validator against it. This is real, deferred work, not silently assumed solved here.

`WorkspacePort` is reusable beyond M2 validation specifically -- any future capability needing "a real directory to apply changes to and inspect" can depend on it, the same way `FileSystemPort` and `SecretPort` (ADR-0042) are not scoped to the one feature that motivated them.

**Deliberately not done here**: multi-strategy patch application (falling back to `patch -p1`, 3-way merge, or fuzzy matching when `git apply` rejects a patch outright), and any workspace lifecycle management (checkout, cleanup, isolation between concurrent validators). Both are real gaps if they become load-bearing; tracked as follow-up, not built speculatively against a scenario this WP does not need.
