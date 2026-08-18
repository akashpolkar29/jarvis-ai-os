# JARVIS — M0: Kernel Architecture (As-Built)

**Status:** As-built record, reconstructed 2026-08-18. M0 was genuinely
designed and approved in an original architecture-phase conversation,
but the source document (`m0-architecture.md`) was never actually
delivered into this repository — see `docs/architecture/README.md`.
This document is not that missing original. It is written *after the
fact*, grounded primarily in the real repository (source code, the 32
M0-era ADRs, `CLAUDE.md`'s own Architecture summary, the real
import-linter contracts) rather than reconstructed from memory of the
original spec. Where recovered fragments of the original design
conversation add real, undisputed context, they are used as connective
narrative only, never as a substitute for what the code actually does.

**Grounded in:** `docs/adr/0001` through `docs/adr/0032` (M0-era),
`pyproject.toml`'s `[tool.importlinter]` section, `src/jarvis/domain/`,
`src/jarvis/application/policy/`, `src/jarvis/kernel/capabilities.py`.

**Milestone status:** Complete. Tagged `v0.1.0`, then `v0.1.1` (a
privacy-fix release — see below).

---

## 1. Clean Architecture / ports and adapters

JARVIS follows Clean Architecture with the dependency rule pointing
inward, across five rings:

```
domain -> ports -> application -> adapters -> kernel -> (ipc / cli)
```

- **`domain/`** — pure business rules and value objects. Stdlib-only,
  no I/O, no async (ADR-0029). No direct wall-clock or randomness
  access anywhere in `src/` — `ClockPort`/`IdPort` are injected instead
  (ADR-0030). No vendor names (ADR-0021).
- **`ports/`** — `typing.Protocol` definitions describing a role
  ("a clock," "a confirmation source," "a capability registry"),
  never a concrete integration. May depend on `domain` only.
- **`application/`** — use cases that wire pure domain logic into
  callable orchestration (e.g. `AuthorizationOrchestrator`). May depend
  on `domain` and `ports`.
- **`adapters/`** — concrete implementations of ports (`ManualConfirmationAdapter`,
  `JsonFileAuditStorageAdapter`, `MprisMediaPlayerAdapter`,
  `LocalFileSystemAdapter`). The only ring allowed to name a vendor or
  a specific technology.
- **`kernel/`** — the composition root. The one place allowed to know
  about every ring at once; wires concrete adapters, ports, and
  application use cases into the actual callable system.
- **`ipc/`, `cli/`** — outermost layer. `cli/` has real content (M0's
  CLI entrypoint); `ipc/` does not yet (see `docs/protocol/README.md`
  — no JSON-RPC/wire protocol exists; the CLI boots the kernel
  in-process for every invocation).

This is ADR-0001. It is enforced by tooling, not convention: an
import-linter "layers" contract (`C1 layered architecture`) fails the
build if a lower ring imports a higher one.

### Import-linter contracts, as actually configured

Verified directly against `pyproject.toml` rather than assumed — **five
contracts are configured today, not more**:

- **C1 layered architecture** — the ring ordering above, `cli` →
  `kernel` → `ipc` → `adapters` → `application` → `ports` → `domain` →
  `ui` (`ui` added in M1/WP-24; see below).
- **C2 domain purity** — `domain/` may not import `ports`,
  `application`, `adapters`, `plugin_api`, `kernel`, `ipc`, or `cli`.
- **C5 ui privilege** — `jarvis.ui` (added in M1) may not import any
  other `jarvis` package at all; it is a pure rendering leaf.
- **C6 no GLib in the core** — `domain`, `application`, and `kernel`
  may never import `gi` (GTK/GLib bindings).
- **C7 plugin_api depends only on domain** — `jarvis.plugin_api` may
  not import `application`, `adapters`, `kernel`, `ipc`, or `cli`.

