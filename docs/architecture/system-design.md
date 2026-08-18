# JARVIS — System Design

**Status:** Reconstructed 2026-08-18 from recovered fragments of the
original architecture-phase design conversation, which was genuinely
approved before implementation started but never persisted into this
repository as a file — see `docs/architecture/README.md`. This is a
reconciliation, not a pristine original: every decision below has been
checked against what actually exists in this repository (real ADRs,
real source code) as of today, and the result of that check — real
match, partial match, or no match at all — is stated explicitly next
to each one, not smoothed over. Where a decision was never actually
built, that is said plainly, not implied to be done because it was
once decided.

**Critical numbering note:** the original design conversation used an
old, two-digit ADR numbering scheme (e.g. "ADR-024"). That scheme does
not exist in this repository. This repo's real ADRs are four-digit
(`ADR-0001`–`ADR-0037`), assigned during actual implementation across
WP-01 through WP-27. No old-scheme number appears anywhere below as if
it were real; every decision is reconciled against the real ADR list
or explicitly marked as having no corresponding real ADR.

---

## 1. Package hierarchy

Covered in full, and grounded directly in the real repo, by
`docs/architecture/m0-architecture.md` section 1 — not repeated here.
The five-ring dependency structure (`domain -> ports -> application ->
adapters -> kernel -> ipc/cli`) and the real, currently-configured
import-linter contracts (five: C1, C2, C5, C6, C7; C3/C4 scheduled but
not yet configurable) are that document's authoritative content.

## 2. Plugin ABI

**Reconciliation: no corresponding real ADR. No corresponding
implementation.** `src/jarvis/plugin_api/` contains only an empty
`__init__.py` today. The recovered decision below is real design
history, not something this repo has built or formally adopted as an
ADR yet.

> "Adding process isolation later usually means rewriting every
> plugin." Decision: "The invocation message schema is identical
> in-process and out-of-process." Consequence: "M3 sandboxing touches
> no plugin code."

This is a real, coherent design intent — worth carrying forward when
`plugin_api` actually gets built — but it is *intent*, not a decided
ADR in this repository and not yet reflected in any real schema. Do
not treat it as settled until an ADR exists for it.

## 3. The event bus: observation-only, never control flow

**Reconciliation: no corresponding real ADR. No corresponding
implementation.** No event bus exists anywhere in this codebase today.
The recovered rationale:

> "If a subscriber must run for correctness it is a function call, not
> a subscriber. The audit log is durable; the bus is lossy... Control
> flow stays explicit. Cost: some things that feel event-shaped are
> written as calls."

This principle is consistent with what M0 actually built: every real
call path in this repo today (`kernel/ping.py`, `kernel/music.py`,
`kernel/files.py`, `kernel/voice_loop.py`) is explicit function calls
end to end, with the audit chain as the durable record — there is no
pub/sub anywhere, so the principle has been followed *by never having
built the alternative*, not verified against a real bus implementation
that respects it.

## 4. Kernel API transport: JSON-RPC 2.0 over a Unix domain socket

**Reconciliation: no corresponding real ADR. No corresponding
implementation.** `src/jarvis/ipc/` contains only an empty
`__init__.py`. `docs/protocol/README.md` confirms this directly: *"No
JSON-RPC/IPC protocol exists yet... `cli/main.py` boots the kernel
directly, in-process, for every invocation."* The recovered decision:

> "The kernel API must not be reachable from the network, and must not
> require credential management." Decision: "JSON-RPC 2.0 over a
> mode-0600 Unix domain socket. Peer uid is read via `SO_PEERCRED` and
> must match the kernel's own." Cost noted: "JSON is slower than
> protobuf, which is irrelevant at this volume."

