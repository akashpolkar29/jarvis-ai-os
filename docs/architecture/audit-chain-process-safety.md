# Audit-chain cross-process safety (WP-115, 2026-09-11)

## Status

Real, implemented. No ADR -- investigated first, per this work
package's own explicit instruction: this closes a previously-documented
structural *bug* (a lost-update race), it does not introduce a new
formal architectural decision. `AuditStoragePort`'s own method
signatures (`save`/`load`) are unchanged; `AuditRecord`'s schema,
hash computation, and chain-verification semantics are all unchanged.

## The real race, precisely

### What was read, modified, and written

Every real `kernel/*.py` composition function follows the identical
shape:

```python
storage = JsonFileAuditStorageAdapter(chain_path)
chain = storage.load()  # READ
decision = orchestrator.authorize_by_id(...)  # MODIFY (internally: chain.append(...))
storage.save(chain)  # WRITE
```

`JsonFileAuditStorageAdapter.save()` (before this fix) was a plain
"write exactly what I was given" operation: `json.dumps([...records
from the chain argument...])`, then an atomic temp-file-then-`replace`
(WP-101, 2026-09-08). It never consulted the file's own *current*
content before overwriting it.

### Which independent processes can trigger it

Any two real JARVIS processes pointed at the same `--chain-path`:
two concurrent `jarvis do`/`jarvis task run` invocations, a running
`jarvis ui` server racing a separate CLI call, two separate `jarvis
ui` server instances, etc. (`jarvis ui`'s own single-threaded design,
WP-108, already prevents *intra-process* concurrent requests from
racing each other on the chain file -- this work package closes the
*inter-process* version of the identical hazard.)

### The exact failure sequence

1. Process A calls `load()` -- sees chain state `S` (N records).
2. Process B calls `load()` -- also sees `S` (nothing has changed yet).
3. Process A's own authorization appends record N (in memory only,
   via `AuditChain.append()`) -- A's in-memory chain is now `S + [A]`.
4. Process B's own authorization appends record N (in memory only) --
   B's in-memory chain is now `S + [B]`, a *different* record also
   claiming sequence N.
5. Process A calls `save()` -- writes `S + [A]`. Disk now has N+1
   records.
6. Process B calls `save()` -- writes `S + [B]`, **completely
   replacing** what A just wrote. Disk now has N+1 records again, but
   record N is B's, not A's. **A's own record is gone, with no error,
   no corruption, and no trace.**

`verify()` on the surviving chain still reports `valid=True` -- B's
own chain is internally self-consistent; only its relationship to
*history* (the fact that A's decision was ever made and ever recorded)
is wrong, and nothing about `verify()`'s own design can detect that,
since it has no independent record of what should have been there.

This is a **lost update**, not corruption: the surviving file is
always a real, valid, hash-chained sequence of *some* records. The bug
is that it silently omits a real decision that was, in fact, durably
authorized (the audit record for A's own granted/denied decision is
gone, even though A's own `authorize_and_*` call already returned
successfully to its own caller).

## Why a file lock, not an append-only format or a port change

Three real options exist in principle for this class of problem:
(1) real OS-level file locking around the critical section, (2) an
append-only storage format (each record its own line/file, no
whole-file rewrite at all), (3) accept the limitation (what this
codebase did until now). Option 2 would be a genuine, larger
`AuditStoragePort`-contract-shaped change (a different on-disk format
entirely) -- out of proportion to the actual problem, and a real
breaking change to every existing `.json` chain file in the field,
with no more safety benefit than option 1 once option 1 is applied
correctly. Option 1 (real process-safe locking) closes the race
completely, requires zero changes to `AuditStoragePort`'s own method
signatures, zero changes to any of the 12+ real `kernel/*.py` callers,
and zero changes to the on-disk JSON schema or the hash-chain formula
-- the narrowest change that actually closes the race, per this work
package's own explicit preference.

**Why `fcntl.flock()`, not a new direct or transitive dependency**:
checked directly before choosing -- `filelock` exists only as a
*transitive* dependency of dev/embedding tooling (`huggingface-hub`,
`virtualenv`), never a direct project dependency; adding it as a real,
direct dependency for this one mechanism was rejected in favor of
`fcntl`, a Linux stdlib module requiring zero new dependencies at
all, matching this project's own Linux-only scope (`CLAUDE.md`'s own
opening line) and its general preference for stdlib over new
third-party surface area.

## The mechanism

### Why a separate lock file, not the chain file itself

`save()`'s own atomic write replaces the chain file's *inode* via
`Path.replace()`. `flock()`ing the chain file directly would have the
lock silently detach from the path the instant any writer's replace
landed -- the lock stays bound to the *old* inode, not whatever inode
the path now points to, for any process that opened-and-locked before
the replace. A real, separate, stable-identity file (`<chain_path>.lock`,
a sibling of the chain file, never itself replaced) has no such
hazard.

