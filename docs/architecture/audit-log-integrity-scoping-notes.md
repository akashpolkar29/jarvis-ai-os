# Audit-log integrity scoping notes — one real, closable test gap closed; one real, structural gap, investigated, not decided

**Status: research and one real test fix only. No architecture decision
made, no new mechanism designed or built.** Written 2026-09-05
(adapter-resilience/mutation-extension/audit-log-integrity pass,
Track 3), per that pass's own instruction: if a real integrity
mechanism already exists, close any real, missing test proving it
works; if a real gap exists with no mechanism at all, write it up here
rather than design or build a fix unprompted. Mirrors
`m7-scoping-notes.md`'s own format and posture exactly.

## What the real code actually does today, quoted directly

`domain/audit.py::AuditChain` is a real, hash-chained, append-only
(by construction — `append()` is the only way a record enters the
chain; there is no `remove`/`edit` method) in-memory sequence of
`AuditRecord`s:

```python
def compute_hash(self) -> str:
    """Compute this record's hash from its own (sequence, decision, previous_hash)."""
    return _compute_record_hash(self.sequence, self.decision, self.previous_hash)


def __post_init__(self) -> None:
    """Validate ``record_hash`` matches this record's own content."""
    if self.record_hash != self.compute_hash():
        msg = f"record_hash does not match content at sequence {self.sequence}."
        raise AuditRecordTampered(msg)
```

Every real `AuditRecord` is reconstructed through this real
constructor on load (`adapters/audit_storage.py::_decode_record`), so
**per-record tampering is caught automatically, for free, with no
bespoke check** — already real, already tested
(`test_a_corrupted_record_hash_raises_on_load`).

`AuditChain.verify()` additionally walks the whole chain checking
`sequence`/`previous_hash` linkage, catching **cross-record**
tampering (a deleted or reordered middle record) that per-record
validation alone cannot see — already real, already tested
(`test_a_deleted_middle_record_is_not_caught_by_load_but_is_caught_by_verify`).

## The real, closable test gap this pass found and closed

Both existing tests tamper with the **`record_hash` field itself**
(setting it to a fixed dummy value), never a real **decision field**
(e.g. `granted`) left in place with `record_hash` untouched — the
more realistic, more security-relevant forgery attempt ("edit a past
denied `fs.delete_file` to look granted, without knowing how to also
recompute a matching hash"). A new test,
`test_editing_a_real_past_decision_field_directly_on_disk_is_caught_on_load`
(`tests/unit/test_audit_storage_adapter.py`), proves the same real
mechanism catches this too — confirmed real, not assumed: the test
passes because `compute_hash()` is recomputed from the record's own
*current* (now-forged) content and compared against the *stale*
stored hash, which no longer matches. This is the exact scenario named
directly by this pass's own instructions ("editing a past entry
directly on disk and confirming the system notices").

## The real, structural gap: no protection against wholesale file replacement

Checked directly, not assumed: `adapters/audit_storage.py::JsonFileAuditStorageAdapter.save()`
is a plain `self._path.write_text(...)` call. No `os.chmod()`, no
restrictive permission mode, no OS-level immutable/append-only flag
(`chattr +a` or equivalent) is ever set anywhere in this codebase --
confirmed by grep, zero hits for `chmod`/permission-mode constants in
`adapters/audit_storage.py`.

**This is a real, different failure mode from the hash chain's own
guarantee, worth stating precisely rather than rounding together**:
the hash chain proves a *loaded* chain's own internal self-consistency
-- it can prove "this sequence of records is coherent and unaltered
relative to itself." It cannot prove anything about records that were
never loaded at all. A real actor (or process) with ordinary
filesystem write access to the chain file -- the same, ordinary access
level the legitimate `JsonFileAuditStorageAdapter` itself already has,
nothing more privileged required -- can replace the *entire file* with
a **new, freshly-computed, fully self-consistent, but wholly
fabricated chain** (e.g. one that simply omits every `DESTRUCTIVE`/
`MANUAL_ONLY` denial, or reports every past decision as `granted`).
`verify()` on the replacement would report `valid=True`: nothing about
a freshly-and-correctly-computed hash chain is wrong, only its
relationship to *history* is fabricated -- a limitation `verify()`
structurally cannot detect on its own, since it has no independent
record of what the chain looked like before.

This is the exact same real, root limitation this pass's own sibling
finding (the cross-process concurrent-writer race, adapter-resilience/
mutation-extension pass Track 1 -- see `docs/threat-model/v0.md`'s own
note) already surfaced from a different angle: `save()`'s whole-file
overwrite has no protection against being replaced, whether by an
innocent second legitimate writer racing a save, or by a deliberate
wholesale forgery. Both point at the same real gap in
`AuditStoragePort`'s own persistence contract.

**No mechanism exists for this today -- stated plainly, not designed
around.** Real options, laid out without deciding between them, matching
this pass's own explicit instruction not to build a fix unprompted:

1. **Restrictive file permissions** (`0o600`, owner-only) at `save()`
   time. Real, minimal, cheap. Does not stop the file's own owner (the
   same user JARVIS itself runs as) from replacing it -- only narrows
   the *other-user* attack surface, not the primary one described
   above.
2. **An OS-level append-only flag** (`chattr +a` on Linux ext-family
   filesystems). Real, stronger -- prevents truncation/replacement by
   the owning user too, without root. Real costs: not universally
   supported (depends on filesystem type), requires the CAP_LINUX_IMMUTABLE
   capability to *set* (though not to *append* once set), and this
   project's own adapter would need real code to detect/handle a
   filesystem that doesn't support it.
3. **A separate, real write-once store or external anchor** (e.g.
   periodically publishing the chain's own latest `record_hash` to a
   location the JARVIS process itself cannot rewrite -- a real design
   space of its own, not sketched further here).
4. **Accept the current guarantee as sufficient and document it
   precisely** -- the hash chain already provides real, meaningful
   tamper-*evidence* for the common, realistic case (accidental
   corruption, a bug, a casual edit), even though it cannot resist a
   deliberate, privileged, wholesale-replacement adversary. Many real
   systems accept exactly this tier of guarantee.

No option is recommended over another here -- this is the user's own
architecture decision to make, per this project's standing "never
silently change the architecture" rule, the same posture
`m7-scoping-notes.md` and every other real scoping note in this
project already takes.