**C3 (plugin isolation)** and **C4 (adapter independence)** are named
and scheduled in `tests/meta/test_gate_integrity.py`'s
`CONTRACT_SCHEDULE` but not yet configured — import-linter errors on a
contract naming a package that doesn't exist on disk yet, and the
packages those two contracts would police (a real `plugins/*` workspace
member, per-adapter subpackages) don't exist yet. This is a real,
current gap, not an oversight to paper over.

## 2. Capabilities, not agents

The kernel's unit of extension is a **capability** — a single typed
action (`ping`, `music.play`, `fs.read_file`) — not an "agent" (ADR-0002).
Nothing in `domain`, `application`, or `ports` names a specific
integration; a plugin adds capabilities, it does not add a bespoke
"email agent" or "browser agent" concept to the kernel itself.

There is no shell and no command blocklist, ever (ADR-0003, ADR-0007).
A capability declares its **effects** from a fixed, closed taxonomy
(`Effect`, a `Flag` enum in `domain/capability.py`) rather than
exposing raw command execution:

```
NONE, READ_LOCAL, WRITE_LOCAL, EXECUTE, DESTRUCTIVE, IRREVERSIBLE,
CREDENTIAL, EGRESS_LOCAL, EGRESS_SENSITIVE, EGRESS_SECRET
```

This taxonomy is fixed and closed (ADR-0004) — a capability cannot
invent a new effect kind to sidestep policy, and every effect maps
deterministically to a minimum required tier.

`CapabilityRegistry` (`domain/registry.py`) holds every registered
`CapabilityDescriptor`; `kernel/capabilities.py`'s
`build_default_registry()` is the single place every capability the
kernel actually knows about is declared. As of `v0.1.1`, three real
capabilities exist: `ping` (a no-op proving the stack), the four
`music.*` commands (MPRIS playback control), and `fs.read_file` (scoped
local file reads).

## 3. Provenance and taint tracking

Every value that could influence an authorization decision is wrapped
in `Tainted[T]` (ADR-0010), carrying a `Provenance`: a `Trust` level
and a `Classification`.

`Trust` (`domain/provenance.py`, ADR-0008):
```
USER_DIRECT, SYSTEM, UNTRUSTED_EXTERNAL
```

`Classification` (ADR-0009):
```
PUBLIC, PERSONAL, SENSITIVE, SECRET
```

Untrusted external content (a web page, an email, a file whose
provenance is unknown) auto-escalates the required policy tier by one
step (ADR-0011) — a capability that would otherwise be `ALLOW` becomes
`CONFIRM` if any of its tainted arguments carry `UNTRUSTED_EXTERNAL`
trust. Where classification is genuinely uncertain, the system fails
closed to the highest classification present (ADR-0016) rather than
guessing low.

`SECRET` data is an unconditional `DENY` to any cloud provider, no
exceptions (ADR-0014). `SENSITIVE` data may reach a cloud provider only
behind an explicit `CONFIRM` (ADR-0015). Secrets themselves — API keys,
passwords, tokens — live only in the system keyring; every other layer
of the system (domain objects, the database, the audit log, source
code) holds a reference, never the value (ADR-0017).

## 4. The policy engine: four tiers

`domain/policy.py`'s `evaluate()` is a pure function — no I/O, no
logging, no side effects — and the sole place a `Decision` gets made
(ADR-0005). It is the actual authorization choke point of the whole
system; everything else (audit logging, UI confirmation prompts, the
orchestration layer) reacts to what this function decides, never
overrides it.

Four tiers (`Tier`, an `IntEnum` in `domain/capability.py`, ADR-0006):

```
ALLOW = 0       granted unconditionally, context never read
CONFIRM = 1     granted if physical_confirmation_available OR remote_confirmation_available
MANUAL_ONLY = 2 granted only if physical_confirmation_available
DENY = 3        never granted, regardless of confirmation
```