Real, coherent, unbuilt design intent — the actual protocol document
(`docs/protocol/README.md`) already anticipates this ("this document
describes what actually exists today instead... will need a real
rewrite once `jarvis.ipc` exists").

## 5. Persistence: audit chain

**Reconciliation: partial.** The audit chain's *hashing/tamper-evidence*
model is real and covered by `m0-architecture.md` section 5
(ADR-0026, ADR-0027). Two things from the original design conversation
need explicit correction against reality, not silent adoption:

**"SQLite persistence"** — no SQLite anywhere in this codebase today.
`adapters/audit_storage.py`'s `JsonFileAuditStorageAdapter` is a single
JSON file, rewritten whole on every save. If a SQLite-backed
persistence layer was part of the original design, it has not been
built; M0 shipped a simpler mechanism instead.

**"Header/payload split for redactable payloads"** — this recovered
fragment:

> "A hash chain forbids deleting records, but sensitive payloads will
> eventually need purging... 'The audit log can never be redacted' is
> a policy nobody keeps." Decision: "Chain over headers only. Headers
> carry a payload digest; payloads are stored separately and can be
> redacted in place."

**does resolve to a real ADR: ADR-0028** ("Audit log header/payload
split for redactable payloads") — matched on content, not number, per
the reconciliation rule. But checked directly against
`domain/audit.py` and `adapters/audit_storage.py`: **no header/payload
split exists in the actual code.** `AuditRecord.record_hash` covers
the entire `Decision` as one unit; there is no separately-stored,
independently-redactable payload anywhere. The ADR was accepted; the
implementation has not caught up to it. `m0-architecture.md` section 5
states this same gap — it is not repeated context, it is the same real
finding, cited from both documents deliberately rather than only one.

## 6. Secrets: full-disk encryption + system keyring, no SQLCipher

**Reconciliation: partial.** The recovered decision:

> "SQLCipher adds a build dependency and a key-management problem."
> Decision: "Rely on full-disk encryption for the database and the
> system keyring for secrets. Store secret references, never values."
> Stated limitation: "Protects a powered-off machine, not a running
> session against a local attacker."

The "secrets live in the keyring, referenced never stored" half is a
real, exact match: **ADR-0017**. The "rely on FDE instead of
SQLCipher for the database" half has **no corresponding real ADR** —
and, per section 5 above, there is no SQLite database in this
codebase yet for that decision to apply to at all. This is a case
where part of a recovered decision is genuinely settled (and cited
correctly) and part is not yet applicable to anything that exists.

## 7. Embeddings: canonical BLOBs, ANN index as a derived cache

**Reconciliation: no corresponding real ADR — out of M0's scope
entirely.** The recovered decision:

> "sqlite-vec is pre-v1 and states that users should expect breaking
> changes... Recent releases fixed correctness bugs including broken
> deletes and a data leak in its ANN index." Decision: "Embeddings are
> canonical as BLOBs in plain SQLite. The ANN index is a derived,
> rebuildable cache behind `VectorIndexPort`. Start with brute force
> and add an index only when a benchmark demands it."

This belongs to M4 (Memory & Retrieval), which has not started — see
`docs/architecture/m4-memory-retrieval.md`. Recorded here as real
design history worth carrying forward when M4 actually starts, not as
anything decided or built today.

## 8. D-Bus library choice: jeepney in the kernel

**Reconciliation: outcome confirmed correct; no dedicated real ADR.**
The recovered decision:

> "python-sdbus states its API is unstable; dbus-next has fork
> proliferation. The kernel must not depend on GLib." Decision: "Use
> jeepney in the kernel and adapters. Use `Gio.DBus` where GLib is
> already loaded, such as UI processes."

**Confirmed against real code**: `jeepney` is genuinely what
`MprisMediaPlayerAdapter` uses (WP-14, `adapters/media_player.py`), and
`gi`/GLib is genuinely excluded from `domain`, `application`, and
`kernel` — but that exclusion is enforced by import-linter contract
**C6 ("no GLib in the core")**, not by a dedicated ADR documenting the
jeepney-vs-alternatives library choice itself. No ADR titled around
this specific library decision exists in `docs/adr/`. The *outcome*
matches the recovered decision exactly; the *decision itself* was
never written up as its own ADR.

## 9. UI: the physical-confirmation dialog

**Reconciliation: real ADR exists, but the implementation diverged
from the recovered design in a way worth stating plainly, not
glossing over.**

Two recovered fragments:

> "Confirmation dialog is a separate, minimal process" — rationale:
> "Must survive console crash; small enough to audit by reading."

> "Injection interlock + typed challenge for MANUAL_ONLY" — rationale:
> "Emulated input is indistinguishable to Wayland clients by design."

Both are clearly the design intent behind what became **ADR-0035** ("A
genuine physical-keypress ConfirmationPort closes threat-model Finding
2," WP-24). But checked directly against `ADR-0035` and
`src/jarvis/ui/confirm/dialog.py`:

- **"Separate, minimal process" did not happen.** The real
  `Gtk4PhysicalConfirmationAdapter` shows the GTK4 dialog *in-process*,
  from within whatever process is running (`jarvis listen`, or a
  future caller) — not a distinct OS process. The stated rationale
  ("must survive console crash") does not hold for what was actually
  built: if the hosting process crashes, the dialog goes with it. This
  is a real, unresolved gap between the original design intent and
  what shipped, not a documentation oversight — worth a real decision
  (keep in-process, or actually split it out) if it matters going
  forward, not silently inherited as already handled.
- **"Injection interlock" did happen** — `_is_genuine_physical_event`
  requires a genuine `Gdk.Event` backed by a real input device;
  `tests/unit/test_confirmation_dialog.py` proves a missing or
  device-less event is rejected. This is real and matches the
  recovered rationale (emulated/injected input must be distinguishable
  and rejected).
- **"Typed challenge" did not happen.** Nothing in the real
  implementation asks the user to type a confirmation word or code —
  approval is a click or Enter/Space activation on an Approve/Deny
  button, full stop. If a typed-challenge layer is still wanted, it
  does not exist yet and is not implicitly covered by ADR-0035.

## 10. Audio: never persisted by default

**Reconciliation: real, exact match.** The recovered decision —

> "No audio persisted by default" — rationale: "Legal and privacy
> exposure with no design benefit."

— is **ADR-0018** ("Audio is never persisted to disk"), confirmed by
direct content match, not just a title. Also confirmed genuinely
implemented: `_AudioRingBuffer` (`adapters/wake_word.py`) is a plain
in-memory `deque` with zero file I/O anywhere in its implementation,
exercised by `tests/unit/test_wake_word_adapter.py`'s ring-buffer
tests. This is the one full match in this document — real ADR, real
implementation, both confirmed directly rather than assumed from the
recovered fragment alone.

---

## Summary table: old fragment → real repo status

| Recovered decision | Real ADR | Implemented? |
|---|---|---|
| Event bus, observation-only | No corresponding ADR | No |
| Unix-socket JSON-RPC + SO_PEERCRED | No corresponding ADR | No (`jarvis.ipc` empty) |
| Identical in/out-of-process plugin schema | No corresponding ADR | No (`jarvis.plugin_api` empty) |
| Audit chain: header/payload split | **ADR-0028** | **No** — not in the real code |
| Secrets: keyring, referenced not stored | **ADR-0017** | Yes |
| Secrets: FDE instead of SQLCipher | No corresponding ADR | N/A — no database exists yet |
| Embeddings: canonical BLOBs + derived ANN | No corresponding ADR | N/A — M4 scope, not started |
| jeepney in the kernel, no GLib in core | No dedicated ADR (enforced via import-linter C6) | Yes |
| Confirmation dialog as a separate process | **ADR-0035** (partial) | **No** — real dialog is in-process |
| Injection interlock for MANUAL_ONLY | **ADR-0035** (partial) | Yes |
| Typed challenge for MANUAL_ONLY | **ADR-0035** (partial) | No |
| Audio never persisted by default | **ADR-0018** | Yes |
