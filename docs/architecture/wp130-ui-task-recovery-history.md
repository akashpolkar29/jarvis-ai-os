# Task recovery/history visibility in the UI (WP-130, 2026-09-12)

## Status

Real, implemented. No ADR -- no new `CapabilityId`/`Effect`/`Tier`,
no new authorization path. Reuses `authorize_and_recover_task`
(WP-126) and fields `authorize_and_get_task` already computes
(WP-116/WP-124/WP-125), exactly mirroring WP-119/WP-123's own
"real UI counterpart to an existing kernel action" precedent.

## What was built

`GET /api/tasks/<task_id>` now also returns `updated_at`,
`scheduled_at`, `due`, `stale`, and `attempts` -- all real fields the
kernel already computed on every call, none of it previously
surfaced over HTTP (only `goal`/`status`/`reason` were).

`POST /api/tasks/<task_id>/recover` reuses
`kernel.tasks.authorize_and_recover_task` (WP-126) completely
unmodified -- the exact same function `jarvis task recover` already
calls. Mirrors `/cancel`'s own shape: no server-side goal lookup
needed, since `authorize_and_recover_task` already does its own
lookup, status check, and staleness check internally.

The frontend's `pollTaskStatus` status-change message now also shows
the real `reason` (when present) and a real attempt count (when
`attempts` is non-empty) -- e.g. `"Status: failed\nReason:
...\nAttempts: 2"` -- both already returned by the enriched GET
response, neither previously shown anywhere in the UI.

## What was deliberately not built: a frontend "Recover" button

Investigated directly, not assumed: `pollTaskStatus` is only ever
started right after a task is created or a run/retry attempt
concludes, and its own poll ceiling (`TASK_POLL_MAX_ATTEMPTS = 60` at
`TASK_POLL_INTERVAL_MS = 2000`, WP-111's own "~2 minutes total, a
real, bounded ceiling, not forever") ends the poll loop long before
`STALE_RUNNING_THRESHOLD_SECONDS` (1800s, 30 minutes) could ever
genuinely elapse within that same live browser session. A task is
never already stale at the moment polling starts, since polling only
ever starts immediately after a fresh creation or run attempt. A
"Recover" button wired into this poll loop would therefore be real
code that can never practically fire under the UI's own existing
usage pattern -- adding it would be inventing a feature for its own
sake, not closing a real, reachable gap, so it was not built. The
backend endpoint itself is real, tested, and independently callable
(by `jarvis task recover`, by direct HTTP, or by a future, longer-
lived UI surface) regardless of this specific frontend limitation.

## Testing

`test_ui_server.py`: a new test proves the enriched `GET` response's
five new fields on a real, freshly-created task
(`updated_at` present, `scheduled_at`/`stale`/`due` correctly
default-`None`/`False`, `attempts` an empty list). A new WP-130
section mirrors `/cancel`'s own test shape exactly for `/recover`:
not-found-but-granted lookup, empty task id (404), a real round trip
against a task forced `"running"` with a deliberately ancient
`updated_at` (a real `_FixedClock`, not mocked authorization), a
mocked refusal, a handled kernel error, and the unexpected-error
traceback-suppression case. 100% branch coverage maintained on
`ui_server.py`. The frontend's small string-formatting change has no
dedicated JS test (this repository's own already-documented,
unchanged limitation) but was reviewed directly against the exact
JSON shape the new tests prove the backend returns.