### Why the lock file is permanent, not deleted after use

Deleting a lock file while another process might still hold an open
file descriptor to it recreates it under a new inode on next use --
the identical class of hazard from a different angle (a waiting
process's already-open descriptor stays locked against the *deleted*
inode; a new caller opens and locks the *freshly recreated* one; the
two no longer exclude each other). A small, permanent, zero-byte file
is the accepted, standard cost of `flock()`-based locking.

### Why `load()` needs no lock at all

`os.replace()` is atomic at the filesystem level (same-filesystem
rename) -- any concurrent reader sees either the complete old file or
the complete new file, never a torn mix. `load()` was already safe
against a concurrent `save()` before this work package; it remains a
plain, unlocked read. Locking is scoped to exactly the one method that
actually needs it, per this work package's own "lock the smallest
necessary critical section" instruction.

### What `save()` now actually does

Under a real, exclusive, cross-process `fcntl.flock()` held only for
this one method's own body:

1. Re-reads the file's *current* content fresh from disk (never
   trusts whatever this instance's own last `load()` saw -- that may
   now be stale).
2. Identifies which of the caller's own `chain` records are genuinely
   *new* -- its tail beyond `self._loaded_count` (the record count
   this same adapter instance's own most recent `load()` returned; 0
   if `load()` was never called on this instance, meaning "treat
   everything I have as new, append it after whatever is already
   there").
3. Re-parents each new record onto the file's *current* tail via
   `AuditChain.append()` (completely unmodified, reused as-is) --
   recomputing a fresh `sequence`/`previous_hash`/`record_hash` for
   each, exactly as if this caller's own append had happened after
   whatever another process already persisted. A record's true
   position in the chain is only knowable at the moment it is
   actually durably persisted, not when it was first computed in
   memory.
4. Atomically writes the merged result through the same,
   byte-for-byte-unchanged WP-101 temp-file-then-`replace` mechanism,
   then releases the lock.

In the common case -- no concurrent writer, the overwhelming majority
of real calls -- the disk has not moved since this instance's own
`load()`, so rebasing the new records onto the unchanged base
reproduces the original `chain` argument exactly, record for record,
hash for hash. **This method's observable behavior in the no-race case
is byte-for-byte identical to before this work package.**

### A real, necessary, explicitly-named semantic change

`save()` no longer means "overwrite the file with exactly this
chain" -- it means "durably persist this chain's own new content,
without ever discarding unrelated content already on disk."
`save(AuditChain())` (an empty chain) can no longer be used to wipe an
existing file. Checked directly before accepting this: no real caller
in this codebase ever relied on that -- every real kernel composition
function follows the identical `load()` -> authorize (-> `append()`)
-> `save()` sequence on one shared adapter instance, never a bare
`save()` meant to discard unrelated history. One existing test
(`test_save_overwrites_a_previous_save`) tested exactly this
incompatible, bug-adjacent semantic and was rewritten
(`test_save_of_an_empty_chain_on_a_fresh_instance_does_not_discard_existing_records`)
to prove the new, correct property instead.

### A record's in-memory identity can legitimately change before persistence, and why this is invisible

If another process's save lands in between, a caller's own
just-appended `AuditRecord` (as `AuthorizationOrchestrator.authorize_by_id()`
returned it, before the caller's own `save()` runs) may end up
persisted under a different `sequence`/`previous_hash`/`record_hash`
than it was originally computed with in memory. Checked directly, not
assumed: no real caller in this codebase ever reads
`AuditRecord.sequence`/`.record_hash` from a just-appended record --
`Decision`, the one value every real `authorize_and_*` composition
function actually returns to its own caller, carries neither field at
all (confirmed by grep: `.record_hash` and `.sequence` are read
nowhere in `kernel/`/`application/` except inside
`domain/audit.py`/`adapters/audit_storage.py` themselves, and one real,
compatible exception -- `kernel/audit.py`'s `audit.history`, which
always displays a record's position from a *freshly reloaded* chain,
never a stale in-memory one). A caller that reads the chain back via a
fresh `load()` always sees the true, final, correctly-rebased state.

### A real, additional safety property gained for free

Re-reading the disk inside `save()` means a genuinely corrupted
on-disk file (tampered `record_hash`, a dangling `previous_hash`) now
raises `AuditRecordTampered` *during* `save()` too, not only during an
explicit `load()`. Before this work package, `save()` never read the
disk at all, so it would have silently overwritten a corrupted file
without ever noticing.

## Why an unbounded, blocking lock, not a timeout

`fcntl.flock()` is called without `LOCK_NB` -- a waiting process
blocks until the lock is free, however long that takes. Two real
properties justify this: (1) the real critical section is always fast
(read a small JSON file, append N records, write it back -- never
network I/O, never user interaction), so genuine contention is
resolved in milliseconds; (2) a timeout would introduce a *new*
failure mode this work package exists to prevent -- a legitimate
second writer giving up and losing its own audit record under
real load, the exact harm being fixed. `flock()` locks held via an
open file descriptor are released automatically by the kernel the
moment the holding process exits, for any reason, including a crash or
`SIGKILL` -- "normal process failure" (the scenario this work package's
own requirements name) cannot leave a stuck lock. Only a process that
is hung but still alive would hold the lock indefinitely, the same
property any real mutex has under a hang, not a new risk.

## Testing

- **`tests/unit/test_audit_storage_adapter.py`** (existing file,
  updated): the pre-existing
  `test_two_independent_writers_racing_on_the_same_file_silently_lose_one_writers_record`
  (which *proved the bug*) is now
  `test_two_independent_writers_racing_on_the_same_file_both_records_survive`
  (proves the fix) -- two separate adapter instances, each used for
  its own complete `load()` -> `append()` -> `save()` sequence
  (mirroring real kernel usage exactly, unlike the original test's own
  fresh-instance-per-call simulation), both records present in the
  final, valid chain. `test_save_overwrites_a_previous_save` (tested
  the incompatible old semantic) is replaced by two new tests proving
  the new, correct "never silently discards unrelated content" and
  "same-instance load-then-save still works exactly as before"
  properties. Two existing atomic-write tests were updated to expect
  the real, new, permanent `.lock` file alongside the chain file. A
  new, explicit test
  (`test_save_releases_its_real_lock_even_when_the_write_raises`)
  proves lock release after a real, simulated mid-save crash --
  directly, via a real, independent, non-blocking `flock()` probe
  immediately afterward, not inferred from a later call merely
  succeeding.
- **`tests/unit/test_audit_storage_process_safety.py`** (new): real
  `multiprocessing.Process` workers -- genuinely separate OS processes,
  not threads or sequential simulated instances -- synchronized via a
  real `multiprocessing.Barrier` immediately before each one's own
  `save()` call, maximizing actual lock contention deterministically
  (never relying on timing luck for correctness: the fix must hold
  regardless of how much real overlap occurs; the barrier only makes
  the contended path likely to actually be exercised). Two tests: one
  starting from an empty chain, one starting from real pre-existing
  history. Both prove every worker's own record survives, the final
  chain has the expected length, `verify()` reports `valid=True`, and
  sequence numbers are contiguous. Run 5 consecutive times during
  development with zero flakiness.
- Unaffected, confirmed by direct rerun: `tests/unit/test_audit_concurrency.py`
  (the pre-existing in-process `threading.Lock` tests) and
  `tests/contract/test_audit_storage_port.py` (the adapter still
  satisfies `AuditStoragePort`'s own Protocol).

## Regression checks performed

Confirmed unchanged by direct inspection and full-suite rerun (1652
real tests passing, only the two pre-existing, unrelated failures --
a GUI-display sandbox test needing a real X11 display, and the
already-documented ~33%-failure-rate live-Ollama planning test):
audit record schema (`AuditRecord`'s own fields, untouched),
hash calculation (`domain/audit.py`, zero lines changed),
chain verification (`AuditChain.verify()`, zero lines changed),
authorization decisions (`domain/policy.py`/`application/policy/orchestrator.py`,
zero lines changed), `TaskStore`/router/UI behavior (none of
`kernel/tasks.py`, `kernel/router.py`, `cli/ui_server.py` were
touched), capability registration (`kernel/capabilities.py`, zero
lines changed), and every existing CLI subcommand's own semantics.

## Residual limitations, stated plainly

- **Not a signing/HMAC/external-anchor mechanism.** This closes the
  lost-update race between legitimate JARVIS processes. It does not,
  and was never intended to, defend against a privileged adversary
  with filesystem write access who is willing to fabricate an entire,
  freshly-self-consistent replacement chain (the separate,
  already-documented "whole-file replacement" gap,
  `docs/architecture/audit-log-integrity-scoping-notes.md`) -- a
  genuinely different threat model, out of this work package's own
  scope.
- **Advisory locking, not mandatory.** `fcntl.flock()` is advisory --
  it only excludes other `flock()`-respecting callers. A process that
  opened the chain file directly with a plain text editor and wrote to
  it would not be blocked. This matches every other file-locking
  mechanism on Linux and is not specific to this fix.
- **A genuinely hung (not crashed) holder blocks others indefinitely.**
  Accepted deliberately (see "Why an unbounded, blocking lock" above)
  rather than introducing a timeout that could itself cause a
  legitimate writer to lose its own record under load.
- **`save(AuditChain())` can no longer wipe the file.** If a future,
  real need for "delete the entire audit chain" ever arises, it needs
  its own explicit, dedicated mechanism -- not expressible through
  `save()` anymore, by design.
