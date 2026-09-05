# End-to-end scenarios — real capabilities composed together

**Status: two real, passing integration tests, no design decisions
made.** Written 2026-09-05 (10-phase combined pass, Phase 1). Every
capability in this codebase has been tested in isolation; this
document and its accompanying test file
(`tests/integration/test_end_to_end_scenarios.py`) are the first proof
that they compose correctly in a realistic sequence a real user would
actually run.

## Why these two scenarios

Grounded in this project's own charter examples ("continue yesterday's
project") rather than contrived toy sequences:

1. **Read a real file, remember it, recall it back.** The most basic
   real "continue where I left off" shape: `fs.read_file` produces
   real content, `memory.write` stores it, `memory.retrieve` gets it
   back later. Every assertion checks the *same* real string survived
   the whole round trip, not just that each call individually
   succeeded.
2. **Recalled context feeds a real coding task, then a real git
   session concludes it.** The next real step in that same session
   shape: something remembered earlier becomes the actual prompt text
   for a new task, and the session ends with a real, observable git
   state change (`git.status` → `git.commit` → `git.status` again,
   confirming a clean tree).

## What's real and what's faked, and why

Memory's own embedding step uses a fake, deterministic `EmbeddingPort`
in both scenarios — matching this codebase's own already-established
"only the true external-I/O edge is faked" convention
(`test_coding_kernel.py`'s own docstring, `tests/unit/adapters/test_memory.py`'s
own `_FakeEmbeddingPort`). The real vector-similarity model is a
separate, already live-verified concern
(`docs/architecture/m4-benchmark-results.md`) — not what these
scenarios exist to prove, and using the real model would make this
test slow and non-deterministic for no real benefit here.

`coding.run_task` in the second scenario uses the real, local Ollama
default (`qwen2.5:0.5b`) wherever it's reachable, `skipif`-guarded
honestly where it is not (mirroring every other real-Ollama test in
this codebase). Every other step is a real adapter: a real file on a
real temporary filesystem, a real SQLite-backed memory store, a real
`git init`/`git commit` against a real, disposable repository (never
the actual JARVIS project repository).

## A real, empirically-found timing constraint, named honestly

The second scenario's first draft used a longer, context-heavy coding
task description. That made the real local model's own `SELF_REPAIR`
escalation rung (`DETERMINISTIC_FIX` has no real implementation yet,
WP-37, a pre-existing, already-named gap) take longer than
`LocalReasoningAdapter`'s own fixed 120-second per-request timeout on
this development machine — a real, observed `TimeoutError`, not a bug
in the composition being tested. Fixed by shortening the task prompt,
not by changing the adapter's own timeout (which is real production
behavior, not this test's own to change). This is a real, useful data
point for anyone else writing a real-Ollama integration test in this
codebase: keep the task prompt short, since a longer one measurably
risks the fixed real timeout once a real self-repair rung's own
longer, failure-context-laden prompt is generated internally.

## What was NOT found

No real bug was found in the actual data-flow composition itself —
`memory.write`'s real `Tainted[T]`/`Provenance` shape round-trips
through `memory.retrieve` intact, and a recalled record's own real
text value substitutes cleanly into a new capability's own real
argument. Stated plainly, not invented: this phase closes a real,
previously-untested gap (composition had never been proven), but the
underlying capabilities themselves already composed correctly.
