# Task retention policy preparation (WP-162, 2026-09-12)

## Status

Investigated, no policy chosen, no code changed — per this work
package's own explicit instruction not to decide the policy
unilaterally.

## What was investigated

`docs/OPEN_DECISIONS.md` item 52 (task/job-application record
retention) is the unresolved item this work package targets. The real
question needed: whether task records (and/or the job-application
ledger) should keep the shared 90-day memory-retention default, be
pinned, or get their own distinct retention window — a real,
system-wide default-policy choice this pass has no authority to make.

**Checked whether safe, neutral infrastructure could be added without
choosing that policy** — found it already exists, verified live, no
new code needed: `jarvis memory pin <identifier>` operates on any
record by identifier regardless of its own `"kind"` marker (`memory.pin`'s
own implementation has no `"kind"`-specific logic at all), so a task
id is already a valid, working identifier for it today. Verified
end to end: `task create` → `memory pin <task_id>` → `task status
<task_id>` still reads the pinned record correctly. See
`docs/architecture/wp151-task-retention-review.md`'s own "Update
2026-09-12" section for the full account.

## What was built

Nothing new — the real, neutral, opt-in infrastructure this work
package looked for already exists (`memory.pin`, `memory.forget`, both
pre-existing, both identifier-agnostic). Documented, not built.

## What remains, unresolved by design

The real, precise decision needed from the user, unchanged: should
task/job-application records get a distinct default retention policy
(and if so, which), or is the shared 90-day default the accepted,
intended behavior? See `docs/OPEN_DECISIONS.md` item 52 for the full
statement of the question and the two candidate fixes already
considered and rejected as unilateral policy decisions.
