# CI pipeline speed audit (5 combined hygiene/reliability tasks, Task 4)

## Status

Real, measured baseline; two real, safe changes applied; real
after-timing measured from an actual CI run on this branch before
merging. No check was skipped, weakened, or reduced in coverage.

## Real baseline, measured directly from 5 recent, real `main` runs (GitHub Actions API, not estimated)

| Run | Wall clock (both matrix legs, workflow start to finish) |
| --- | --- |
| `33985705838` | 138s |
| `33985237146` | 145s |
| `33984507174` | 158s |
| `33983547983` | 163s |
| `33956871660` | 162s |

Per-step breakdown (from `33985705838`'s own real job-step timestamps,
representative of the others -- both matrix legs matched within a
couple seconds of each other):

| Step | Real duration |
| --- | --- |
| Install system dependencies (apt-get) | ~13-14s |
| Install dependencies (`uv sync`) | ~15-16s |
| Start GreenMail | ~7-8s |
| Start Radicale | ~3-4s |
| ruff / mypy / lint-imports (combined) | ~14s |
| pytest (with coverage) | ~54-55s |
| sphinx-build (API reference) | ~19-21s |

`pytest` is the dominant real cost, by a wide margin.

## Real change 1: explicit `uv` dependency caching

`astral-sh/setup-uv@v3`'s own real, documented `enable-cache` input
defaults to `"auto"` (confirmed against the action's own README, not
assumed). Direct evidence this default was not, in practice, producing
a warm cache for this repo: the "Install dependencies" step measured a
flat ~15-19s across every historical run checked, spanning many hours
and many pushes, with `uv.lock` completely unchanged in between --
the signature of a cold resolve every time, not a warm one. Added
explicit `enable-cache: true` plus a per-Python-version
`cache-suffix` (the two matrix legs resolve different wheels for
`3.12`/`3.13` and must not collide on one cache key). This is a real,
safe change: it can only speed up an already-fully-deterministic
`uv sync --locked` step (the lockfile is authoritative regardless of
cache state), never change what gets installed or skip a check.

## Real change 2: parallelize the two independent local test-server startups

`Start local GreenMail IMAP/SMTP test server` and `Start local
Radicale CalDAV test server` were two fully sequential steps despite
being completely independent (different Docker images, different
ports, no shared state, no ordering requirement between them --
confirmed by re-reading both blocks directly). Merged into one step
that launches both `docker run -d` calls in the background (`&`,
`wait`) so their image pulls/container creation overlap, then runs a
single combined readiness loop that polls both real conditions
(GreenMail's real IMAP4 handshake; Radicale's real HTTP reachability)
every iteration until both succeed or the same real 30s deadline
elapses. Both original, specific, real readiness checks are unchanged
and still both required to pass -- a failure on either one still fails
closed with a real `docker logs` dump identifying which server never
became ready, matching the original two-step behavior's own failure
mode exactly, just interleaved rather than duplicated per-container.

## Investigated, deliberately not applied: `pytest-xdist` parallelization

`pytest` is the dominant real cost (~54-55s of the job's own ~135-165s
total) and is the one lever with real, large upside --
`pytest-xdist`'s worker-based parallelism could plausibly cut this
step meaningfully on a multi-core runner. **Not applied here**: this
same prompt's own Task 2 (real test-suite flakiness audit) just
confirmed the suite's current behavior only under *serial* execution,
5 consecutive full runs, explicitly noting that methodology "does not
exercise true concurrent in-process races." Real, concrete risks
specific to this suite that a genuinely safe adoption would need to
rule out first, not merely hope don't apply: fixed Docker container
names (`jarvis-test-greenmail`/`jarvis-test-radicale`) shared across
the whole run, a `memory.sqlite3` relative-path CWD hazard already
found and fixed once this session (Phase 10), and GTK4 window-related
tests already guarded against leaking real windows on the real
desktop. Adopting `-n auto` without first auditing every test for
process-isolation safety would risk introducing exactly the kind of
new flakiness this pass's own Task 2 was run to rule out -- a real,
substantive, separate investigation, correctly out of this specific
audit's own "safe optimization only" scope. Named here as a real,
identified, larger lever for a future, dedicated pass, not silently
dropped.

## Real after-timing, measured from an actual CI run on this branch

<!-- Filled in after this branch's own CI run completes, before merging to main. -->