`PolicyContext` (the only value `evaluate()` reads to decide) is
deliberately just two booleans: `physical_confirmation_available`,
`remote_confirmation_available`. `MANUAL_ONLY` deliberately never reads
`remote_confirmation_available`, even if `True` — voice/remote
confirmation is a convenience filter, never an authorization boundary
(ADR-0012), and physical interaction with the machine is the one
signal the design treats as trustworthy for that tier (ADR-0013).
Destructive, irreversible, or credential-touching actions always
require `MANUAL_ONLY` (ADR-0019).

`ConfirmationPort` is the seam between a real confirmation source and
`PolicyContext`. In M0, the only implementation is
`ManualConfirmationAdapter` — fixed, constructor-supplied booleans,
honestly documented in the M0 threat model as providing no real
presence signal at all (Finding 2). Closing that gap for voice-triggered
invocation was M1's central goal (`PhysicalConfirmationPort`, ADR-0035)
— out of scope for M0 itself, noted here only so this document doesn't
read as though the gap was already closed at M0's tag.

## 5. The audit log

Every capability invocation is logged, hash-chained, and
tamper-evident (ADR-0026). `AuditChain`/`AuditRecord`
(`domain/audit.py`) form an append-only sequence where each record's
`record_hash` covers `(sequence, decision, previous_hash)` — a
structurally-enforced chain: it is not possible to construct an
`AuditRecord` whose stored hash doesn't match its own content
(`__post_init__` raises `AuditRecordTampered` otherwise).

Argument **values** are never logged, only digests (ADR-0027) — a
sha256 hexdigest of a canonicalized JSON representation. This was not
true from the very first M0 release: `v0.1.0`'s tag message documents
this as a known gap (raw argument values were briefly persisted,
contradicting the ADR), closed in `v0.1.1` as a breaking, one-way
change — pre-`v0.1.1` audit chain files cannot be loaded, because raw
values were never persisted for digest recomputation. This is real
project history, not a hypothetical caveat.

**A genuine gap between decided and built, worth stating plainly**:
ADR-0028 ("audit log header/payload split for redactable payloads") is
an accepted ADR, but checked directly against `domain/audit.py` and
`adapters/audit_storage.py`, **no header/payload split exists in the
actual code** — no field or storage structure named or shaped that way
anywhere. `record_hash` covers the entire `Decision` as one unit. The
ADR states an intended design; the implementation has not yet realized
it. This document does not paper over that difference.

The hash chain's own honestly-documented limit: it detects any
tampering with a single record, or any partial reordering not
accompanied by recomputing every subsequent hash. It does **not**
protect against an attacker with write access to storage who is
willing to relabel sequence numbers and recompute hashes forward
through the rest of the chain — that requires a signing key, HMAC, or
external anchoring, none of which exists yet (see
`docs/threat-model/v0.md`, Gap 3).

## 6. What M0 deliberately did not build

Stated plainly, matching the threat model's own honesty: no real
physical-presence detection (closed for voice in M1, not for direct
CLI use — see `m1-voice-architecture.md`), no plugin sandboxing
(`jarvis.plugin_api` has no real content yet), no signed/externally-anchored
audit chain, no encryption at rest for the audit log, no atomic writes
for the audit file, and no verification that a `ConfirmationPort`
adapter is telling the truth. `docs/threat-model/v0.md` is the
authoritative, continuously-maintained record of these — this document
does not duplicate it, only points at it.

## 7. Coverage discipline

Coverage is gated per-package, not globally (ADR-0032): `domain/` and
`application/policy/` are held to 100% branch coverage as their own,
separate gates — a change that adds untested code elsewhere in the
tree cannot dilute coverage on the two rings where correctness matters
most. This is real, currently enforced: `uv run coverage report
--include="src/jarvis/domain/*" --fail-under=100` and the equivalent
for `application/policy/*` are two of the seven gates every work
package must pass (see `CLAUDE.md`).
