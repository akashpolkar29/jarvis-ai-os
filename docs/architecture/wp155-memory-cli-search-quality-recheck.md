# Memory CLI/search quality, re-checked (WP-155, 2026-09-12)

## Status

Investigated, **already solved** -- no code change.

## What was investigated

Whether `jarvis memory retrieve <query>` still has any real, concrete
usability or correctness gap, beyond what two already-completed pieces
of work cover:

- WP-144 (2026-09-12, this same session's queue): fixed the one real,
  demonstrated bug -- a granted, zero-match recall printed nothing at
  all, indistinguishable from a silent failure. Already closed.
- The retrieval-quality evaluation (`docs/architecture/
  retrieval-quality-eval-results.md`, "5 mixed real tasks" prompt,
  Task 3): a real, 35-fact corpus with deliberate distractors and 25
  real queries against the actual production pipeline, measuring
  84.0% top-1 accuracy / 92.0% top-3 recall, with two concrete failure
  cases investigated directly.

**Real checks run live, not assumed, before concluding nothing new was
found**: an empty query string (`jarvis memory retrieve ""`) returns
cleanly, no crash; `--limit 0` returns cleanly ("No matching memories
found."), no crash; a negative `--limit` (spot-checked as part of
WP-152's own numeric-flag review) already degrades gracefully via
SQLite's own negative-`LIMIT`-means-unlimited behavior, not a bug.

No new duplicate-result, ranking-clarity, or error-handling gap was
found beyond what those two already cover.

## What was deliberately not built

- No similarity-score/rank display in `jarvis memory retrieve`'s own
  output -- `RetrievalPort.retrieve()`'s contract returns ranked
  records, not scores; exposing an internal ranking number was judged
  a cosmetic addition, not a quality fix, and out of this work
  package's own narrow "smallest useful improvement" scope.
- No re-evaluation of the retrieval pipeline itself -- the existing
  evaluation already measured accuracy against the real, current
  production pipeline; re-running it would not surface anything new
  without a pipeline change, which this work package did not make.
