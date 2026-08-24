# JARVIS AI OS

Privacy-first, plugin-based agent kernel for Linux. Pre-alpha. Milestone 0 complete (v0.1.1).

## Baseline
`docs/architecture/` and `docs/adr/` are approved and frozen. They are the source of truth, not this file. `m0-architecture.md`, `system-design.md`, and `m2-reasoning-layer.md` now exist (reconstructed 2026-08-18 from recovered fragments of the original design conversation and reconciled against the real repo — real ADRs, real code, real import-linter config). State plainly: these are reconciled reconstructions, not pristine originals; each documents its own gaps between what was decided and what was actually built. `m2-reasoning-layer.md` is recovered and was reconciled against what M0 became during the WP-28 planning pass (2026-08-18) — see that document's own status note and ADR-0038 through ADR-0043 for what the reconciliation actually decided; the recovered fragments themselves are not rewritten, deviations are recorded in the real ADRs and in `docs/threat-model/v0.md`'s "Milestone 2 additions" section instead. `m1-voice-architecture.md` is current and was kept in sync with implementation. `m3-desktop-control.md` is a real design (written 2026-08-21, not recovered from anything — no original fragments for M3 were ever found) and has now been implemented (WP-43 through WP-55); ADR-0044 through ADR-0046 record its own real, pre-implementation decisions (SandboxPort/bwrap, the Claude/ChatGPT ordinary-control boundary, Terminal's narrow no-shell exception). `m4-memory-retrieval.md`, `m5-browser-coding.md`, and `m6-integrations.md` remain intentional gate-only placeholders per this project's rolling-wave planning principle (see `docs/ROADMAP.md`) — do not add ports, adapters, work-package breakdowns, or ADRs to them until each milestone actually starts. `docs/ROADMAP.md` is the real roadmap; a bare `roadmap.md` file does not exist.

## Current Status
M0 complete, tagged v0.1.1. M1 (voice) is code-complete, tagged v0.2.0 — all 7 gates pass, CI green — see `docs/architecture/m1-voice-architecture.md`. Live end-to-end voice verification is still an open item (tracker #19): the bug is isolated to the capture code's own audio path, not the OS/PipeWire layer. M2 (reasoning layer) is code-complete (WP-31 through WP-40; WP-41 deferred to M5 by design) — all gates pass including the `application/reasoning` 100%-branch-coverage gate (ADR-0041) — see `docs/architecture/m2-reasoning-layer.md` and `docs/threat-model/v0.md`'s "Milestone 2 additions" for what was actually built and the real, explicitly-accepted gaps (candidate execution is not sandboxed; cloud-provider adapters and the local-model adapter are code-complete but only partially live-verified against a real provider). M3 (desktop control) is code-complete (WP-43 through WP-55) — all gates pass, all eight target applications (Spotify, Brave, VS Code, Terminal, Docker, Git, the Claude desktop app, the ChatGPT desktop app) have real, typed, capability-gated support plus a real `SandboxPort`/`bwrap` containment mechanism — see `docs/architecture/m3-desktop-control.md` and `docs/threat-model/v0.md`'s "Milestone 3 additions" for what was actually built and the real, explicitly-accepted gap that spans every app at once: **no capability in this milestone was ever exercised against a real, live desktop window, a real Docker daemon, or a real network-reachable git remote** — every automated test uses an injected fake or a fully disposable scratch environment, by deliberate design during an unsupervised implementation run; live verification is a real, tracked, open item, not rounded up to "done." Next: M4 planning, not started.

## Architecture summary (see docs/architecture/ for full detail)

JARVIS is a capability-based agent kernel following Clean Architecture / ports & adapters, dependency rule pointing inward:

domain (stdlib only, no I/O, no async) → ports (Protocols) → application (use cases) → adapters (implementations) → kernel (composition root) → ipc/cli

Core principles:
- The kernel knows capabilities, not agents. New features are plugins; nothing in domain/application/ports names a specific integration (no "email agent", no vendor names).
- No shell. Capabilities declare typed effects (READ_LOCAL, WRITE_LOCAL, EGRESS_LOCAL, DESTRUCTIVE, IRREVERSIBLE, CREDENTIAL, EGRESS_SENSITIVE, etc). A single Policy Engine evaluates effects against a Tier (ALLOW/CONFIRM/MANUAL_ONLY/DENY) at one choke point. Command blocklists are never used.
- Every value carries Provenance (Trust: USER_DIRECT/SYSTEM/UNTRUSTED_EXTERNAL; Classification: PUBLIC/PERSONAL/SENSITIVE/SECRET). Values are wrapped Tainted[T]. Untrusted external content (web pages, emails, READMEs) escalates the required permission tier automatically.
- Voice/speaker verification is a convenience filter, never an authorization boundary (defeated by replay/cloning). Physical interaction with the machine is the real auth boundary.
- Privacy: SECRET data (API keys, passwords, tokens) is DENY to any cloud provider, always, no exceptions, never enters model context. SENSITIVE data (personal info, third-party confidential data) may go to a cloud provider only behind explicit CONFIRM. Where classification of a task's inputs is uncertain, it fails closed — inherits the highest classification present. Secrets live only in the system keyring, referenced, never stored as values, never in source, database, or audit log.
- Audio is never persisted to disk, ever, unless an explicit temporary debug mode is enabled.
- Destructive/irreversible/credential actions always require MANUAL_ONLY confirmation — never satisfiable by voice alone.
- Multi-provider reasoning (ChatGPT, Claude, others): both are trusted providers behind a ReasoningPort abstraction. No vendor names anywhere in domain/application/ports. Passing validation (build/test/lint/execution) is always stronger evidence than model agreement. An escalation ladder tries cheap deterministic fixes first, then self-repair, before ever consulting a second provider. Models never merge implementations — the arbiter selects one candidate unmodified, never a splice of two. A reviewing model must produce a failing test case, not a verdict/opinion. A test authored by a provider carries zero weight when scoring that same provider's own candidate.
- Audit log: every capability invocation is logged, hash-chained (tamper-evident), argument VALUES are never logged (only digests — secrets must never appear in the audit trail). A header/payload split so payloads can be redacted without breaking the chain is accepted (ADR-0028) but **not yet implemented** — `record_hash` today covers the whole record as one unit (see `docs/architecture/m0-architecture.md` section 5 and `docs/architecture/system-design.md` section 5).

## Workflow — one work package at a time, as directed

`docs/architecture/roadmap.md` does not exist yet (see `docs/architecture/README.md`); work package sequencing and scope come directly from the user in conversation, not from a roadmap file. If `roadmap.md` is ever supplied, this section should be updated to reference it for real.

For each work package: Analysis → Plan → Implement → Verify (all gates) → Review. You may move through these phases without stopping for approval at each one (I've approved autonomous execution for now), but ALWAYS stop completely at the end of a work package and report before starting the next one.

## Hard rules
- Never implement a future work package "while you're at it."
- Never silently change the architecture. If something in this file or the docs seems wrong once you're implementing, stop, explain the problem, propose a fix as a new ADR, and wait for approval before proceeding.
- Report every deviation from what was planned, including things you added.

## Invariants enforced by tooling, not convention
- domain/ imports stdlib only (mypy --strict clean, import-linter contract, and an AST-based test all check this).
- No datetime.now(), time.time(), time.monotonic(), or uuid.uuid4() anywhere in src/ — inject ClockPort / IdPort instead. Enforced by ruff banned-api AND an AST test (ruff alone doesn't catch attribute-style calls like time.time() after `import time`).
- No vendor names (openai, anthropic, chatgpt, claude, gpt) in src/jarvis/domain/, application/, or ports/.

## Gates — ALL must pass before any work package is considered done
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src tests
uv run lint-imports
uv run pytest
uv run coverage report --include="src/jarvis/domain/*" --fail-under=100
uv run coverage report --include="src/jarvis/application/policy/*" --fail-under=100
uv run coverage report --include="src/jarvis/application/reasoning/*" --fail-under=100

## Meta-tests

`tests/meta/` tests the gates themselves. If you add an import-linter contract,
add a test proving it fires against a deliberate violation, and add it to
`CONTRACT_SCHEDULE` in `test_gate_integrity.py`.

## Git
Branch wp/NN-slug. Conventional Commits. Squash-merge into main, one commit per work package. Tags at milestone completion only.
