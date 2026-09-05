# Kernel-path performance benchmark results (WP-67, 10-phase pass, Phase 4)

## Status

Real, recorded results from a real run -- not a projection, not a repeated CI artifact.

## Date

2026-09-05

## What this is

`poc/wp67_kernel_benchmark.py` produced the real numbers below on this
real development machine. Re-run the script directly for current
numbers -- this document is a snapshot, not a live-updating source of
truth, matching `m4-benchmark-results.md`'s own established precedent
exactly.

## Machine

AMD Ryzen 9 8940HX (32 logical CPUs), 196GB free disk, Python 3.12.3.
Embedding inference ran CPU-only via ONNX (`fastembed`,
`BAAI/bge-small-en-v1.5`, 384 dimensions) -- the same real pipeline
`m4-benchmark-results.md` already used, not re-justified here.

## Scope, and what this pass may not touch

This benchmark measures `JsonFileAuditStorageAdapter`'s real, existing
whole-file-rewrite behavior at scale. It does not attempt to fix that
adapter's already-known, already-documented gaps (the cross-process
race, the whole-file-replacement cost itself) -- both remain open,
awaiting the user's own architecture decision, per this pass's own
hard scope boundary and `docs/threat-model/v0.md`'s existing note on
both.

## 1. `JsonFileAuditStorageAdapter`: save()/load() in isolation

Real `AuditChain`/`AuditRecord` objects (one real `Decision`, obtained
via one real `authorize_ping()` call, reused to fill the chain) --
isolates the file-I/O cost alone from embedding/orchestrator overhead.

| Chain size | save() | load() |
|---|---|---|
| 10 | 0.339ms | 0.451ms |
| 100 | 2.854ms | 3.619ms |
| 500 | 14.171ms | 13.609ms |
| 2,000 | 44.076ms | 62.966ms |

Real, confirmed linear (O(n)) growth, exactly as expected from a
whole-file JSON rewrite/re-read on every call -- roughly 22µs/record
for save, 31µs/record for load at this scale. Not fixed here (see
"Scope" above); this is the number by which any future fix's benefit
would be measured.

## 2. `authorize_ping()`: real end-to-end call, growing chain

Every real capability call in this codebase today pays this same
load-authorize-save cost (see `kernel/ping.py`'s own docstring: "Loaded
before the call and saved again after"). Real per-call latency,
measured directly, no mocking, against a chain growing from a real,
repeated series of calls:

| Call # (= chain size at that point) | Latency |
|---|---|
| 1 | 0.254ms |
| 10 | 0.555ms |
| 50 | 1.704ms |
| 100 | 3.301ms |
| 300 | 14.190ms |
| 600 | 18.758ms |
| 1,000 | 31.433ms |

Confirms the isolated adapter numbers above show up directly in
real, user-facing capability latency: by 1,000 real invocations, every
subsequent one already costs ~31ms just to load+save the accumulated
chain, before any actual capability work happens. Still well under any
threshold a human would perceive as sluggish at this scale; the
concern is the trend (O(n) per call, O(n²) total across n calls), not
today's absolute number.

## 3. `authorize_and_remember()`/`authorize_and_recall()`: real embeddings

A genuinely new number: WP-61/62's own benchmark measured only the
cosine-similarity math over synthetic vectors, never the real
embedding-inference latency real callers actually pay. One real,
one-time warmup call (first-use model download + ONNX session load,
~30s on this machine's connection) was excluded from the timed rows
below -- a real cost, but not a per-write one, and would otherwise
badly distort record #1's own number.

| Record # | write() | recall() |
|---|---|---|
| 1 | 91.904ms | 87.858ms |
| 10 | 96.200ms | 108.644ms |
| 50 | 131.446ms | 135.290ms |
| 100 | 116.925ms | 127.905ms |
| 200 | 124.104ms | 145.705ms |

Real embedding inference (~90-100ms/call on this CPU-only pipeline)
dominates both write and recall latency at this scale -- the
brute-force cosine-similarity math itself (per WP-61/62's own
benchmark, sub-millisecond through 10,000 synthetic vectors) is not
yet the bottleneck; real end-to-end latency here is essentially flat
across 1-200 records, bounded by embedding inference, not by corpus
size or audit-chain growth (both real but small at this scale relative
to inference cost).

## Honest limitations

Single machine, single run, not a formal performance-test environment
or a CI-gated regression check -- matching this project's own existing
precedent for `poc/wp61_vector_store_benchmark.py` (a real, recorded
spike, not a repeated benchmark suite). No CI step re-runs this
script: a stable perf-regression gate would need a dedicated,
isolated runner to avoid noisy-neighbor variance on shared CI
infrastructure, which is out of this phase's own scope to build.
