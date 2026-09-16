# Event / trace observability review (WP-177)

## Status

Real, implemented (one small, additive piece). No ADR -- no new
`CapabilityId`/`Effect`/`Tier`, no change to `AuditRecord`'s schema,
no change to the audit chain's storage format, no new source of
truth.

## What was reviewed (checked directly, file by file)

- **`domain/events.py`** (`EventBus`, `TaskCreated`, `TaskStatusChanged`,
  WP-111) -- a real, minimal, in-process, synchronous event bus.
  `TaskStatusChanged.new_status` already represents "started"
  (`"running"`), "completed" (`"completed"`), and "failed"
  (`"failed"`) as the identical, general transition shape -- WP-111's
  own docstring already reasoned through and rejected a separate class
  per destination status. `kernel/tasks.py` publishes it from the
  *only* two real places task state ever changes
  (`write_task_record`/`update_task_status`), always *after* the
  underlying write was actually granted -- never fabricated.
- **`kernel/worker.py`** and `cli/ui_server.py` -- both real, already-
  wired consumers: the worker threads `event_bus` through every task
  it runs; the UI server owns one shared `EventBus`, subscribes real
  logging callbacks to both event types, and exposes `GET
  /api/tasks/<id>` as a deliberate polling (not push/SSE) recovery
  path, reasoned through already in WP-111's own module docstring
  (the server's `HTTPServer` is deliberately single-threaded, so a
  long-lived SSE connection would block it).
- **`domain/audit.py::AuditChain`/`AuditRecord`** -- the real,
  hash-chained, tamper-evident record of every capability invocation
  and its `Decision` (granted/denied/reason). This is, and remains,
  the one authoritative trace of "what was authorized and what
  happened as a result" -- **not replaced or duplicated by this work
  package**, per its own explicit instruction.
- **`kernel/audit.py::authorize_and_view_audit_history`** (Phase 10)
  -- the existing, real, read-only way to inspect that trace
  (`jarvis audit-history`), already supporting a `--capability-id`
  filter.

## What was found to already be sufficient (no new infrastructure)

- **"Task started" / "task completed" / "task failed"**: already
  fully covered by `TaskStatusChanged`, already published, already
  logged by `jarvis ui`'s own subscribers. Nothing missing.
- **"Authorization decision"**: already fully covered by the audit
  chain itself -- every decision, granted or denied, is already a
  durable, tamper-evident record, and `jarvis audit-history` already
  exposes it. Building a second, event-based representation of the
  same fact would be exactly the "second source of truth" this work
  package explicitly forbids.
- **"Tool/capability execution"**: this *is* what the audit chain
  records, by construction -- already complete.

## What was found genuinely missing, and built

**"Skill invocation"** had no real answer: a skill (WP-171-175) is
never itself invoked -- only the real capabilities it groups are --
so there was no way to ask "which real, audited capability calls
belong to skill X?" without manually cross-referencing two disconnected
listings by hand. `authorize_and_view_audit_history` gained one new,
optional parameter, `skill_id` (and `jarvis audit-history --skill
<skill_id>`, combinable with the existing `--capability-id`): it looks
up the real, already-registered skill's own `capability_ids`
(`build_default_skill_registry`, completely unmodified) and filters
the already-loaded, already-authoritative chain against that set. An
unregistered or malformed skill id matches nothing -- an honest empty
result, mirroring `jarvis skills show`'s own identical treatment of
the same failure mode, never a crash.

**Why this is not a new source of truth**: no new storage, no
`AuditRecord` field, no write path. It is a pure, read-time
correlation between two already-real, already-authoritative
structures (the audit chain and the skill registry), computed fresh
on every call, never cached or persisted separately. If a skill's own
`capability_ids` ever change, the very next call reflects that --
there is nothing to keep in sync.

## What was deliberately not built

- No `AuditRecord` schema change (no timestamp, no task-id/correlation
  field) -- explicitly out of scope, matches this project's own
  already-documented, already-accepted limitation
  (`docs/architecture/audit-log-integrity-scoping-notes.md`) and the
  hard rule against silently changing the architecture.
- No SSE/push-based live trace stream -- WP-111 already reasoned
  through and rejected this for the current single-threaded
  `HTTPServer`; re-litigating that is out of this review's own scope.
- No new `EventBus` subscriber type, no "skill invocation" event --
  a skill cannot be invoked, so there is nothing real for such an
  event to describe.

## Testing

`tests/unit/test_audit_kernel.py`: a real `fs.list_dir` call (grouped
under the "filesystem" skill) is correctly isolated from an unrelated
`ping` call by `--skill filesystem`; `--skill` and `--capability-id`
combine with AND semantics; both an unregistered skill id and a
malformed (whitespace-containing) one return an honest empty result,
never raise.
